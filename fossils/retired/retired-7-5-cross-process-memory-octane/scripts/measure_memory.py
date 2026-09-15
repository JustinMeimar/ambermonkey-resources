#!/usr/bin/env python3
"""Run a command and emit peak_rss_kb / peak_anon_kb / peak_anon_exec_kb on stderr."""

import re
import resource
import subprocess
import sys
import threading
import time


HEADER_RE = re.compile(r"^[0-9a-f]+-[0-9a-f]+ [rwxp-]+ ")


def scan_smaps(pid):
    """Return (anon_kb, anon_exec_kb) or None if pid vanished."""
    anon = 0
    anon_exec = 0
    is_anon = False
    is_exec = False
    try:
        with open(f"/proc/{pid}/smaps") as fh:
            for line in fh:
                if HEADER_RE.match(line):
                    parts = line.split(maxsplit=5)
                    perms = parts[1]
                    path = parts[5].strip() if len(parts) == 6 else ""
                    is_anon = not path
                    is_exec = "x" in perms
                elif is_anon and line.startswith("Rss:"):
                    rss = int(line.split()[1])
                    anon += rss
                    if is_exec:
                        anon_exec += rss
    except OSError:
        return None
    return anon, anon_exec


def poll(pid, out, stop, interval=0.05):
    while not stop.is_set():
        r = scan_smaps(pid)
        if r is None:
            return
        anon, anon_exec = r
        if anon > out["anon"]:
            out["anon"] = anon
        if anon_exec > out["anon_exec"]:
            out["anon_exec"] = anon_exec
        time.sleep(interval)


p = subprocess.Popen(sys.argv[1:])
out = {"anon": 0, "anon_exec": 0}
stop = threading.Event()
t = threading.Thread(target=poll, args=(p.pid, out, stop), daemon=True)
t.start()
p.wait()
stop.set()
t.join(timeout=1.0)

r = resource.getrusage(resource.RUSAGE_CHILDREN)
print(f"peak_rss_kb={r.ru_maxrss}", file=sys.stderr, flush=True)
print(f"peak_anon_kb={out['anon']}", file=sys.stderr, flush=True)
print(f"peak_anon_exec_kb={out['anon_exec']}", file=sys.stderr, flush=True)
sys.exit(p.returncode)
