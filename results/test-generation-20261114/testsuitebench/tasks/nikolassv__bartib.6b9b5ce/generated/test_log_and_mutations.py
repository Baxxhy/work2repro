from datetime import datetime

from conftest import text


def test_start_stops_existing_runs_in_order_and_serializes_escapes(invoke):
    p, log = invoke('start','-p','P|\\','-d','D|\\','-t','10:00', content='2024-01-01 09:00 | P1 | old\n2024-01-01 09:30 | P2 | older\n')
    out = text(p.stdout)
    assert p.returncode == 0 and out.index('old') < out.index('older') < out.index('Started activity')
    data = log.read_text()
    assert 'P\\|\\\\' in data and 'D\\|\\\\' in data
    assert data.count(' - 202') == 2 and data.endswith('10:00 | P\\|\\\\ | D\\|\\\\\n')


def test_start_time_parser_normalizes_and_invalid_time_falls_back(invoke):
    p, log = invoke('start','-p','P','-d','D','-t','10:5')
    assert p.returncode == 0 and '| P | D\n' in log.read_text() and '10:05' in text(p.stdout)
    p, _ = invoke('start','-p','Q','-d','E','-t','1:2x')
    assert p.returncode == 0 and 'trailing input' in text(p.stdout)


def test_stop_completes_all_running_and_repeat_is_noop(invoke):
    src='2024-01-01 09:00 | P | A\n2024-01-01 09:30 | Q | B\n2020-01-01 00:00 - 2020-01-01 01:00 | X | done\n'
    p, log = invoke('stop','-t','10:00',content=src)
    assert p.returncode == 0 and text(p.stdout).count('Stopped activity:') == 2
    saved=log.read_bytes()
    p, _ = invoke('stop','-t','11:00')
    assert p.returncode == 0 and p.stdout == b'' and log.read_bytes() == saved


def test_stop_allows_negative_duration(invoke):
    today = datetime.now().astimezone().strftime('%Y-%m-%d')
    p, log = invoke('stop','-t','09:00',content=f'{today} 10:00 | P | A\n')
    assert p.returncode == 0 and '(<1m)' in text(p.stdout)
    assert f'{today} 10:00 - ' in log.read_text()


def test_cancel_removes_running_and_canonicalizes_survivors(invoke):
    src='2020-01-01 00:00 - 2020-01-01 00:01 | P | done  \r\n2024-01-01 10:00 | Q | running\n'
    p, log=invoke('cancel',content=src)
    assert p.returncode == 0 and 'Canceled activity:' in text(p.stdout)
    assert log.read_bytes() == b'2020-01-01 00:00 - 2020-01-01 00:01 | P | done\n'


def test_cancel_no_runs_still_canonicalizes(invoke):
    p, log=invoke('cancel',content='2020-01-01 00:00 - 2020-01-01 00:01 | P | done  \r\n')
    assert p.returncode == 0 and p.stdout == b''
    assert log.read_bytes().endswith(b'| done\n')


def test_change_updates_every_run_and_empty_values(invoke):
    src='2024-01-01 08:00 | P | A\n2024-01-01 09:00 | Q | B\n2020-01-01 00:00 - 2020-01-01 01:00 | X | done  \n'
    p, log=invoke('change','-p','','-d','','-t','9:00',content=src)
    assert p.returncode == 0 and text(p.stdout).count('Changed activity:') == 2
    lines=log.read_text().splitlines()
    assert lines[0].endswith(' |  | ') and lines[1].endswith(' |  | ')
    assert lines[2].endswith('| done')


def test_change_without_runs_rewrites_canonical_log(invoke):
    p, log=invoke('change',content='2020-01-01 00:00 - 2020-01-01 00:01 | P | D  \n')
    assert p.returncode == 0 and p.stdout == b'' and log.read_bytes().endswith(b'| D\n')


def test_valid_read_lines_escape_fields_and_seconds_warning(invoke):
    p, _=invoke('list','--no_grouping',content='2024-01-01 09:00:30 - 2024-01-01 09:01:00 | test project\\| 1 | test\\\\description\r\n')
    assert p.returncode == 0 and '09:01' in text(p.stdout) and 'test project| 1' in text(p.stdout)
    assert text(p.stderr).count('WARNING: Bartib log encountered') == 2


def test_normal_readers_warn_bad_and_blank_lines_but_continue(invoke):
    p, _=invoke('list',content='bad\n   \n2024-01-01 09:00 - 2024-01-01 09:01 | P | ok\n')
    out=text(p.stdout)
    assert p.returncode == 0 and 'Ignoring line 1' in out and 'Ignoring line 2' in out and 'ok' in out


def test_check_classifies_each_bad_line_and_accepts_empty_description(invoke):
    src='bad\n2024-13-40 09:00 | P | bad date\n2024-01-01 09:00 | P\n\n'
    p, _=invoke('check',content=src)
    out=text(p.stdout)
    assert p.returncode == 0 and 'Found 3 line(s)' in out
    assert 'could not parse activity (Line: 1)' in out
    assert 'could not parse date or time of activity (Line: 2)' in out
    assert 'could not parse activity (Line: 4)' in out


def test_check_empty_file_and_valid_leap_second(invoke):
    p, _=invoke('check',content='')
    assert p.returncode == 0 and text(p.stdout) == 'All lines in the file have been successfully parsed as activities.'
    p, _=invoke('check',content='2024-01-01 09:00:60 | P | leap\n')
    assert p.returncode == 0 and 'successfully parsed' in text(p.stdout) and 'WARNING:' in text(p.stderr)
