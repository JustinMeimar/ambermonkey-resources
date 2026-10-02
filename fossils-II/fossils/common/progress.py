import os
from pathlib import Path
import signal
import subprocess
import sys
import time


def progress(message):
    print(f'[recording] {message}', file=sys.stderr, flush=True)


def run_logged(command, cwd, env, directory, duration=None, heartbeat_seconds=15):
    directory = Path(directory)
    log = directory / 'harness.log'
    progress(f'Harness log: {log}')
    started = time.monotonic()
    heartbeat = started + heartbeat_seconds
    pending = ''
    with log.open('w') as output, log.open(errors='replace') as reader:
        def relay():
            nonlocal pending
            chunk = reader.read(65536)
            if chunk:
                lines = (pending + chunk).split('\n')
                pending = lines.pop()
                for line in lines:
                    print(line[:600] + (' ... [full line in harness.log]' if len(line) > 600 else ''),
                          file=sys.stderr, flush=True)
            return bool(chunk)

        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=output,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            while process.poll() is None:
                relay()
                now = time.monotonic()
                if duration is not None and now - started >= duration:
                    raise subprocess.TimeoutExpired(command, duration)
                if now >= heartbeat:
                    logs = list(directory.glob('trace*.moz_log'))
                    size = sum(path.stat().st_size for path in logs)
                    progress(f'{directory.name}: {now - started:.0f}s elapsed; '
                             f'{len(logs)} trace files, {size / 1024**2:.1f} MiB; harness running')
                    heartbeat = now + heartbeat_seconds
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    pass
            status = process.returncode
        except (KeyboardInterrupt, subprocess.TimeoutExpired):
            progress('Stopping browser process group and preserving logs')
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                status = process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise RuntimeError('Browser required SIGKILL; recording is incomplete.')
            if duration is not None and status == -signal.SIGTERM:
                status = 0
            elif status == 0:
                status = 130
        finally:
            while relay():
                pass
            if pending:
                print(pending[:600], file=sys.stderr, flush=True)
        progress(f'{directory.name}: harness exited {status} after {time.monotonic() - started:.0f}s')
        return status
