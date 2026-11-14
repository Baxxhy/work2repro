import fcntl
import os
import pty
import select
import struct
import subprocess
import termios
import time

EXE = "/workspace/executable"

def session(document, keys=b"q", fullscreen=False):
    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 30, 100, 0, 0))
    args = [EXE] + (["--fullscreen"] if fullscreen else [])
    proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=slave, stderr=slave)
    os.close(slave)
    proc.stdin.write(document)
    proc.stdin.close()
    output = bytearray()
    deadline = time.monotonic() + 1.0
    while time.monotonic() < deadline:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try: output.extend(os.read(master, 65536))
            except OSError: break
        if proc.poll() is not None: break
    if proc.poll() is None:
        os.write(master, keys)
    end = time.monotonic() + 1
    while time.monotonic() < end and proc.poll() is None:
        ready, _, _ = select.select([master], [], [], .05)
        if ready:
            try: output.extend(os.read(master, 65536))
            except OSError: break
    if proc.poll() is None:
        proc.kill()
    try: proc.wait(timeout=1)
    except subprocess.TimeoutExpired: pass
    try:
        while True: output.extend(os.read(master, 65536))
    except OSError: pass
    os.close(master)
    return proc.returncode, bytes(output)

def visible(output):
    # Remove CSI and OSC terminal controls while preserving rendered text.
    import re
    return re.sub(rb"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))", b"", output).replace(b"\r", b"")

def test_valid_redirected_input_stays_interactive_until_quit():
    p = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.stdin.write(b"{}")
    p.stdin.close()
    time.sleep(.15)
    assert p.poll() is None
    p.kill(); p.wait()

def test_sorted_object_rendering_and_primitive_spelling():
    code, out = session(b'{"name":"John Doe","age":30,"active":true,"balance":null}')
    assert code == 0
    text = visible(out)
    for fragment in (b'"active": true', b'"age": 30', b'"balance": null', b'"name": "John Doe"'):
        assert fragment in text
    assert text.index(b'"active"') < text.index(b'"age"') < text.index(b'"balance"') < text.index(b'"name"')

def test_depth_expansion_and_collapsed_nested_array():
    code, out = session(b'{"count":42,"items":["apple","banana"],"user":{"name":"Alice","email":"a@b"}}')
    text = visible(out)
    assert code == 0 and b'"items": [...]' in text
    assert b'"user": {' in text and b'"email": "a@b"' in text

def test_root_collapse_and_reexpand_are_reversible():
    code, out = session(b'{"a":1}', b" q")
    assert code == 0
    assert b"{...}" in visible(out)

def test_nested_root_array_labels_table_capability():
    _, capable = session(b'[{"id":1},{"id":2}]')
    _, incapable = session(b'[{"id":1}]')
    assert b"(table view)" in visible(capable)
    assert b"(table view)" not in visible(incapable)

def test_fullscreen_uses_alternate_buffer_and_quits():
    code, out = session(b'{"x":1}', fullscreen=True)
    assert code == 0 and b"\x1b[?1049h" in out
    assert b"\x1b[?1049l" in out

