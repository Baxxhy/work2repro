import csv
import fcntl
import os
import pty
import re
import select
import struct
import subprocess
import termios
import time
from pathlib import Path

BIN = '/workspace/executable'
ANSI = re.compile(rb'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')

class Session:
    def __init__(self, args, rows=24, cols=80, config=None):
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        env = os.environ.copy()
        env.update(TERM='xterm-256color', BROWSER='/bin/false')
        env.pop('DISPLAY', None); env.pop('WAYLAND_DISPLAY', None)
        if config is not None: env['XDG_CONFIG_HOME'] = str(config)
        self.proc = subprocess.Popen([BIN, *args], stdin=slave, stdout=slave, stderr=slave, env=env, close_fds=True)
        os.close(slave); self.data = b''
        self.read_for(.6)

    def read_for(self, duration=.2):
        end = time.monotonic() + duration
        while time.monotonic() < end:
            ready, _, _ = select.select([self.master], [], [], max(0, end-time.monotonic()))
            if not ready: break
            try: part = os.read(self.master, 65536)
            except OSError: break
            if not part: break
            self.data += part
        return self.data

    def send(self, data):
        os.write(self.master, data)
        return self.read_for(.25)

    def finish(self, key=b'\x1b'):
        if self.proc.poll() is None: self.send(key)
        try: self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.proc.kill(); self.proc.wait()
        self.read_for(.1)
        os.close(self.master)
        return self.proc.returncode, self.data

    def plain(self):
        return ANSI.sub(b'', self.data).decode('utf-8', 'replace')

def test_ascii_prompt_starts_fullscreen_and_escape_restores():
    s = Session(['-p','hello world'])
    assert b'\x1b[?1049h' in s.data and b'hello world' in s.data and b'\x1b[?25l' in s.data
    code, data = s.finish()
    assert code == 0 and b'\x1b[?1049l' in data

def test_prompt_centering_line_break_processing_and_timer_layout():
    s = Session(['-p','hello world'])
    plain = s.plain()
    row = next(line for line in plain.splitlines() if 'hello world' in line)
    assert row.startswith(' '*35) and row.endswith(' '*34)
    s.finish()
    s = Session(['-p','top\nbottom'])
    assert 'topbottom' in s.plain() and 'top\nbottom' not in s.plain()
    s.finish()
    s = Session(['-p','timer','-s','4'])
    lines = s.plain().splitlines()
    assert '4.0' in lines[11] and 'timer' in lines[13]
    s.finish()

def test_typing_colors_expected_characters_and_completes_positionally():
    s = Session(['-p','dog'])
    s.send(b'd'); assert b'\x1b[38;5;2md' in s.data
    s.send(b'x'); assert b'\x1b[38;5;1mo' in s.data
    s.send(b'g')
    assert '0% acc' in s.plain() and '0 wpm' in s.plain()
    code, _ = s.finish()
    assert code == 0

def test_backspace_retypes_position_and_retry_keeps_prompt():
    s = Session(['-p','cat'])
    s.send(b'c'); s.send(b'a'); s.send(b'\x7f'); s.send(b'x')
    assert b'\x1b[38;5;1ma' in s.data
    s.send(b't')
    assert '67% acc' in s.plain()
    s.send(b'r'); s.read_for(.2)
    assert 'cat' in s.plain()
    s.finish()

def test_zero_length_states_show_results_and_log_only_calculated_nonempty_runs(tmp_path):
    s = Session(['-p',''], config=tmp_path)
    assert '0 wpm' in s.plain() and '(r)etry' in s.plain()
    s.finish()
    log = tmp_path/'thokr'/'log.csv'
    # Empty prompt may display results without requiring a timing/log calculation.
    if log.exists():
        assert len(list(csv.reader(log.open()))) <= 1

def test_completed_test_appends_csv_with_configured_word_count(tmp_path):
    s = Session(['-p','a','-w','7'], config=tmp_path)
    s.send(b'a')
    s.read_for(.1)
    s.finish()
    path = tmp_path/'thokr'/'log.csv'
    assert path.exists()
    rows = list(csv.reader(path.open(newline='')))
    assert rows[0] == ['date','num_words','num_secs','elapsed_secs','wpm','accuracy','std_dev']
    assert len(rows) == 2 and len(rows[1]) == 7
    assert rows[1][0] and rows[1][1] == '7' and rows[1][2] == ''
    assert re.fullmatch(r'\d+\.\d{2}', rows[1][3])
    assert rows[1][5] == '100' and re.fullmatch(r'\d+\.\d{2}', rows[1][6])

def test_non_ascii_prompt_has_documented_byte_boundary_panic():
    s = Session(['-p','界界界'])
    code, data = s.finish()
    assert code == 101
    plain = data.decode('utf-8', 'replace')
    assert "byte index 1 is not a char boundary" in plain and "inside '界' (bytes 0..3)" in plain

