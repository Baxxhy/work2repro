import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


def run(args, cwd, *, env=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)


def write_dump(path, operations, date='anything'):
    path.write_text(json.dumps({'date': date, 'operations': operations}), encoding='utf-8')


@pytest.fixture
def work(tmp_path):
    return tmp_path


def test_global_help_and_version(work):
    p = run(['--help'], work)
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout.startswith('RnR is a command-line tool to rename multiple files and directories that\nsupports regular expressions\n\nUsage: executable <COMMAND>\n')
    assert p.stdout.endswith('  -V, --version  Print version\n')
    for flag in ('-h',):
        q = run([flag], work)
        assert (q.returncode, q.stdout, q.stderr) == (0, p.stdout, '')
    for flag in ('--version', '-V', '--version',):
        q = run([flag], work)
        assert (q.returncode, q.stdout, q.stderr) == (0, 'rnr 0.5.1\n', '')
    assert run(['--help', 'regex'], work).stdout == p.stdout
    assert run(['help'], work).stdout == p.stdout


@pytest.mark.parametrize('cmd,title', [
    ('regex', 'Rename files and directories using a regular expression'),
    ('from-file', 'Read operations from a dump file'),
    ('to-ascii', 'Replace file name UTF-8 chars with ASCII chars representation'),
], ids=['regex-help', 'replay-help', 'ascii-help'])
def test_command_help(cmd, title, work):
    for flag in ('--help', '-h'):
        p = run([cmd, flag, 'ignored'], work)
        assert p.returncode == 0 and p.stderr == ''
        assert p.stdout.startswith(title + '\n\nUsage: executable ' + cmd)


def test_missing_and_unknown_commands(work):
    p = run([], work)
    assert p.returncode == 2 and p.stdout == '' and p.stderr.startswith('RnR is a command-line tool')
    p = run(['bogus'], work)
    assert p.returncode == 2 and "unrecognized subcommand 'bogus'" in p.stderr
    assert run(['help', '--help'], work).returncode == 2


@pytest.mark.parametrize('args,fragment', [
    (['regex', 'a'], '<REPLACEMENT>'),
    (['regex', 'a', 'b'], '<PATH(S)>'),
    (['to-ascii'], 'Replace file name UTF-8 chars'),
    (['regex', 'a', 'b', 'x', '--unknown'], "unexpected argument '--unknown'"),
    (['regex', 'a', 'b', 'x', '--color', 'bogus'], "invalid value 'bogus'"),
    (['regex', 'a', 'b', 'x', '--color', 'never', '--color', 'auto'], 'cannot be used multiple times'),
    (['regex', 'a', 'b', 'x', '-nf'], "'--dry-run' cannot be used with '--force'"),
    (['regex', 'a', 'b', 'x', '--dump', '--no-dump'], "'--dump' cannot be used with '--no-dump'"),
    (['--color', 'never', 'regex', '--help'], "unexpected argument '--color'"),
    (['regex', 'a', 'b', 'x', '--hidden'], "requires '--recursive'"),
], ids=['missing-replacement', 'missing-path', 'ascii-no-path', 'unknown-option', 'bad-color', 'repeat-color', 'mode-conflict', 'dump-conflict', 'pre-command-option', 'hidden-needs-recursive'])
def test_cli_errors(args, fragment, work):
    p = run(args, work)
    assert p.returncode == 2 and p.stdout == '' and fragment in p.stderr


def test_default_preview_and_no_match(work):
    (work / 'test-aaa-bbb.txt').write_text('payload')
    p = run(['regex', '-', '_', 'test-aaa-bbb.txt'], work)
    assert p.returncode == 0 and p.stderr == ''
    assert p.stdout == 'This is a DRY-RUN\ntest-aaa-bbb.txt -> test_aaa-bbb.txt\n'
    assert (work / 'test-aaa-bbb.txt').exists() and not (work / 'test_aaa-bbb.txt').exists()
    q = run(['regex', 'absent', 'x', 'test-aaa-bbb.txt'], work)
    assert q.stdout == 'This is a DRY-RUN\n'


@pytest.mark.parametrize('limit,want', [(None, 'a_b-c-d.txt'), (2, 'a_b_c-d.txt'), (0, 'a_b_c_d.txt')], ids=['default-limit', 'limit-two', 'unlimited'])
def test_regex_replacement_limit(limit, want, work):
    (work / 'a-b-c-d.txt').touch()
    args = ['regex'] + (['-l', str(limit)] if limit is not None else []) + ['-', '_', 'a-b-c-d.txt']
    p = run(args, work)
    assert p.returncode == 0 and f'a-b-c-d.txt -> {want}\n' in p.stdout


def test_regex_captures_and_transform(work):
    (work / 'report_2023_01.txt').touch()
    p = run(['regex', r'report_(\d+)_(\d+)', '$2-$1-report', 'report_2023_01.txt'], work)
    assert 'report_2023_01.txt -> 01-2023-report.txt\n' in p.stdout
    (work / 'aa-bb-cc.txt').touch()
    q = run(['regex', '-t', 'upper', r'([a-z]+)', '${1}', 'aa-bb-cc.txt'], work)
    assert 'aa-bb-cc.txt -> AA-bb-cc.txt\n' in q.stdout
    (work / 'test.txt').touch()
    r = run(['regex', '', 'prefix_', 'test.txt'], work)
    assert 'test.txt -> prefix_test.txt\n' in r.stdout


@pytest.mark.parametrize('name,want', [
    ('café.txt', 'cafe.txt'), ('naïve_résumé.pdf', 'naive_resume.pdf'), ('straße.txt', 'strasse.txt'),
    ('Þórr.txt', 'Thorr.txt'), ('æther.txt', 'aether.txt'), ('привет.txt', 'privet.txt'),
    ('日本語.doc', 'RiBenYu.doc'), ('한글.pdf', 'HanGeul.pdf'), ('Ελληνικά.txt', 'Ellinika.txt'),
    ('العربية.md', 'l`rbyh.md'), ('test☕.txt', 'test:coffee:.txt'), ('with╱slash.txt', 'with_slash.txt'),
], ids=['accent', 'multi-accent', 'german-sharp-s', 'thorn', 'ligature', 'cyrillic', 'japanese', 'korean', 'greek', 'arabic', 'emoji', 'slash-like'])
def test_ascii_examples(name, want, work):
    (work / name).touch()
    p = run(['to-ascii', name], work)
    assert p.returncode == 0 and f'{name} -> {want}\n' in p.stdout


def test_force_backup_and_no_dump(work):
    (work / 'old.txt').write_text('bytes')
    (work / 'old.txt.bk').write_text('old backup')
    p = run(['regex', '-f', '-b', '--no-dump', 'old', 'new', 'old.txt'], work)
    assert p.returncode == 0 and (work / 'new.txt').read_text() == 'bytes'
    assert (work / 'old.txt.bk.1').read_text() == 'bytes'
    assert 'Info:  Backup created - old.txt -> old.txt.bk.1\nold.txt -> new.txt\n' == p.stdout


def test_recursive_hidden_depth_and_dirs(work):
    (work / 'root').mkdir(); (work / 'root' / 'inner').mkdir()
    (work / 'root' / 'a.txt').touch(); (work / 'root' / 'inner' / 'b.txt').touch()
    (work / 'root' / '.secret.txt').touch()
    p = run(['regex', '-r', '-d', '1', 'txt', 'doc', 'root'], work)
    assert 'root/a.txt -> root/a.doc' in p.stdout
    assert 'b.txt' not in p.stdout and '.secret' not in p.stdout
    q = run(['regex', '-r', '-x', 'txt', 'doc', 'root'], work)
    assert '.secret.txt -> .secret.doc' in q.stdout
    assert 'root/inner/b.txt' in q.stdout


def test_symlink_and_lexical_alias_dedup(work):
    (work / 'old').write_text('x')
    p = run(['regex', 'old', 'new', 'old', './old'], work)
    assert p.stdout.count(' -> ') == 2
    (work / 'link').symlink_to('missing-target')
    q = run(['regex', '-f', '--no-dump', 'link', 'renamed', 'link'], work)
    assert q.returncode == 0 and (work / 'renamed').is_symlink()
    assert os.readlink(work / 'renamed') == 'missing-target'


def test_collisions_and_occupied_target(work):
    (work / 'cat').touch(); (work / 'bat').touch()
    p = run(['regex', '-f', '[cb]at', 'x', 'cat', 'bat'], work)
    assert p.returncode == 1 and 'Files will have the same name' in p.stderr
    assert (work / 'cat').exists() and (work / 'bat').exists()
    (work / 'source').touch(); (work / 'target').touch()
    q = run(['regex', '-f', 'source', 'target', 'source'], work)
    assert q.returncode == 1 and 'Conflict with existing path source -> target' in q.stderr


def test_chain_order_execution(work):
    for n in ('a.txt', 'aa.txt', 'aaa.txt'):
        (work / n).write_text(n)
    p = run(['regex', '-f', '--no-dump', 'a', 'aa', 'a.txt', 'aa.txt', 'aaa.txt'], work)
    assert p.returncode == 0
    lines = p.stdout.splitlines()
    assert lines == ['aaa.txt -> aaaa.txt', 'aa.txt -> aaa.txt', 'a.txt -> aa.txt']
    assert (work / 'aa.txt').read_text() == 'a.txt'
    assert (work / 'aaa.txt').read_text() == 'aa.txt'
    assert (work / 'aaaa.txt').read_text() == 'aaa.txt'


def test_from_file_preview_force_undo_and_validation(work):
    dump = work / 'ops.json'
    write_dump(dump, [{'source': 'one', 'target': 'two'}, {'source': 'three', 'target': 'four'}])
    p = run(['from-file', str(dump)], work)
    assert p.returncode == 0 and p.stdout == 'This is a DRY-RUN\none -> two\nthree -> four\n'
    (work / 'two').write_text('2'); (work / 'four').write_text('4')
    q = run(['from-file', '-f', '--no-dump', '-u', str(dump)], work)
    assert q.returncode == 0 and (work / 'one').read_text() == '2' and (work / 'three').read_text() == '4'
    for content in ('', '{bad', '{"date":1,"operations":[]}','{"date":"x","operations":[{}]}'):
        bad = work / 'bad.json'; bad.write_text(content)
        r = run(['from-file', str(bad)], work)
        assert r.returncode == 1 and r.stdout == 'This is a DRY-RUN\n' and 'Cannot parse JSON file' in r.stderr


def test_dump_json_schema_and_preview_dump(work):
    (work / 'old.txt').touch()
    p = run(['regex', '--dump', '--dump-prefix', 'saved-', 'old', 'new', 'old.txt'], work)
    assert p.returncode == 0
    files = list(work.glob('saved-*.json'))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert set(data) == {'date', 'operations'} and re.fullmatch(r'\d{4}-\d\d-\d\d \d\d:\d\d:\d\d', data['date'])
    assert data['operations'] == [{'source': 'old.txt', 'target': 'new.txt'}]


def test_dump_failure_order_and_silence(work):
    (work / 'old').touch()
    p = run(['regex', '--dump', '--dump-prefix', 'missing/x', 'old', 'new', 'old'], work)
    assert p.returncode == 1 and p.stdout == 'This is a DRY-RUN\n' and 'Cannot create file' in p.stderr
    q = run(['regex', '-s', '-f', 'old', 'new', 'old'], work)
    assert q.returncode == 0 and q.stdout == q.stderr == '' and (work / 'new').exists()


def test_replay_errors_and_missing_source(work):
    p = run(['from-file', 'missing.json'], work)
    assert p.returncode == 1 and p.stdout == 'This is a DRY-RUN\n' and p.stderr == 'Error: Cannot open/read file missing.json\n'
    dump = work / 'op.json'; write_dump(dump, [{'source': 'absent', 'target': 'new'}])
    q = run(['from-file', '-f', '--no-dump', dump.name], work)
    assert q.returncode == 1 and 'Cannot rename absent -> new' in q.stderr


def test_color_always_preview(work):
    (work / 'abc123xyz.txt').touch()
    p = run(['regex', '--color', 'always', '123', '456', 'abc123xyz.txt'], work)
    assert p.stdout == '\x1b[1mThis is a DRY-RUN\x1b[0m\n\x1b[38;5;8mabc123xyz.txt\x1b[0m -> \x1b[32mabc\x1b[0m\x1b[1;31m456\x1b[0m\x1b[32mxyz.txt\x1b[0m\n'


@pytest.mark.parametrize('pattern,reason', [
    ('([a-z])\\1', 'backreferences are not supported'),
    ('(?=x)', 'look-around'),
    ('([', 'unclosed character class'),
], ids=['backreference', 'lookaround', 'malformed-class'])
def test_bad_regex_even_silent(pattern, reason, work):
    p = run(['regex', '-s', pattern, 'x', 'filename'], work)
    assert p.returncode == 1 and p.stdout == '' and 'Error: Bad expression provided' in p.stderr and reason in p.stderr
