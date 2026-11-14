import os
import pty
import re
import select
import signal
import subprocess
import time
import fcntl
import termios
import struct

import pytest

EXE = "/workspace/executable"

HELP = """ Usage: cmatrix -[abBcfhlsmVxk] [-u delay] [-C color] [-t tty] [-M message]
 -a: Asynchronous scroll
 -b: Bold characters on
 -B: All bold characters (overrides -b)
 -c: Use Japanese characters as seen in the original matrix. Requires appropriate fonts
 -f: Force the linux $TERM type to be on
 -l: Linux mode (uses matrix console font)
 -L: Lock mode (can be closed from another terminal)
 -o: Use old-style scrolling
 -h: Print usage and exit
 -n: No bold characters (overrides -b and -B, default)
 -s: "Screensaver" mode, exits on first keystroke
 -x: X window mode, use if your xterm is using mtx.pcf
 -V: Print version information and exit
 -M [message]: Prints your message in the center of the screen. Overrides -L's default message.
 -u delay (0 - 10, default 4): Screen update delay
 -C [color]: Use this color for matrix (default green)
 -r: rainbow mode
 -m: lambda mode
 -k: Characters change while scrolling. (Works without -o opt.)
 -t [tty]: Set tty to use
"""


def invoke(*args, term="dumb"):
    env = os.environ.copy()
    env["TERM"] = term
    return subprocess.run([EXE, *args], env=env, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=3)


@pytest.mark.parametrize("args", [
    ("-h",), ("-?",), ("--help",), ("-z",), ("-Z",),
    ("--version",), ("--nonexistent",), ("-C",), ("-u",), ("-M",), ("-t",),
], ids=["h", "question", "long-help", "unknown-lower", "unknown-upper",
       "long-version-unknown", "long-unknown", "missing-color", "missing-delay",
       "missing-message", "missing-tty"])
def test_help_exit_cases(args):
    p = invoke(*args)
    assert p.returncode == 0
    assert p.stdout.decode() == HELP
    assert p.stderr == b""
    assert b"\x1b" not in p.stdout


@pytest.mark.parametrize("args", [("-V",), ("-abBnkcrmx -V",), ("-t", "/dev/null", "-V"),
                                    ("-u3.5", "-V"), ("-nBbn", "-V")],
                         ids=["basic", "grouped-flags", "tty-value", "decimal-prefix", "bold-flags"])
def test_version_shape_and_precedence(args):
    p = invoke(*args)
    out = p.stdout.decode()
    assert p.returncode == 0
    assert p.stderr == b""
    assert "compiled " in out
    assert re.fullmatch(r" CMatrix version 2\.0 \(compiled [A-Z][a-z]{2} +\d{1,2} \d{2}:\d{2}:\d{2} \d{4}\)\nEmail: abishekvashok@gmail.com\nWeb: https://github.com/abishekvashok/cmatrix\n", out)
    assert out != HELP and "\x1b" not in out


def test_help_and_version_are_left_to_right_terminators():
    assert invoke("-V", "-h").stdout.decode().startswith(" CMatrix version")
    assert invoke("-h", "-V").stdout.decode() == HELP
    assert invoke("-ab", "-h").stdout.decode() == HELP


@pytest.mark.parametrize("color", ["green", "RED", "ReD", "blue", "white", "yellow", "cyan", "magenta", "black"],
                         ids=["green", "red-upper", "red-mixed", "blue", "white", "yellow", "cyan", "magenta", "black"])
def test_accepted_colors_can_precede_info(color):
    p = invoke("-C", color, "-V")
    assert p.returncode == 0 and "CMatrix version 2.0" in p.stdout.decode()


@pytest.mark.parametrize("color", ["", "gre", "reen", "7", "purple"],
                         ids=["empty", "prefix", "suffix", "numeric", "unrelated"])
def test_invalid_color_is_exact_and_stops_processing(color):
    p = invoke("-C", color, "-V")
    assert p.returncode == 0
    assert p.stdout == b""
    assert p.stderr.decode() == " Invalid color selection\n Valid colors are green, red, blue, white, yellow, cyan, magenta and black.\n"


def test_last_invalid_color_is_rejected():
    p = invoke("-C", "green", "-C", "purple", "-V")
    assert p.stderr.startswith(b" Invalid color selection\n") and p.stdout == b""


def start_pty(*args, term="xterm"):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
    env = os.environ.copy(); env["TERM"] = term
    proc = subprocess.Popen([EXE, *args], stdin=slave, stdout=slave, stderr=slave, env=env,
                            close_fds=True, start_new_session=True)
    os.close(slave)
    return proc, master


def read_for(fd, duration):
    data = bytearray(); end = time.monotonic() + duration
    while time.monotonic() < end:
        ready, _, _ = select.select([fd], [], [], max(0, end-time.monotonic()))
        if not ready: break
        try: chunk = os.read(fd, 65536)
        except OSError: break
        if not chunk: break
        data.extend(chunk)
    return bytes(data)


@pytest.mark.parametrize("args", [(), ("-a",), ("-u0",), ("-m",), ("-a", "-b", "-r", "-C", "ReD")],
                         ids=["default", "async", "fast", "lambda", "composed"])
def test_normal_modes_render_and_stop_on_sigint(args):
    proc, fd = start_pty(*args)
    try:
        first = read_for(fd, .35)
        assert b"\x1b[?1049h" in first and b"\x1b[?25l" in first
        assert len(first) > 100 and len(set(first)) > 8
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=2)
        tail = read_for(fd, .2)
        assert b"\x1b[?1049l" in first + tail
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        os.close(fd)


@pytest.mark.parametrize("args", [("-l",), ("-lba",), ("-ol",), ("-aobBnkcrmlx",)],
                         ids=["linux", "linux-group", "old-linux", "all-flags-linux"])
def test_linux_mode_conflict_path(args):
    proc, fd = start_pty(*args)
    try:
        proc.wait(timeout=3)
        output = read_for(fd, .1)
        assert proc.returncode == 0
        assert b' Unable to use both "setfont" and "consolechars".\r\n' in output or b' Unable to use both "setfont" and "consolechars".\n' in output
        assert b"\x1b[?1049h" in output and b"\x1b[?1049l" in output
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        os.close(fd)


def test_screensaver_exits_on_arbitrary_key_and_restores_terminal():
    proc, fd = start_pty("-s")
    try:
        initial = read_for(fd, .2)
        assert b"\x1b[?1049h" in initial
        os.write(fd, b"q")
        proc.wait(timeout=1)
        assert b"\x1b[?1049l" in read_for(fd, .15) + initial
    finally:
        if proc.poll() is None: proc.kill(); proc.wait()
        os.close(fd)


def test_unusable_terminal_fails_promptly_with_diagnostic():
    p = invoke(term="definitely-not-a-terminal")
    assert p.returncode != 0
    assert p.stderr.decode() == "Error opening terminal: definitely-not-a-terminal.\n"


def test_invalid_tty_path_does_not_crash():
    p = invoke("-t", "/definitely/missing/terminal", term="dumb")
    assert p.returncode != 0 or p.stderr

