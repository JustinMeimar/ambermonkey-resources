#!/usr/bin/env python3
"""Sidecar smaps sampler for AWSY tp6 runs. Watches the AWSY --results
directory for new memory-report-*.json.gz files (which AWSY writes at each
checkpoint via nsIMemoryInfoDumper) and on each new file dumps
/proc/<pid>/smaps for every discovered Firefox process. Terminates on SIGTERM.

Filename convention: memory-report-<checkpoint>-<iteration>.json.gz produced
by awsy_test_case.do_memory_report -> awsy_test_case.py:172. Checkpoint
names emitted by AWSY tp6 are:
  Start, StartSettled, TabsOpen, TabsOpenSettled, TabsOpenForceGC,
  TabsClosedExtraProcesses, TabsClosed, TabsClosedSettled, TabsClosedForceGC.

Writes:
  $DIR/sidecar/pids.jsonl                          append-only PID lifecycle log
  $DIR/sidecar/smaps/<seq>-<checkpoint>-<pid>.json raw per-VMA rows per (checkpoint,pid)
  $DIR/sidecar/meta.json                           run-level metadata, written on exit
"""

import argparse
import errno
import json
import os
import platform
import re
import resource
import signal
import sys
import threading
import time
from pathlib import Path


HEADER_RE = re.compile(
    r"^(?P<start>[0-9a-f]+)-(?P<end>[0-9a-f]+)\s+"
    r"(?P<perms>[rwxps-]+)\s+"
    r"(?P<offset>[0-9a-f]+)\s+"
    r"(?P<dev>[0-9a-f]+:[0-9a-f]+)\s+"
    r"(?P<inode>\d+)"
    r"(?:\s+(?P<path>.*))?$"
)

KV_RE = re.compile(r"^([A-Za-z_]+):\s*(\d+)\s*kB$")

WANTED_KV = {
    "Size": "size_kb",
    "Rss": "rss_kb",
    "Pss": "pss_kb",
    "Shared_Clean": "shared_clean_kb",
    "Shared_Dirty": "shared_dirty_kb",
    "Private_Clean": "private_clean_kb",
    "Private_Dirty": "private_dirty_kb",
    "Referenced": "referenced_kb",
    "Anonymous": "anonymous_kb",
}


def now_us():
    return int(time.time() * 1_000_000)


def read_cmdline(pid):
    try:
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            return f.read().replace(b"\0", b" ").decode("utf-8", errors="replace").strip()
    except OSError:
        return None


def read_starttime(pid):
    """Return field 22 (starttime) from /proc/<pid>/stat, or None."""
    try:
        with open(f"/proc/{pid}/stat", "rb") as f:
            data = f.read()
    except OSError:
        return None
    # comm field can contain spaces; skip past the last ')'.
    end = data.rfind(b")")
    if end < 0:
        return None
    fields = data[end + 2 :].split()
    if len(fields) < 20:
        return None
    try:
        return int(fields[19])  # field 22 = index 19 after the two fields before comm
    except ValueError:
        return None


def classify(cmd):
    if not cmd or "firefox" not in cmd:
        return None
    if "-contentproc" in cmd:
        return "content"
    if "-parentBuildID" in cmd:
        # Content procs also carry -parentBuildID but that branch is above.
        return "content"
    return "parent"


def walk_smaps(pid):
    """Parse /proc/<pid>/smaps. Returns list of VMA dicts, or None on OSError."""
    vmas = []
    cur = None
    path = f"/proc/{pid}/smaps"
    try:
        with open(path, "r", errors="replace") as fh:
            for line in fh:
                m = HEADER_RE.match(line)
                if m:
                    if cur is not None:
                        vmas.append(cur)
                    cur = {
                        "start": m.group("start"),
                        "end": m.group("end"),
                        "perms": m.group("perms"),
                        "offset": m.group("offset"),
                        "dev": m.group("dev"),
                        "inode": int(m.group("inode")),
                        "path": (m.group("path") or "").strip(),
                        "size_kb": 0, "rss_kb": 0, "pss_kb": 0,
                        "shared_clean_kb": 0, "shared_dirty_kb": 0,
                        "private_clean_kb": 0, "private_dirty_kb": 0,
                        "referenced_kb": 0, "anonymous_kb": 0,
                    }
                    continue
                if cur is None:
                    continue
                colon = line.find(":")
                if colon < 0:
                    continue
                key = line[:colon]
                if key not in WANTED_KV:
                    continue
                m = KV_RE.match(line)
                if not m:
                    continue
                cur[WANTED_KV[key]] = int(m.group(2))
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ESRCH, errno.EACCES, errno.EPERM):
            return None
        raise
    if cur is not None:
        vmas.append(cur)
    return vmas


def safe_marker_slug(marker):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", marker)[:80] or "unnamed"


MEMREPORT_RE = re.compile(r"^memory-report-(?P<checkpoint>.+?)-(?P<iter>\d+)\.json\.gz$")


def resolve_exe(pid):
    """Return the absolute exe target of /proc/<pid>/exe, or None on OSError.

    Uses readlink so we get the launcher's actual binary (following any
    symlink), independent of what argv[0] happens to be. Strips the
    Linux "(deleted)" suffix that appears when the exe file was unlinked
    after the process started.
    """
    try:
        target = os.readlink(f"/proc/{pid}/exe")
    except OSError:
        return None
    if target.endswith(" (deleted)"):
        target = target[: -len(" (deleted)")]
    return target


class Sidecar:
    def __init__(self, dir_path, parent_exe, parent_cmdline, poll_ms,
                 interval_ms):
        self.dir = Path(dir_path)
        # Absolute path of the test binary. PIDs whose /proc/<pid>/exe does
        # not resolve to this exact file are ignored. This is what stops
        # co-resident daily-driver Firefox processes from polluting the run.
        self.parent_exe = os.path.realpath(parent_exe) if parent_exe else None
        # Optional cmdline substring filter, applied on top of exe. Kept for
        # backward compatibility; on its own it is too loose because argv[0]
        # collisions between a test binary and a user's system browser (e.g.
        # both contain "firefox") pull unrelated processes into the sample.
        self.parent_cmdline = parent_cmdline
        self.poll_s = poll_ms / 1000.0
        # When set, sample smaps every interval_ms regardless of any external
        # marker files. Emits markers of the form "interval:<seq>". Use for
        # workloads that do not write memory-report-*.json.gz (e.g. Speedometer
        # under Raptor). Marker-file watching still runs in parallel, so a
        # workload that DOES emit markers gets both sample streams.
        self.interval_s = interval_ms / 1000.0 if interval_ms else 0.0
        self.stop = threading.Event()

        self.sidecar_dir = self.dir / "sidecar"
        self.smaps_dir = self.sidecar_dir / "smaps"
        self.sidecar_dir.mkdir(parents=True, exist_ok=True)
        self.smaps_dir.mkdir(parents=True, exist_ok=True)
        self.pids_log = open(self.sidecar_dir / "pids.jsonl", "a", buffering=1)

        self.warnings = []
        self.epoch_us = now_us()

        # (pid, starttime) -> {"kind","cmd","first_ts"}
        self.seen = {}
        self.seen_lock = threading.Lock()

        # Track memory-report file names we've already reacted to. This is the
        # sidecar's "marker channel" — AWSY writes memory-report-<cp>-<i>.json.gz
        # at each checkpoint via nsIMemoryInfoDumper.
        self.seen_reports = set()
        self.seq = 0
        self.interval_seq = 0
        self.epperm_reported = False

    def append_pid_event(self, event, pid, starttime, kind, cmd):
        row = {"ts_us": now_us(), "event": event, "pid": pid,
               "starttime": starttime, "kind": kind, "cmd": cmd}
        self.pids_log.write(json.dumps(row) + "\n")

    def discover_loop(self):
        while not self.stop.is_set():
            try:
                self._discover_pass()
            except Exception as e:
                self.warnings.append(f"discover_pass: {type(e).__name__}: {e}")
            self.stop.wait(self.poll_s)

    def _discover_pass(self):
        current = set()
        for name in os.listdir("/proc"):
            if not name.isdigit():
                continue
            pid = int(name)
            cmd = read_cmdline(pid)
            if cmd is None:
                continue
            if self.parent_exe is not None:
                exe = resolve_exe(pid)
                if exe != self.parent_exe:
                    continue
            if self.parent_cmdline and self.parent_cmdline not in cmd:
                continue
            starttime = read_starttime(pid)
            if starttime is None:
                continue
            key = (pid, starttime)
            current.add(key)
            with self.seen_lock:
                if key in self.seen:
                    continue
                kind = classify(cmd) or "other"
                self.seen[key] = {"kind": kind, "cmd": cmd, "first_ts": now_us()}
                self.append_pid_event("discover", pid, starttime, kind, cmd)
        # Detect vanished pids (that were previously in seen).
        with self.seen_lock:
            gone = [k for k in self.seen if k not in current]
            for key in gone:
                info = self.seen.pop(key)
                self.append_pid_event("vanish", key[0], key[1],
                                      info["kind"], info["cmd"])

    def marker_loop(self):
        while not self.stop.is_set():
            try:
                self._marker_pass()
            except Exception as e:
                self.warnings.append(f"marker_pass: {type(e).__name__}: {e}")
            self.stop.wait(self.poll_s)

    def interval_loop(self):
        # Wait one interval before the first sample so the browser can spawn
        # its content procs before we start counting.
        while not self.stop.is_set():
            if self.stop.wait(self.interval_s):
                return
            try:
                self.interval_seq += 1
                self.take_snapshot(f"interval:{self.interval_seq}")
            except Exception as e:
                self.warnings.append(
                    f"interval_pass: {type(e).__name__}: {e}"
                )

    def _marker_pass(self):
        """Scan $DIR for new memory-report-*.json.gz files. Each new file is
        a checkpoint firing; snapshot smaps immediately."""
        try:
            entries = os.listdir(self.dir)
        except OSError:
            return
        # Order deterministically by (checkpoint order in filename) — but
        # honestly first-seen is fine since AWSY writes them sequentially.
        for name in sorted(entries):
            m = MEMREPORT_RE.match(name)
            if not m:
                continue
            if name in self.seen_reports:
                continue
            self.seen_reports.add(name)
            checkpoint = m.group("checkpoint")
            iteration = int(m.group("iter"))
            marker = f"{checkpoint}:{iteration}"
            self.take_snapshot(marker)

    def take_snapshot(self, marker):
        self.seq += 1
        marker_ts = now_us()
        with self.seen_lock:
            pids = list(self.seen.items())  # snapshot
        slug = safe_marker_slug(marker)
        for (pid, starttime), info in pids:
            vmas = walk_smaps(pid)
            if vmas is None:
                # PID vanished or unreadable. Record a stub with error.
                out = {
                    "seq": self.seq, "marker": marker,
                    "marker_ts_us": marker_ts, "sample_ts_us": now_us(),
                    "pid": pid, "starttime": starttime,
                    "kind": info["kind"], "cmd": info["cmd"],
                    "vmas": [], "error": "unreadable",
                }
                if not self.epperm_reported and info["kind"] == "content":
                    # Only warn once about permission problems.
                    try:
                        open(f"/proc/{pid}/smaps").close()
                    except PermissionError:
                        self.warnings.append(
                            f"EPERM reading /proc/{pid}/smaps — "
                            "content sandbox likely enabled; unset MOZ_DISABLE_CONTENT_SANDBOX=0"
                        )
                        self.epperm_reported = True
                    except OSError:
                        pass
            else:
                out = {
                    "seq": self.seq, "marker": marker,
                    "marker_ts_us": marker_ts, "sample_ts_us": now_us(),
                    "pid": pid, "starttime": starttime,
                    "kind": info["kind"], "cmd": info["cmd"],
                    "vmas": vmas,
                }
            fname = f"{self.seq:04d}-{slug}-{pid}.json"
            (self.smaps_dir / fname).write_text(json.dumps(out) + "\n")

    def run(self):
        signal.signal(signal.SIGTERM, self._on_term)
        signal.signal(signal.SIGINT, self._on_term)
        t_disc = threading.Thread(target=self.discover_loop, daemon=True)
        t_mark = threading.Thread(target=self.marker_loop, daemon=True)
        t_disc.start()
        t_mark.start()
        t_intv = None
        if self.interval_s > 0:
            t_intv = threading.Thread(target=self.interval_loop, daemon=True)
            t_intv.start()
        while not self.stop.is_set():
            self.stop.wait(0.5)
        t_disc.join(timeout=2.0)
        t_mark.join(timeout=2.0)
        if t_intv is not None:
            t_intv.join(timeout=self.interval_s + 2.0)
        self._write_meta()
        try:
            self.pids_log.flush()
            self.pids_log.close()
        except Exception:
            pass

    def _on_term(self, signum, frame):
        self.stop.set()

    def _write_meta(self):
        meta = {
            "schema_version": 1,
            "argv": sys.argv,
            "dir": str(self.dir),
            "epoch_us": self.epoch_us,
            "exit_us": now_us(),
            "page_size": resource.getpagesize(),
            "uname": platform.uname()._asdict(),
            "warnings": self.warnings,
            "n_markers_seen": self.seq,
        }
        (self.sidecar_dir / "meta.json").write_text(json.dumps(meta, indent=2))


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--dir", required=True, help="JS_INSTR_DIR (run scratch dir)")
    p.add_argument("--parent-exe", default=None,
                   help="absolute path to the test binary; PIDs whose "
                        "/proc/<pid>/exe does not resolve here are ignored. "
                        "Strongly preferred over --parent-cmdline for isolating "
                        "the test browser from any co-resident Firefox instance.")
    p.add_argument("--parent-cmdline", default=None,
                   help="optional substring PIDs must contain in "
                        "/proc/<pid>/cmdline; applied on top of --parent-exe "
                        "when both are set. On its own, this filter is too "
                        "loose on machines with an unrelated Firefox running.")
    p.add_argument("--poll-ms", type=int, default=50)
    p.add_argument("--interval-ms", type=int, default=0,
                   help="if >0, also sample smaps on this interval regardless "
                        "of marker files. Emits marker 'interval:<n>'. Use "
                        "for workloads (e.g. Raptor Speedometer) that do not "
                        "themselves write memory-report-*.json.gz files.")
    args = p.parse_args()
    if args.parent_exe is None and args.parent_cmdline is None:
        p.error("at least one of --parent-exe or --parent-cmdline is required")
    return args


def main():
    args = parse_args()
    Sidecar(args.dir, args.parent_exe, args.parent_cmdline, args.poll_ms,
            args.interval_ms).run()


if __name__ == "__main__":
    main()
