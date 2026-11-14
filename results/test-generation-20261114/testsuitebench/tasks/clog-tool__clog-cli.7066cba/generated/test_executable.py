import datetime
import os
import pathlib
import re
import subprocess
import tempfile

EXE = pathlib.Path('/workspace/executable')
ANSI = '\x1b[1;31merror:\x1b[0m '


def run(args=(), cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')


def config(directory, content='[clog]\n'):
    p = pathlib.Path(directory) / '.clog.toml'
    p.write_text(content, encoding='utf-8')
    return p


def successful(r):
    assert r.returncode == 0, (r.returncode, r.stdout, r.stderr)
    assert r.stderr == ''
    assert re.search(r'changelog written\. \([0-9]+ ms\)\n\Z', r.stdout)


def test_help_exact():
    r = run(['--help'])
    assert r.returncode == 0 and r.stderr == ''
    assert r.stdout.startswith('a conventional changelog for the rest of us\n\nUsage: executable [OPTIONS]\n\nOptions:\n')
    assert '  -s, --subtitle <STR>    \n' in r.stdout
    assert 'Commands:' not in r.stdout and 'Subcommands:' not in r.stdout
    assert r.stdout.endswith('If using the --config to specify a clog configuration TOML file NOT in the current working directory (meaning you need to use --work-tree or --git-dir) AND\nthe TOML file is inside your project directory (i.e. /myproject/.clog.toml) you do not need to use --work-tree or --git-dir.\n')


def test_version_exact():
    for opt in ('--version', '-V'):
        r = run([opt])
        assert (r.returncode, r.stdout, r.stderr) == (0, 'clog 0.10.0\n', '')


def test_option_parser_rejects_positional_unknown_and_after_dash():
    for args in (['bogus'], ['--wat'], ['-Z'], ['--', '--help'], ['add'], ['one', 'two']):
        r = run(args)
        assert r.returncode == 2 and r.stdout == ''
        assert 'unexpected argument' in r.stderr and 'Usage:' in r.stderr
        assert r.stderr.rstrip().endswith("For more information, try '--help'.")


def test_help_precedence():
    assert run(['--help', '--bad-option']).returncode == 0
    r = run(['nonsense', '--help'])
    assert r.returncode == 2 and 'unexpected argument' in r.stderr


def test_missing_and_repeated_values():
    for opt in ('--repository', '--from', '--format', '--git-dir', '--work-tree', '--subtitle', '--to', '--outfile', '--config', '--infile', '--setversion', '--link-style', '--changelog'):
        r = run([opt])
        assert r.returncode == 2 and r.stdout == ''
        assert opt in r.stderr and 'a value is required' in r.stderr and 'but none was supplied' in r.stderr
    r = run(['--subtitle', '-test-value'])
    assert r.returncode == 2 and r.stdout == ''
    r = run(['--repository', 'a', '--repository', 'b'])
    assert r.returncode == 2 and 'cannot be used multiple times' in r.stderr


def test_invalid_enum_values():
    for opt, bad, allowed in [('--format', 'xml', 'markdown, json'), ('--format', 'JSON', 'markdown, json'), ('--link-style', 'bitbucket', 'github, gitlab, stash, cgit')]:
        r = run([opt, bad])
        assert r.returncode == 2 and r.stdout == ''
        assert f"invalid value '{bad}'" in r.stderr and f'[possible values: {allowed}]' in r.stderr
    for opt, bad, good in [('--format', 'Markdown', 'markdown'), ('--link-style', 'GitHub', 'github')]:
        r = run([opt, bad])
        assert r.returncode == 2 and f"tip: a similar value exists: '{good}'" in r.stderr


def test_mutually_exclusive_options_and_pair_allowed():
    for args, first, second in [(['--from','abc','--from-latest-tag'], '--from <COMMIT>', '--from-latest-tag'),
                                (['--infile','a','--changelog','b'], '--infile <PATH>', '--changelog <PATH>'),
                                (['--changelog','a','--outfile','b'], '--changelog <PATH>', '--outfile <PATH>')]:
        r = run(args)
        assert r.returncode == 2 and r.stdout == ''
        assert f"the argument '{first}' cannot be used with '{second}'" in r.stderr
    with tempfile.TemporaryDirectory() as d:
        config(d)
        r = run(['--infile','absent','--outfile','out'], d)
        successful(r)


def test_missing_and_invalid_config_are_fatal():
    with tempfile.TemporaryDirectory() as d:
        r = run([], d)
        assert (r.returncode, r.stdout, r.stderr) == (1, '', ANSI + 'fatal I/O error with output file\n')
        for body in ('', 'not toml = [', '[clog]\nrepository = 2\n', 'subtitle="x"\n'):
            p = pathlib.Path(d) / 'bad.toml'; p.write_text(body)
            r = run(['--config', p], d)
            assert (r.returncode, r.stdout, r.stderr) == (1, '', ANSI + 'Failed to parse TOML configuration file\n')


def test_markdown_exact_shape_and_aliases():
    with tempfile.TemporaryDirectory() as d:
        config(d)
        r = run([], d); successful(r)
        date = datetime.date.today().isoformat()
        assert r.stdout.startswith(f'<a name=""></a>\n##   ({date})\n\n')
        r = run(['-Tmarkdown', '-s', 'Release', '--setversion', 'v weird'], d); successful(r)
        assert r.stdout.startswith(f'<a name="v weird"></a>\n## v weird Release ({date})\n\n')
        r = run(['--format=json', '--subtitle=Bug Fix', '--setversion', '1.0.1'], d); successful(r)
        assert r.stdout.startswith(f'{{"header":{{"version":Some("1.0.1"),"patch_version":false,"subtitle":Bug Fix,"date":"{date}"}},"sections":null}}changelog written.')


def test_config_ignored_fields_and_sections_accepted():
    with tempfile.TemporaryDirectory() as d:
        config(d, '[clog]\nrepository="https://example.test/r"\nsubtitle="From config"\noutput-format="json"\n[sections]\n"Odd name"=["feat", "type(scope)"]\n')
        r = run([], d); successful(r)
        assert r.stdout.startswith(f'<a name=""></a>\n##   ({datetime.date.today().isoformat()})\n\n')


def test_setversion_bypasses_increments_and_is_verbatim():
    with tempfile.TemporaryDirectory() as d:
        config(d)
        for version in ('1', 'v1.2.3-rc+build', 'anything !', '雪'):
            r = run(['--setversion', version, '--major', '-p'], d); successful(r)
            assert f'<a name="{version}"></a>' in r.stdout
        r = run(['--major'], d)
        assert r.returncode == 1 and r.stdout == '' and r.stderr == ANSI + 'Failed to parse version into valid SemVer. Ensure the version is in the X.Y.Z format.\n'


def test_git_range_and_location_options_are_tolerated():
    with tempfile.TemporaryDirectory() as d:
        config(d)
        for args in (['--from','does-not-exist'], ['--to','not-a-ref'], ['--from-latest-tag'], ['--git-dir','missing'], ['--work-tree','missing'], ['--repository','opaque value','--link-style','cgit']):
            r = run(args, d); successful(r)


def test_file_output_prepends_and_infile_preserves_bytes():
    with tempfile.TemporaryDirectory() as d:
        config(d)
        dest = pathlib.Path(d) / 'new.md'
        r = run(['--outfile', dest], d); successful(r)
        assert r.stdout.startswith('changelog written.')
        data = dest.read_bytes()
        assert data.endswith(b'\n' * 5)
        old = b'Old release\r\nsecond line\n'
        src = pathlib.Path(d) / 'old.md'; src.write_bytes(old)
        r = run(['--infile', src], d); successful(r)
        assert r.stdout.endswith(old.decode())
        r = run(['--infile', src, '--outfile', dest], d); successful(r)
        assert dest.read_bytes().endswith(old)
        assert src.read_bytes() == old


def test_changelog_in_place_and_output_errors():
    with tempfile.TemporaryDirectory() as d:
        config(d)
        p = pathlib.Path(d) / 'log.md'; p.write_bytes(b'old\n')
        r = run(['--changelog', p], d); successful(r)
        assert r.stdout.startswith('changelog written.') and p.read_bytes().endswith(b'old\n')
        r = run(['--outfile', pathlib.Path(d)/'missing'/'file'], d)
        assert (r.returncode, r.stdout, r.stderr) == (1, '', ANSI + 'fatal I/O error with output file\n')
