import csv
import gzip
import json
import os
import re
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def entry(remote='192.0.2.1', stamp='22/Jan/2021:01:47:05 +0000', request='GET /test HTTP/1.1', status='200', size='100', referer='-', ua='Agent'):
    return f'{remote} - - [{stamp}] "{request}" {status} {size} "{referer}" "{ua}"'


@pytest.fixture
def log(tmp_path):
    def write(text, name='access.log'):
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
        return p
    return write


def run(*args, env=None, cwd=None, timeout=8):
    e = os.environ.copy()
    e.update({'NO_COLOR': '1', 'TERM': 'dumb'})
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def json_rows(*args, **kw):
    p = run('--silent-load', '--output', 'json', *args, **kw)
    assert p.returncode == 0, p.stderr.decode(errors='replace')
    return json.loads(p.stdout)


def test_version_help_and_help_precedence():
    p = run('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'rhit 2.0.4\n', b'')
    p = run('--output', 'json', '--color', 'no', '--help')
    assert p.returncode == 0 and p.stderr == b'' and p.stdout.endswith(b'\n\n')
    assert b'Rhit analyzes your nginx logs.' in p.stdout
    assert b'--method' in p.stdout
    assert p.stdout == run('--help').stdout


def test_help_and_version_parse_contract():
    p = run('-h')
    assert p.returncode == 2 and not p.stdout
    assert b"unexpected argument '-h'" in p.stderr and b'Usage:' in p.stderr
    p = run('--quux')
    assert p.returncode == 2 and not p.stdout
    assert b"error: unexpected argument '--quux' found" in p.stderr
    assert b"use '-- --quux'" in p.stderr and b'Usage: executable [OPTIONS] [FILES]...' in p.stderr
    p = run('--wat')
    assert p.returncode == 2
    assert p.stderr.decode() == "error: unexpected argument '--wat' found\n\n  tip: a similar argument exists: '--path'\n\nUsage: executable --path <PATH> [FILES]...\n"


def test_option_forms_clusters_and_validation(log):
    f = log(entry())
    assert json_rows('-cl', '1', '-o=json', f)[0]['path'] == '/test'
    p = run('--length=-1', f)
    assert p.returncode == 2 and b"'--length <LENGTH>'" in p.stderr and b'invalid digit found in string' in p.stderr
    p = run('--length', '-1', f)
    assert p.returncode == 2 and b"unexpected argument '-1' found" in p.stderr
    p = run('--output', 'invalid', f)
    assert p.returncode == 2 and p.stderr == b'error: invalid value \'invalid\' for \'--output <OUTPUT>\': unrecognized output "invalid"\n'
    p = run('--fields', 'xyz', f)
    assert p.returncode == 2 and b"unrecognized field start 'x'" in p.stderr
    for flag, value in [('--key', 'hits'), ('--method', 'GET')]:
        p = run(flag, value, flag, value, f)
        assert p.returncode == 2 and b'cannot be used multiple times' in p.stderr


def test_paths_recursion_name_filter_explicit_and_repeat(tmp_path):
    root = tmp_path / 'logs'; root.mkdir()
    good = root / 'access.log.1'; good.write_text(entry(request='GET /one HTTP/1.1')+'\n')
    ignored = root / 'other.txt'; ignored.write_text(entry(request='GET /no HTTP/1.1')+'\n')
    p = json_rows(root)
    assert [x['path'] for x in p] == ['/one']
    assert [x['path'] for x in json_rows('--no-name-check', root)] == ['/one', '/no']
    assert [x['path'] for x in json_rows(good, good)] == ['/one', '/one']


def test_missing_file_and_no_log_errors(tmp_path):
    missing = tmp_path / 'absent'
    p = run(missing)
    assert p.returncode == 1 and p.stderr == f'Error: PathNotFound("{missing}")\n'.encode()
    empty = tmp_path / 'access.log'; empty.write_text('not a log\n')
    p = run('--silent-load', empty)
    assert p.returncode == 1 and p.stderr == b'Error: NoLogFileFound\n'


def test_gzip_raw_utf8_and_gzip_failures(tmp_path):
    raw = entry(request='GET /x?q=1 HTTP/1.1') + '\n'
    gz = tmp_path / 'access.log.gz'
    gz.write_bytes(gzip.compress(raw.encode()))
    p = run('--silent-load', '--output', 'raw', gz)
    assert p.returncode == 0 and p.stdout == raw.encode()
    bad = tmp_path / 'bad.log'; bad.write_bytes(b'\xff')
    p = run('--silent-load', bad)
    assert p.returncode == 1 and b'InvalidData' in p.stderr
    gzbad = tmp_path / 'bad.gz'; gzbad.write_bytes(b'not gzip')
    p = run('--silent-load', gzbad)
    assert p.returncode == 1 and b'UnexpectedEof' in p.stderr


def test_detection_first_three_lines_and_skip_bad_lines(tmp_path):
    f = tmp_path / 'access.log'
    valid = entry(request='GET /valid HTTP/1.1')
    f.write_text('rotate\nmalformed\n'+valid+'\nbad\n'+entry(request='GET /last HTTP/1.1')+'\n')
    assert [r['path'] for r in json_rows(f)] == ['/valid', '/last']
    f2 = tmp_path / 'access.log.1'; f2.write_text('x\ny\nz\n'+valid+'\n')
    p = run('--silent-load', f2)
    assert p.returncode == 1 and p.stderr == b'Error: NoLogFileFound\n'


def test_parsing_normalization_order_and_csv_json_shapes(log):
    f = log('\n'.join([
        entry(remote='host-token', stamp='2021-01-22T10:00:00.000Z', request='GET /a?x=1 HTTP/1.1', referer='a,b'),
        entry(request='odd target extra', status='201', size='0', referer='-'),
        entry(request='broken'),
    ])+'\n')
    rows = json_rows(f)
    assert [(r['remote_addr'], r['date'], r['time'], r['path'], r['referer']) for r in rows] == [
        ('host-token', '2021/01/22', '10:00:00', '/a', 'a,b'),
        ('192.0.2.1', '2021/01/22', '01:47:05', 'target', '-'),
        ('192.0.2.1', '2021/01/22', '01:47:05', 'broken', '-')]
    assert list(rows[0]) == ['date','time','remote_addr','method','path','status','bytes_sent','referer']
    assert rows[1]['method'] == 'other' and rows[2]['method'] == 'none'
    p = run('--silent-load', '--output', 'csv', f)
    assert p.returncode == 0
    parsed = list(csv.reader(p.stdout.decode().splitlines()))
    assert parsed[0] == ['date','time','remote address','method','path','status','bytes sent','referer']
    assert len(parsed) == 4 and parsed[1][4] == '/a'


def test_special_text_unicode_percent_and_raw_preservation(log):
    physical = entry(request=r'GET /literal\x00tail?q=yes HTTP/1.1', referer='https://café.example.org/日本語, x')+'\n'
    f = log(physical)
    rows = json_rows(f)
    assert rows[0]['path'] == r'/literal\x00tail'
    assert rows[0]['referer'] == 'https://café.example.org/日本語, x'
    assert r'"path": "/literal\x00tail"' in run('--silent-load','-o','json',f).stdout.decode()
    assert run('--silent-load','-o','raw',f).stdout == physical.encode()


def test_all_filter_kinds_and_boolean_regex(log):
    f = log('\n'.join([
        entry(remote='10.0.0.1', request='GET /api/page HTTP/1.1', referer='https://x'),
        entry(remote='10.0.0.2', request='POST /api HTTP/1.1', status='404', referer='-'),
        entry(remote='2001:db8::1', request='GET /blog HTTP/1.1', status='302', referer='https://blog'),
    ])+'\n')
    assert [r['path'] for r in json_rows('--ip','10.0','--path','api','--method','GET',f)] == ['/api/page']
    assert [r['path'] for r in json_rows('--status','4xx,!404',f)] == []
    assert [r['path'] for r in json_rows('--status','2xx,3xx',f)] == ['/api/page','/blog']
    assert [r['path'] for r in json_rows('--referer','blog',f)] == ['/blog']
    assert [r['path'] for r in json_rows('--method','!other',f)] == ['/api/page','/api','/blog']
    assert [r['path'] for r in json_rows('--path','api, page',f)] == ['/api/page']
    assert [r['path'] for r in json_rows('--path','api | blog & page',f)] == ['/api/page']


def test_expression_errors_and_empty_expression_side_effect(log):
    f = log('\n'.join(entry(request=f'GET /p{i} HTTP/1.1') for i in range(2))+'\n')
    p = run('--silent-load','-o','json','--path','',f)
    assert p.returncode == 0 and p.stdout.count(b'unexpected lack of expr result') == 2 and p.stdout.endswith(b'[\n]\n')
    p = run('--silent-load','--path','a )',f)
    assert p.returncode == 1 and p.stdout.startswith(b'expr: BeTree {')
    assert b'unexpected closing parenthesis' in p.stderr
    p = run('--silent-load','--path','[',f)
    assert p.returncode == 1 and b'StrFilter(InvalidRegex(Syntax(' in p.stderr and b'unclosed character class' in p.stderr


def test_date_time_filters(log):
    f = log('\n'.join([
        entry(stamp='31/Dec/2020:23:59:59 +0000', request='GET /a HTTP/1.1'),
        entry(stamp='01/Jan/2021:00:00:00 +0000', request='GET /b HTTP/1.1'),
        entry(stamp='02/Jan/2021:12:30:00 +0000', request='GET /c HTTP/1.1'),
    ])+'\n')
    assert [r['path'] for r in json_rows('--date','2021/01/01-2021/01/02',f)] == ['/b','/c']
    assert [r['path'] for r in json_rows('--date','>2021/01/01',f)] == ['/c']
    assert [r['path'] for r in json_rows('--time','22:00-04:00',f)] == ['/a','/b']
    assert [r['path'] for r in json_rows('--time','>12:00',f)] == ['/c']
    for value, expected in [('11:30', b'Error: TimeFilter(InvalidFormat)'), ('>25:00', b'Error: TimeFilter(TimeParse(InvalidHour(25)))')]:
        p = run('--silent-load','--time',value,f)
        assert p.returncode == 1 and expected in p.stderr


def test_tables_defaults_fields_and_resource_exclusion(log):
    f = log('\n'.join(entry(request=f'GET /{path} HTTP/1.1') for path in ['page','img.png','map.map'])+'\n')
    p = run('--silent-load','--color','no',f)
    out = p.stdout.decode()
    assert '3 hits and 300 from 2021/01/22 to 2021/01/22' in out
    assert '2 paths (excluding resources like images, css, etc.).' in out
    assert '/page' in out and '/map.map' in out and 'img.png' not in out
    all_out = run('--silent-load','--color','no','--all','--fields','path,method',f).stdout.decode()
    assert '3 paths.' in all_out and all_out.index('│path') < all_out.index('│method')
    empty_fields = run('--silent-load','--fields=',f).stdout.decode()
    assert '┌' not in empty_fields and empty_fields.endswith('\n')


def test_tables_color_and_filter_summary(log):
    f = log('\n'.join([entry(remote='1.1.1.1',request='GET /a HTTP/1.1'), entry(remote='2.2.2.2',request='GET /b HTTP/1.1')])+'\n')
    plain = run('--silent-load','--color','no',f).stdout
    forced = run('--silent-load','--color','yes',f,env={'NO_COLOR':'1'}).stdout
    assert b'\x1b[' not in plain and b'\x1b[' in forced
    strip_sgr = lambda value: re.sub(rb'\x1b\[[0-9;]*m', b'', value)
    assert strip_sgr(forced) == plain
    p = run('--silent-load','--color','no','--ip','1.1','--referer','absent',f).stdout.decode()
    assert 'Filtering by remote address on pattern 1.1' in p
    assert 'Filtering by referer on pattern absent removed 50.00% of total lines' in p


def test_loading_progress_and_silent_load(tmp_path):
    f = tmp_path / 'access.log'; f.write_text(entry()+'\n')
    noisy = run(f); quiet = run('--silent-load',f)
    assert noisy.returncode == quiet.returncode == 0
    assert b'\x1b[2K' in noisy.stderr and b'read' in noisy.stderr and b"I've read 1 file" in noisy.stderr
    assert quiet.stderr == b'' and quiet.stdout == noisy.stdout


def test_date_runs_and_changes_table(log):
    lines=[]
    for day, path, n in [(1,'/x',2),(2,'/x',2),(1,'/x',2),(3,'/x',2)]:
        lines += [entry(stamp=f'{day:02d}/Jan/2024:01:00:00 +0000',request=f'GET {path} HTTP/1.1') for _ in range(n)]
    f=log('\n'.join(lines)+'\n')
    out=run('--silent-load','--color','no','--changes',f).stdout.decode()
    assert '│ # │path' in out and 'days' in out and '│trend│' in out


def test_option_terminator_and_explicit_file_bypasses_filtering(tmp_path):
    f=tmp_path/'custom.log'; f.write_text(entry()+'\n')
    assert len(json_rows(f)) == 1
    # An option-looking filename after -- remains a positional path.
    dash=tmp_path/'-file'; dash.write_text(entry(request='GET /dash HTTP/1.1')+'\n')
    assert json_rows('--',dash)[0]['path'] == '/dash'


def test_method_categories_status_language_and_absent_values(log):
    f=log('\n'.join([entry(request='get /a HTTP/1.1',status='201'),entry(request='GET /b HTTP/1.1',status='404'),entry(request='BROKEN',status='999')])+'\n')
    assert [r['method'] for r in json_rows('--method','other',f)] == ['other','other']
    assert [r['method'] for r in json_rows('--method','none',f)] == ['none']
    assert [r['status'] for r in json_rows('--status','4xx,!404',f)] == []
    assert [r['status'] for r in json_rows('--status','999',f)] == ['999']
    p=run('--silent-load','--status','x',f)
    assert p.returncode==1 and b'StatusFilter(ParseInt(ParseIntError { kind: InvalidDigit }))' in p.stderr
