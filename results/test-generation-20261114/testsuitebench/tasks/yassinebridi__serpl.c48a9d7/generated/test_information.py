import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor


HELP = ("A simple terminal UI for search and replace, ala VS Code\n\n"
        "Usage: executable [OPTIONS]\n\nOptions:\n"
        "  -p, --project-root <PATH>  Path to the project root [default: .]\n"
        "  -h, --help                 Print help\n"
        "  -V, --version              Print version\n")


def test_help_short_and_long_are_exact(run_prog):
    for flag in ('-h', '--help'):
        p = run_prog(flag)
        assert p.returncode == 0
        assert p.stdout.decode('utf-8') == HELP
        assert p.stderr == b''


def test_help_works_without_environment(run_prog, executable):
    env = {'PATH': os.environ.get('PATH', ''), 'HOME': '', 'TERM': '',
           'LANG': '', 'PWD': '', 'EDITOR': '', 'PAGER': '',
           'XDG_CONFIG_HOME': '', 'XDG_DATA_HOME': '', 'SERPL_CONFIG': '',
           'SERPL_DATA': ''}
    p = subprocess.run([executable, '--help'], env=env, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, timeout=4)
    assert (p.returncode, p.stdout.decode(), p.stderr) == (0, HELP, b'')


def version_parts(output):
    text = output.decode('utf-8')
    lines = text.splitlines()
    assert len(lines) == 5
    assert lines[0].startswith('serpl 0.3.4- (') and lines[0].endswith(')')
    date = lines[0][len('serpl 0.3.4- ('):-1]
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', date)
    import datetime
    datetime.date.fromisoformat(date)
    assert lines[1] == ''
    assert lines[2] == 'Authors: Yassine Bridi <ybridi@gmail.com>'
    assert lines[3] == ''
    assert lines[4].startswith('Config directory: ')
    assert text.endswith('\n') and not text.endswith('\n\n')
    return date, lines[4][len('Config directory: '):]


def test_version_aliases_fixed_date_and_layout(run_prog):
    results = [run_prog(flag) for flag in ('-V', '--version')]
    assert all(p.returncode == 0 and p.stderr == b'' for p in results)
    parts = [version_parts(p.stdout) for p in results]
    assert results[0].stdout == results[1].stdout
    assert parts[0][0] == parts[1][0]


def test_config_directory_precedence_and_data_independence(run_prog, tmp_path):
    cases = [
        ({'SERPL_CONFIG': '/exact/cfg', 'XDG_CONFIG_HOME': '/xdg',
          'SERPL_DATA': '/data1', 'XDG_DATA_HOME': '/data2'}, '/exact/cfg'),
        ({'SERPL_CONFIG': None, 'XDG_CONFIG_HOME': '/xdg',
          'SERPL_DATA': '/data1'}, '/xdg/serpl'),
        ({'SERPL_CONFIG': None, 'XDG_CONFIG_HOME': None, 'HOME': str(tmp_path)},
         str(tmp_path / '.config/serpl')),
    ]
    for env, expected in cases:
        p = run_prog('--version', env=env)
        assert p.returncode == 0 and p.stderr == b''
        assert version_parts(p.stdout)[1] == expected


def test_information_modes_are_deterministic_concurrently(run_prog):
    with ThreadPoolExecutor(max_workers=8) as pool:
        outputs = list(pool.map(lambda _: run_prog('--version').stdout, range(12)))
    assert len(set(outputs)) == 1
    assert all(run_prog('-h').stdout == HELP.encode() for _ in range(3))


def test_help_and_version_short_circuit_later_arguments(run_prog):
    for args, expected in [(("--help", "--badflag"), HELP.encode()),
                           (("--version", "extra-positional"), None),
                           (("--version", "--", "--badflag"), None),
                           (("-hp", "/tmp"), HELP.encode())]:
        p = run_prog(*args)
        assert p.returncode == 0 and p.stderr == b''
        if expected is not None:
            assert p.stdout == expected
        else:
            version_parts(p.stdout)


def test_later_information_flag_after_valid_root_short_circuits(run_prog, tmp_path):
    for args in [('-p', str(tmp_path), '--help'), ('--project-root', str(tmp_path), '-V')]:
        p = run_prog(*args)
        assert p.returncode == 0 and p.stderr == b''
