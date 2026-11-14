import os
import pty
import select
import subprocess
import time
from pathlib import Path


EXE = Path(__file__).resolve().parent.parent / "executable"


def _read_for(fd, duration):
    end = time.monotonic() + duration
    chunks = []
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], min(0.05, end - time.monotonic()))
        if not ready:
            continue
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
    return b"".join(chunks)


def _session(keys=(), wait=0.12):
    master, slave = pty.openpty()
    env = os.environ.copy()
    env.update({"TERM": "xterm", "COLUMNS": "120", "LINES": "40"})
    proc = subprocess.Popen([str(EXE)], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
    os.close(slave)
    try:
        initial = _read_for(master, 0.4)
        assert initial
        snapshots = [initial]
        for key in keys:
            os.write(master, key)
            snapshots.append(_read_for(master, wait))
        return proc, master, snapshots
    except BaseException:
        proc.kill()
        proc.wait(timeout=2)
        os.close(master)
        raise


def test_interactive_paints_promptly_and_quits():
    proc, master, snapshots = _session([b"q"])
    try:
        assert snapshots[0]
        proc.wait(timeout=2)
        assert proc.returncode == 0
    finally:
        os.close(master)


def test_interactive_help_setup_sort_and_escape_overlays():
    proc, master, snapshots = _session([b"h", b"\x1b", b"\x1bOQ", b"\x1b", b"\x1b[17~", b"\x1b", b"q"])
    try:
        assert all(snapshots)
        proc.wait(timeout=3)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        os.close(master)


def test_interactive_tree_navigation_search_and_filter():
    proc, master, snapshots = _session([b"t", b"\x1b[B", b"\x1b[B", b"\x1b[A", b"/", b"bash", b"\x1b", b"\\", b"sleep", b"\x1b", b"q"])
    try:
        assert all(snapshots)
        # q closes any remaining overlay; a second q always exits.
        if proc.poll() is None:
            os.write(master, b"q")
        proc.wait(timeout=3)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=2)
        os.close(master)

