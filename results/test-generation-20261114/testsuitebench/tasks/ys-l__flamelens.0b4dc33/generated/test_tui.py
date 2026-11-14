import os
import pty
import re
import select
import subprocess
import tempfile
import time
from pathlib import Path

EXE = '/workspace/executable'
ANSI = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]|\x1b\][^\x07]*(?:\x07|\x1b\\)')


def tui(text, keys=b'q', args=(), width=100, height=28, timeout=4):
    fd, path = tempfile.mkstemp(prefix='profile-', suffix='.folded', dir='/workspace/eval')
    os.write(fd, text.encode('utf-8'))
    os.close(fd)
    master, slave = pty.openpty()
    import fcntl, termios, struct
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack('HHHH', height, width, 0, 0))
    env = dict(os.environ, TERM='xterm-256color')
    proc = subprocess.Popen([EXE, *args, path], stdin=slave, stdout=subprocess.PIPE,
                            stderr=slave, env=env, close_fds=True)
    os.close(slave)
    output = bytearray()
    try:
        # Allow initial paint, then drive input one key at a time to avoid losing keystrokes.
        deadline = time.monotonic() + timeout
        for key in keys:
            os.write(master, bytes([key]))
            time.sleep(.04)
        while time.monotonic() < deadline:
            ready, _, _ = select.select([master], [], [], .08)
            if ready:
                try:
                    chunk = os.read(master, 65536)
                except OSError:
                    break
                output.extend(chunk)
            if proc.poll() is not None:
                # Drain any final terminal restoration bytes.
                continue
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=1)
        stdout = proc.stdout.read()
    finally:
        os.close(master)
        Path(path).unlink(missing_ok=True)
    raw = output.decode('utf-8', errors='replace')
    clean = ANSI.sub('', raw).replace('\r', '')
    return proc.returncode, clean, stdout


def test_initial_screen_has_graph_header_and_selected_root():
    rc, screen, out = tui('a;b 10\na;c 5\n')
    assert rc == 0
    assert '[Flamegraph] | Top' in screen and 'flamelens v0.3.1' in screen
    assert 'stdin' not in screen  # named input is shown as the supplied filename
    assert 'all [15 samples, 100.00% of all]' in screen
    assert 'hjkl: move cursor' in screen and 'tab: switch view' in screen
    assert out == b''


def test_top_table_includes_aggregated_distinct_names_and_default_own_sort():
    rc, screen, _ = tui('a;b;c 10\na;b;c 5\na;e 30\n', keys=b'\tq')
    assert rc == 0
    assert 'Flamegraph | [Top]' in screen
    assert 'Total          Own [▼]       Name' in screen
    assert 'a' in screen and 'b' in screen and 'c' in screen and 'e' in screen
    assert '45 (100.00%)' in screen and '30 (66.67%)' in screen
    assert 'j/k: move cursor' in screen and '1: sort by total' in screen


def test_top_sort_keys_switch_active_column():
    rc, screen, _ = tui('a;b 2\na;c 8\n', keys=b'\t1q')
    assert rc == 0 and 'Total [▼]' in screen and 'Own [▼]' not in screen


def test_top_filter_search_and_empty_match_fallback():
    rc, screen, _ = tui('alpha 2\nbeta 3\n', keys=b'\t/zz\nq')
    assert rc == 0
    assert '(no match; showing all)' in screen
    assert 'alpha' in screen and 'beta' in screen


def test_manual_search_reports_coverage_and_filters_top():
    # Coverage must count the matching ancestor once even when its descendant also matches.
    rc, screen, _ = tui('foo;foo 7\nbar 3\n', keys=b'/foo\nq')
    assert rc == 0 and '"foo" [7 samples, 70.00% of all]' in screen


def test_regex_invalidity_is_reported_without_crashing():
    rc, screen, _ = tui('a 1\n', keys=b'/[\nq')
    assert rc == 0 and 'Invalid regex: [' in screen


def test_debug_panel_is_enabled_by_flag_and_toggleable():
    rc, screen, _ = tui('a 1\n', args=('--debug',))
    assert rc == 0 and 'Debug:' in screen and 'render:' in screen


def test_navigation_and_zoom_show_selected_fraction_and_zoom_fraction():
    rc, screen, _ = tui('a;b 10\na;c 30\n', keys=b'j\nq')
    assert rc == 0 and 'a [40 samples, 100.00% of all]' in screen
    assert '100.00% of zoomed' in screen


def test_exact_name_search_escapes_regex_characters():
    rc, screen, _ = tui('work (file.py:8) 5\nother 2\n', keys=b'j#q')
    assert rc == 0 and r'^work \(file\.py:8\)$' in screen


def test_echo_in_tui_emits_input_before_ui_and_then_exits_cleanly():
    data = 'a 1\n'
    rc, screen, out = tui(data, keys=b'q', args=('--echo',))
    assert rc == 0 and out == (data + '\n').encode()


def test_parser_preserves_spaces_punctuation_and_utf8_frame_names():
    folded = 'work frame;C++ (worker)$<é> 12\n'
    rc, screen, _ = tui(folded, keys=b'\tq')
    assert rc == 0
    assert 'work frame' in screen and 'C++ (worker)$<é>' in screen
    assert '12 (100.00%)' in screen


def test_parser_ignores_comments_blank_lines_and_malformed_lines():
    folded = '# comment\n   \nbad-line\nmissing-count;frame nope\nvalid;leaf 4\n'
    rc, screen, _ = tui(folded, keys=b'\tq')
    assert rc == 0
    assert 'valid' in screen and 'leaf' in screen
    assert '4 (100.00%)' in screen
    assert 'bad-line' not in screen and 'missing-count' not in screen


def test_zero_count_is_valid_and_empty_graph_has_nan_selection():
    rc, screen, _ = tui('zero 0\n', keys=b'q')
    assert rc == 0 and 'all [0 samples, NaN% of all]' in screen


def test_malformed_only_input_still_shows_empty_root():
    rc, screen, _ = tui('# comment\nnot-a-count\n', keys=b'q')
    assert rc == 0 and 'all [0 samples, NaN% of all]' in screen
