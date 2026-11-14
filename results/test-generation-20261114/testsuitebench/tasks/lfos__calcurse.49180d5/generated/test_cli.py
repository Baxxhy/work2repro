import hashlib
import os
import pathlib
import re
import subprocess

import pytest

EXE = pathlib.Path('/workspace/executable')

@pytest.fixture
def box(tmp_path):
    home = tmp_path / 'home'; home.mkdir()
    data = tmp_path / 'data'
    env = os.environ.copy()
    env.update(HOME=str(home), XDG_DATA_HOME=str(tmp_path/'xd'), XDG_CONFIG_HOME=str(tmp_path/'xc'), LC_ALL='C')
    def run(*args, timeout=8):
        return subprocess.run([str(EXE), *map(str,args)], cwd='/workspace/eval', env=env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    def setup(apts='', todo='', extra=None):
        data.mkdir(exist_ok=True)
        (data/'apts').write_text(apts, encoding='utf-8')
        (data/'todo').write_text(todo, encoding='utf-8')
        (data/'notes').mkdir(exist_ok=True)
        if extra: extra(data)
    def invoke(*args, **kw):
        return run(*args, '-D', data, **kw)
    return tmp_path, data, run, invoke, setup

HELP = '''Usage:
calcurse [-D <directory>] [-C <directory>] [-c <calendar file>]
calcurse -Q [--from <date>] [--to <date>] [--days <number>]
calcurse -a | -d <date> | -d <number> | -n | -r[<number>] | -s[<date>] | -t[<number>]
calcurse -h | -v | --status | -G | -P | -g | -i <file> | -x[<format>] | --daemon

Operations in command line mode:
  -Q, --query   Print items in a given query range
  -G, --grep    Grep items from the data files
  -P, --purge   Read items and write them back
Query short forms:
-a, -d <date>|<number>, -n, -r[<number>], -s[<date>], -t<number>

Note that filter, format and day-range options affect input or output:
  --filter-*              Filter items loaded by -Q, -G, -P and -x
  --format-*              Rewrite output from -Q, -G and --dump-imported
  --from <date>           Limit day range of -Q.
  --to <date>             Limit day range of -Q.
  --days <number>         Limit day range of -Q.

  --limit, -l <number>    Limit number of query results
  --search, -S <regexp>   Match regular expression in queries
Consult the man page for details.

Miscellaneous:
  -c, --calendar <file>   The calendar data file to use
  -C, --confdir <dir>     The configuration directory to use
  --daemon                Run notification daemon in the background
  -D, --datadir <dir>     The data directory to use
  -g, --gc                Run the garbage collector
  -h, --help              Show this help text
  -i, --import <file>     Import iCal data from file
  -q, --quiet             Suppress import/export result message
  --read-only             Do not save configuration or data files
  --status                Display status of running instances
  -v, --version           Show version information
  -x, --export[<format>]  Export to stdout in ical (default) or pcal format

For more information, type '?' from within calcurse, or read the manpage.
Submit feature requests and suggestions to <misc@calcurse.org>.
Submit bug reports to <bugs@calcurse.org>.
'''


def test_help_exact_and_positionals_ignored(box):
    _,_,run,_,_ = box
    for args in [('-h',),('--help',),('odd','--help'),('--help','--','odd')]:
        p=run(*args); assert p.returncode == 0 and p.stdout.decode() == HELP and p.stderr == b''

def test_version_exact(box):
    _,_,run,_,_ = box
    expected='calcurse 4.8.2 -- text-based organizer\n\nCopyright (c) 2004-2023 calcurse Development Team.\nThis is free software; see the source for copying conditions.\n'
    for flag in ('-v','--version'):
        p=run(flag); assert p.returncode == 0 and p.stdout.decode() == expected and not p.stderr

def test_cli_validation(box):
    _,_,run,_,_ = box
    for args, phrase in [(('--bad',),'unrecognized option'),(('foo',),'invalid argument combination'),(('-Q','-G'),'invalid argument combination'),(('-Q','--days','0'),'invalid range: 0'),(('-Q','--to','01/02/2020','--days','2'),'cannot specify a range and an end date'),(('-Q','--from','01/03/2020','--to','01/02/2020'),'end date cannot come before start date'),(('-xinvalid',),'invalid export format: invalid'),(('-G','--filter-type','alien'),'invalid filter mask'),(('-G','--filter-priority','99'),'invalid priority: 99'),(('-Q','--filter-pattern','[invalid'),'could not compile regular expression')]:
        p=run(*args); assert p.returncode != 0 and phrase.encode() in p.stderr

def test_help_unknown_option_still_error(box):
    _,_,run,_,_ = box
    p=run('--bad','--help'); assert p.returncode != 0 and b'unrecognized option' in p.stderr

def test_paths_create_and_readonly_missing(box):
    tmp,data,run,_,_ = box
    p=run('-a','-D',data); assert p.returncode == 0 and (data/'apts').exists() and (data/'conf').exists()
    missing=tmp/'missing'; p=run('--read-only','-D',missing,'-a')
    assert p.returncode != 0 and not p.stdout and b'failed to open appointment file' in p.stderr and not missing.exists()

def test_readonly_writable_storage_separation(box):
    tmp,_,run,_,_ = box; d=tmp/'d'; c=tmp/'c'
    p=run('-t','-D',d,'-C',c); assert p.returncode == 0
    assert (d/'todo').exists() and (d/'conf').exists() and (c/'conf').exists()

def test_native_grep_normalization_order_and_hash(box):
    _,d,_,invoke,setup=box
    apts='''01/02/2024 @ 10:00 -> 01/02/2024 @ 11:00 |Meet
01/02/2024 [8] Zulu
01/02/2024 [2] Alpha
01/02/2024 @ 09:00 -> 01/02/2024 @ 10:00 !Alert
'''
    setup(apts,'[0] Later\n[-5] Done\n[1] First\n')
    p=invoke('-G'); assert p.returncode == 0
    lines=p.stdout.decode().splitlines()
    assert lines[:3] == ['[1] First','[0] Later','[-5] Done']
    assert lines[3].startswith('01/02/2024 @ 09:00') and lines[4].startswith('01/02/2024 @ 10:00')
    assert '|Meet' in lines[4] and '!Alert' in lines[3]
    raw=invoke('-G','--format-todo','%(raw)'); assert raw.stdout.startswith(b'[1] First\n')
    digest=hashlib.sha1(b'[1] First').hexdigest()
    h=invoke('-G','--format-todo','%(hash)'); assert digest.encode() in h.stdout

def test_native_todo_open_completed_order_and_filters(box):
    _,_,_,invoke,setup=box; setup('', '[0] Z\n[2] Bee\n[2] Able\n[-5] Done\n')
    p=invoke('-t'); assert p.stdout.decode() == 'to do:\n2. Able\n2. Bee\n0. Z\n'
    p=invoke('-t0'); assert p.stdout.decode() == 'completed tasks:\n5. Done\n'
    p=invoke('-t2'); assert p.stdout.decode() == 'to do:\n2. Able\n2. Bee\n'
    p=invoke('-t','-l','0'); assert p.returncode == 0 and p.stdout == b''

def test_query_dates_filter_and_todo_opt_in(box):
    _,_,_,invoke,setup=box
    setup('02/29/2024 [1] Leap\n02/29/2024 @ 10:00 -> 02/29/2024 @ 11:00|Timed\n','[1] Todo\n')
    p=invoke('-Q','--from','2/29/2024','--to','2/29/2024'); assert p.returncode == 0 and b'Leap' in p.stdout and b'Timed' in p.stdout and b'Todo' not in p.stdout
    p=invoke('-Q','--from','2/29/2024','--days','1','--filter-type','todo'); assert b'Todo' in p.stdout
    p=invoke('-Q','--from','2/29/2024','--filter-type','todo,cal'); assert b'Todo' in p.stdout
    p=invoke('-G','--limit','0'); assert b'Leap' in p.stdout and b'Todo' in p.stdout

def test_query_ranges_and_output_heading_format(box):
    _,_,_,invoke,setup=box
    setup('01/01/2100 [1] Y2100\n12/31/9999 [2] Y9999\n')
    p=invoke('-Q','--from','01/01/2100','--output-datefmt','%Y/%m/%d'); assert p.stdout.startswith(b'2100/01/01:')
    p=invoke('-Q','--from','12/31/9999'); assert p.stdout.startswith(b'12/31/99:')

def test_input_date_formats_and_option_order(box):
    tmp,_,run,_,_=box
    data=tmp/'date-data'
    p=run('--input-datefmt','2','-d','29/2/2020','-D',data); assert p.returncode == 0
    p=run('-d','29/2/2020','--input-datefmt','2','-D',data); assert p.returncode != 0 and b'invalid date' in p.stderr

def test_output_grouping_spans_and_sorting(box):
    _,_,_,invoke,setup=box
    setup('''02/23/2013 [1] Zebra
02/23/2013 [2] Apple
02/23/2013 @ 10:00 -> 02/24/2013 @ 12:00|Long
02/24/2013 @ 23:00 -> 02/25/2013 @ 00:00|Midnight end
''')
    p=invoke('-Q','--from','02/23/2013','--to','02/25/2013'); out=p.stdout.decode()
    assert out.index('* Apple') < out.index('* Zebra')
    assert '10:00 -> ..:..' in out and '..:.. -> 12:00' in out
    assert '02/25/13:' not in out

def test_query_short_format_search(box):
    _,_,_,invoke,setup=box; setup('01/02/2024 [1] Alpha\n01/02/2024 [2] Beta\n')
    p=invoke('-d','01/02/2024','-S','^Al'); assert b'Alpha' in p.stdout and b'Beta' not in p.stdout
    p=invoke('-Q','--day','01/02/2024','--format-event','X:%m'); assert p.stdout.endswith(b'X:AlphaX:Beta') and b'01/02/24:' in p.stdout

def test_malformed_native_diagnostics(box):
    _,_,_,invoke,setup=box
    cases=[('not an item\n','syntax error in the item date'),('01/01/2020 @ 25:00 -> 01/01/2020 @ 26:00|bad\n','illegal date in appointment'),('01/01/2020 [0] bad\n','syntax error in item identifier')]
    for content, phrase in cases:
        setup(content,''); p=invoke('-G'); assert p.returncode != 0 and phrase.encode() in p.stderr
    setup('','garbage\n'); p=invoke('-t'); assert p.returncode != 0 and b'syntax error' in p.stderr

def test_zero_recurrence_signal(box):
    _,_,_,invoke,setup=box; setup('01/01/2020 [1] {0D} bad\n','')
    p=invoke('-G'); assert p.returncode == -signal.SIGFPE and not p.stdout and not p.stderr

def test_purge_filters_and_readonly(box):
    _,d,_,invoke,setup=box; setup('01/01/2024 [1] Event\n01/01/2024 @ 10:00 -> 01/01/2024 @ 11:00|Meet\n','[1] Task\n')
    p=invoke('-P','--filter-type','event'); assert p.returncode == 0 and not p.stdout
    assert (d/'apts').read_text().find('Event') < 0 and 'Meet' in (d/'apts').read_text() and 'Task' in (d/'todo').read_text()
    invoke('--read-only','-P'); assert 'Meet' in (d/'apts').read_text()

def test_gc_removes_only_unreferenced_notes(box):
    _,d,_,invoke,setup=box
    def notes(data):
        (data/'notes'/'keep').write_text('note'); (data/'notes'/'orphan').write_text('unused')
    setup('01/01/2024 [1] >keep Event\n','',notes)
    p=invoke('-g'); assert p.returncode == 0 and not p.stdout and (d/'notes'/'keep').exists() and not (d/'notes'/'orphan').exists()

def test_export_empty_and_pcal(box):
    _,_,_,invoke,setup=box; setup('','')
    p=invoke('-x'); assert p.stdout.decode() == 'BEGIN:VCALENDAR\nVERSION:2.0\nPRODID:-//calcurse//NONSGML v4.8.2//EN\nEND:VCALENDAR\n'
    p=invoke('-xpcal'); assert p.returncode == 0 and p.stdout.startswith(b'# calcurse pcal export') and b'BEGIN:VCALENDAR' not in p.stdout

def test_import_report_persistence_quiet_and_dump(box):
    tmp,d,_,invoke,setup=box; setup('','')
    f=tmp/'in.ics'; f.write_text('BEGIN:VCALENDAR\nVERSION:2.0\nBEGIN:VEVENT\nDTSTART;VALUE=DATE:20240115\nSUMMARY:Planning Day\nEND:VEVENT\nEND:VCALENDAR\n')
    p=invoke('-i',f); assert p.returncode == 0 and p.stdout == b'Import process report: 7 lines read\n0 apps / 1 event / 0 todos / 0 skipped\n'
    assert b'Planning Day' in invoke('-G').stdout
    p=invoke('-i',f,'-q'); assert p.returncode == 0 and p.stdout == b''
    p=invoke('-i',f,'--dump-imported','--format-event','T:%m\\n'); assert p.stdout.startswith(b'T:Planning Day\n')

def test_import_case_handling_duration_and_escape(box):
    tmp,d,_,invoke,setup=box; setup('','')
    f=tmp/'mixed.ics'; f.write_text('BEGIN:VCALENDAR\nVERSION:2.0\nbegin:vevent\ndtstart:20240102T100000\nduration;X="x:y;z":PT1H30M\nsummary:Hi\\, there\nend:vevent\nEND:VCALENDAR\n')
    p=invoke('-i',f); assert p.returncode == 0
    p=invoke('-G'); assert b'Hi, there' in p.stdout
    p=invoke('-Q','--from','01/02/2024','--format-apt','%m:%d'); assert b'Hi, there:5400' in p.stdout

def test_import_access_error(box):
    _,_,_,invoke,setup=box; setup('','')
    p=invoke('-i','/no/such/file'); assert p.returncode != 0 and not p.stdout and b'input file cannot be accessed' in p.stderr

def test_config_unknown_malformed_and_input_format(box):
    tmp,_,run,_,_=box; conf=tmp/'confdir'; conf.mkdir(); (conf/'conf').write_text('# ok\nfuture.option=value\nformat.inputdate=2\n')
    p=run('-D',tmp/'data','-C',conf,'-d','29/2/2020'); assert p.returncode == 0 and b'unknown user option: "future.option" (ignored)' in p.stderr
    (conf/'conf').write_text('bad directive\n'); p=run('-C',conf,'--help'); assert p.returncode != 0 and b'invalid configuration directive' in p.stderr

def test_status_and_invalid_calendar_path(box):
    tmp,_,run,_,_=box; p=run('--status','-D',tmp/'d'); assert p.returncode == 0 and p.stdout == b'calcurse is not running\n'
    p=run('-a','-c',tmp/'missing'); assert p.returncode != 0 and b'does not exist' in p.stderr
