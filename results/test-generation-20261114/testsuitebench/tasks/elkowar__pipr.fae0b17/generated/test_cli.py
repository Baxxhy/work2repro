import os
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')
PROGRAM = str(EXE)

HELP = f'''Usage: {PROGRAM} [options]

Options:
    -d, --default TEXT  text inserted into the textfield on startup
    -o, --out-file FILE write final command to file
        --in-file FILE  read initial command from file
        --config-reference 
                        print out the default configuration file
    -r, --raw-mode      keep linebreaks in finished command when closing
        --no-isolation  disable isolation. This will run the commands directly
                        on your system, without protection. Take care.
    -h, --help          print this help menu
'''

CONFIG = '''
#  ____  _
# |  _ \\(_)_ __  _ __       .________.
# | |_) | | '_ \\| '__|      |________|
# |  __/| | |_) | |          |_    -|
# |_|   |_| .__/|_|     xX  xXx___x_|
#         |_|
#
# A commandline utility by
# Leon Kowarschick

# finish_hook: Executed once you close pipr, getting the command you constructed piped into stdin.
# finish_hook = "xclip -selection clipboard -in"

# Paranoid history mode writes every sucessfully running command into the history in autoeval mode.
paranoid_history_mode_default = false

autoeval_mode_default = true

history_size = 500
cmdlist_always_show_preview = false
cmd_timeout_millis = 2000

highlighting_enabled = true

eval_environment = ["bash", "-c"]

# Snippets can be used to quickly insert common bits of shell
# use || (two pipes) where you want your cursor to be after insertion
[snippets]
s = " | sed -r 's/||//g'"

[help_viewers]
'm' = "man ??"
'h' = "?? --help | less"

[output_viewers]
'l' = "less"

'''


def invoke(*args, env=None, cwd=None, **kwargs):
    return subprocess.run([PROGRAM, *map(str, args)], capture_output=True, env=env, cwd=cwd, **kwargs)


def test_help_short_exact():
    p = invoke('-h')
    assert p.returncode == 0 and p.stdout.decode() == HELP and p.stderr == b''


def test_help_long_exact_and_precedes_runtime_checks(tmp_path):
    env = dict(os.environ, PATH=str(tmp_path), XDG_CONFIG_HOME='/missing')
    p = invoke('--in-file', '/does/not/exist', '--help', env=env)
    assert p.returncode == 0 and p.stdout.decode() == HELP and p.stderr == b''


def test_config_reference_exact_without_bwrap(tmp_path):
    p = invoke('--config-reference', env=dict(os.environ, PATH=str(tmp_path)))
    assert p.returncode == 0 and p.stdout.decode() == CONFIG and p.stderr == b''


def test_help_over_config_reference():
    p = invoke('--config-reference', '-h')
    assert p.returncode == 0 and p.stdout.decode() == HELP


def test_bwrap_missing_precedes_input_file(tmp_path):
    env = dict(os.environ, PATH=str(tmp_path))
    p = invoke('--in-file', '/tmp/programbench-pipr-nonexistent/nonexistent.txt', env=env)
    assert p.returncode == 1
    assert p.stdout == b'bubblewrap installation not found. Please make sure you have `bwrap` on your path, or supply --no-isolation to disable safe-mode\n'
    assert p.stderr == b''


def test_no_isolation_requires_tty():
    p = invoke('--no-isolation', stdin=None)
    assert p.returncode != 0


def test_missing_input_after_isolation_bypassed():
    p = invoke('--no-isolation', '--in-file', '/tmp/programbench-pipr-nonexistent/nonexistent.txt')
    assert p.returncode != 0 and b'No such file or directory' in p.stderr


def test_duplicate_value_options_use_canonical_name():
    cases = [(['--help', '-d', 'a', '-d=b'], 'default'),
             (['--out-file=a', '-o', 'b'], 'out-file'),
             (['--in-file=a', '--in-file', 'b'], 'in-file')]
    for args, name in cases:
        p = invoke(*args)
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr.decode() == f"{PROGRAM}: Option '{name}' given more than once\n"


def test_unrecognized_and_missing_arguments():
    cases = [(['--verbose'], "Unrecognized option: 'verbose'"),
             (['-help'], "Unrecognized option: 'e'"),
             (['--default'], "Argument to option 'default' missing"),
             (['-o'], "Argument to option 'o' missing")]
    for args, msg in cases:
        p = invoke(*args)
        assert p.returncode == 1 and p.stdout == b''
        assert p.stderr.decode() == f'{PROGRAM}: {msg}\n'


def test_long_values_equals_and_invalid_options(tmp_path):
    for option in ['--version', '--quiet', '--debug', '--config', '--def']:
        p = invoke(option)
        assert p.returncode == 1 and p.stdout == b''
    # Syntax is validated before runtime; these values must be accepted as values.
    p = invoke('--default=--help', '--no-isolation')
    assert p.returncode != 0  # accepted options reach the terminal requirement


def test_output_directory_is_startup_error(tmp_path):
    target = tmp_path / 'directory'
    target.mkdir()
    p = invoke('--no-isolation', '--out-file', target)
    assert p.returncode != 0
