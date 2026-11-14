from conftest import text


HELP = """bartib 1.1.0
Nikolas Schmidt-Voigt <nikolas.schmidt-voigt@posteo.de>
A simple timetracker

USAGE:
    executable [OPTIONS] <SUBCOMMAND>

FLAGS:
    -h, --help       Prints help information
    -V, --version    Prints version information

OPTIONS:
    -f <FILE>        the file in which bartib tracks all the activities [env: BARTIB_FILE=]

SUBCOMMANDS:
    cancel      cancels all currently running activities
    change      changes the current activity
    check       checks file and reports parsing errors
    continue    continues a previous activity
    current     lists all currently running activities
    edit        opens the activity log in an editor
    help        Prints this message or the help of the given subcommand(s)
    last        displays the descriptions and projects of recent activities
    list        list recent activities
    projects    list all projects
    report      reports duration of tracked activities
    sanity      checks sanity of bartib log
    search      search for existing descriptions and projects
    start       starts a new activity
    status      shows current status and time reports for today, current week, and current month
    stop        stops all currently running activities

To get help for a specific subcommand, run `bartib [SUBCOMMAND] --help`.
To get started, view the `start` help with `bartib start --help`
"""


def test_top_help_and_version(invoke):
    for args, expected in [(('--help',), HELP), (('-h',), HELP), (('help',), HELP),
                           (('--version',), 'bartib 1.1.0\n'), (('-V',), 'bartib 1.1.0\n'),
                           (('--version', '--help'), 'bartib 1.1.0\n')]:
        p, _ = invoke(*args)
        assert p.returncode == 0 and text(p.stdout) == expected and p.stderr == b''


def test_empty_args_emits_help_to_stderr(invoke):
    p, _ = invoke()
    assert p.returncode == 1 and p.stdout == b'' and text(p.stderr) == HELP


def test_explicit_file_overrides_environment_and_can_contain_unicode(invoke, tmp_path):
    chosen = tmp_path / 'unicodé !.log'
    other = tmp_path / 'other.log'
    p, _ = invoke('-f', chosen, 'start', '-p', 'P', '-d', 'D', '-t', '9:00', env={'BARTIB_FILE': str(other)})
    assert p.returncode == 0 and chosen.exists() and not other.exists()
    assert '09:00 | P | D\n' in chosen.read_text()


def test_missing_log_path_and_empty_env_path_diagnostics(invoke):
    p, _ = invoke('current', env={'BARTIB_FILE': None})
    assert p.returncode == 1 and p.stdout == b'' and b'Please specify a file' in p.stderr
    p, _ = invoke('current', env={'BARTIB_FILE': ''}, path=__import__('pathlib').Path('unused'))
    assert p.returncode == 1 and b'Could not read from file: ' in p.stderr


def test_read_does_not_create_missing_log_and_start_does(invoke, tmp_path):
    missing = tmp_path / 'nested' / 'new.log'
    p, _ = invoke('current', path=missing)
    assert p.returncode == 1 and not missing.exists() and b'Could not read from file:' in p.stderr
    p, _ = invoke('start', '-p', 'P', '-d', 'D', '-t', '10:05', path=tmp_path / 'created.log')
    assert p.returncode == 0


def test_cli_rejects_misplaced_global_options_aliases_and_unknowns(invoke):
    for args in [('current', '-f', 'x'), ('ls',), ('START',), ('list', 'list'), ('--verbose',)]:
        p, _ = invoke(*args)
        assert p.returncode == 1 and p.stdout == b'' and p.stderr


def test_start_requires_fields_but_accepts_empty_values(invoke):
    p, _ = invoke('start', '-d', 'D')
    assert p.returncode == 1 and b'--project <PROJECT>' in p.stderr
    p, log = invoke('start', '--project=', '--description=', '-t', '10:5')
    assert p.returncode == 0 and 'Started activity: "" ()' in text(p.stdout)
    assert '10:05 |  | \n' in log.read_text()


def test_command_help_present_for_commands(invoke):
    for cmd in ('start','stop','change','continue','cancel','check','current','edit','last','list','projects','report','sanity','search','status'):
        p, _ = invoke(cmd, '--help')
        assert p.returncode == 0 and text(p.stdout).startswith(f'executable-{cmd} \n')
        assert 'USAGE:' in text(p.stdout) and 'FLAGS:' in text(p.stdout) and text(p.stdout).endswith('\n')
