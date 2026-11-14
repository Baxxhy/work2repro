import os
import pty
import re
import select
import shutil
import signal
import struct
import subprocess
import termios
import time
import fcntl
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
PROGRAM = Path(os.environ.get("WALK_EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def program():
    assert PROGRAM.is_file(), f"program not found: {PROGRAM}"
    return PROGRAM


def run_pipe(program, *args, env=None, cwd=None, timeout=5):
    merged = os.environ.copy()
    if env:
        merged.update({k: str(v) for k, v in env.items()})
    return subprocess.run([str(program), *map(str, args)], cwd=cwd, env=merged,
                          stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


class Terminal:
    def __init__(self, program, args=(), cwd=None, env=None, rows=30, cols=120):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        merged = os.environ.copy()
        if env:
            merged.update({k: str(v) for k, v in env.items()})
        self.proc = subprocess.Popen([str(program), *map(str, args)], cwd=cwd, env=merged,
                                     stdin=slave, stdout=slave, stderr=slave,
                                     start_new_session=True,
                                     preexec_fn=lambda: fcntl.ioctl(slave, termios.TIOCSCTTY, 0),
                                     close_fds=True)
        os.close(slave)
        self.data = bytearray()

    def read_for(self, duration=0.5):
        end = time.monotonic() + duration
        while time.monotonic() < end and self.proc.poll() is None:
            ready, _, _ = select.select([self.master], [], [], min(.05, end-time.monotonic()))
            if ready:
                try:
                    chunk = os.read(self.master, 65536)
                except OSError:
                    break
                if not chunk:
                    break
                self.data.extend(chunk)
        return self.text

    @property
    def text(self):
        s = self.data.decode("utf-8", "replace")
        s = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", s)
        s = re.sub(r"\x1b\][^\x07]*(?:\x07|\x1b\\)", "", s)
        return s

    def send(self, value):
        os.write(self.master, value if isinstance(value, bytes) else value.encode())
        return self.read_for(.3)

    def close(self):
        if self.proc.poll() is None:
            try:
                os.killpg(self.proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.proc.wait(timeout=2)
        os.close(self.master)


@pytest.fixture
def terminal_factory(program):
    terminals = []
    def create(*args, **kwargs):
        t = Terminal(program, *args, **kwargs)
        terminals.append(t)
        return t
    yield create
    for t in terminals:
        t.close()
