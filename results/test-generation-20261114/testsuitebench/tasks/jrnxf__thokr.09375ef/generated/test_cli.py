import os
import subprocess
from pathlib import Path

BIN = Path('/workspace/executable')

HELP = '''thokr 0.4.1
sleek typing tui with visualized results and historical logging

USAGE:
    executable [OPTIONS]

OPTIONS:
    -f, --full-sentences <NUMBER_OF_SENTENCES>
            number of sentences to use in test

    -h, --help
            Print help information

    -l, --supported-language <SUPPORTED_LANGUAGE>
            language to pull words from [default: english] [possible values: english, english1k,
            english10k]

    -p, --prompt <PROMPT>
            custom prompt to use

    -s, --number-of-secs <NUMBER_OF_SECS>
            number of seconds to run test

    -V, --version
            Print version information

    -w, --number-of-words <NUMBER_OF_WORDS>
            number of words to use in test [default: 15]
'''

def run(*args):
    return subprocess.run([str(BIN), *args], input=b'', stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def test_help_is_exact_and_help_takes_precedence():
    for args in [('--help',), ('-h',), ('--help', '--definitely-not-a-flag'), ('-w', '5', '--help')]:
        p = run(*args)
        assert (p.returncode, p.stdout.decode(), p.stderr) == (0, HELP, b'')
    assert 'COMMANDS:' not in HELP and 'SUBCOMMANDS:' not in HELP

def test_version_is_exact_and_combines_with_valid_options():
    for args in [('-V',), ('--version',), ('-p', 'x', '-w', '0', '-V')]:
        p = run(*args)
        assert p.returncode == 0 and p.stdout == b'thokr 0.4.1\n' and p.stderr == b''

def test_valid_options_reach_tty_validation():
    valid = [(), ('-w','0'), ('--number-of-words=999999999999999999'), ('-w=5',),
             ('-f','0'), ('-s','0'), ('-l','english10k'), ('-p',''), ('-p','café 🧪'),
             ('-w','2','-l','english1k','-p','x'), ('-f=2','-s=1','-l=english')]
    for args in valid:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b''
        assert p.stderr.decode() == 'error: stdin must be a tty\n\nUSAGE:\n    thokr [OPTIONS]\n\nFor more information try --help\n'

def test_missing_values_use_canonical_argument_names():
    pairs = [('-w','--number-of-words <NUMBER_OF_WORDS>'), ('-f','--full-sentences <NUMBER_OF_SENTENCES>'),
             ('-s','--number-of-secs <NUMBER_OF_SECS>'), ('-p','--prompt <PROMPT>')]
    for flag, label in pairs:
        p = run(flag)
        assert p.returncode == 2 and p.stdout == b''
        assert p.stderr.decode().startswith(f"error: The argument '{label}' requires a value but none was supplied\n\nUSAGE:\n")
        assert p.stderr.endswith(b'For more information try --help\n')
    p = run('-l')
    assert p.returncode == 2 and b"'--supported-language <SUPPORTED_LANGUAGE>' requires a value" in p.stderr
    assert b'\t[possible values: english, english1k, english10k]\n' in p.stderr

def test_single_use_options_reject_duplicates():
    cases = [('-w','1','-w','2','--number-of-words <NUMBER_OF_WORDS>'),
             ('-f','1','--full-sentences=2','--full-sentences <NUMBER_OF_SENTENCES>'),
             ('-s','1','-s2','--number-of-secs <NUMBER_OF_SECS>'),
             ('-p','a','--prompt=b','--prompt <PROMPT>'),
             ('-l','english','-lenglish1k','--supported-language <SUPPORTED_LANGUAGE>')]
    for *args, label in cases:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b''
        assert f"error: The argument '{label}' was provided more than once, but cannot be used multiple times" in p.stderr.decode()

def test_integer_values_and_negative_tokens_are_strict():
    for opt, label in [('-w','--number-of-words <NUMBER_OF_WORDS>'),('-f','--full-sentences <NUMBER_OF_SENTENCES>'),('-s','--number-of-secs <NUMBER_OF_SECS>')]:
        p = run(opt, 'abc')
        assert p.returncode == 2 and p.stdout == b''
        assert f'Invalid value "abc" for \'{label}\': invalid digit found in string' in p.stderr.decode()
    p = run('-w','999999999999999999999')
    assert p.returncode == 2 and b'number too large to fit in target type' in p.stderr
    p = run('-w','-1')
    assert p.returncode == 2 and b"Found argument '-1'" in p.stderr and b'-- -1' in p.stderr

def test_languages_unknown_flags_positionals_and_option_cluster():
    p = run('-l','English')
    assert p.returncode == 2 and b'Did you mean "english"?' in p.stderr
    p = run('--supported-language','invalid')
    assert p.returncode == 2 and b'\t[possible values: english, english1k, english10k]' in p.stderr
    for args, token in [(('--oops',), "'--oops'"), (('add',), "'add'"), (('--','--help'), "'--help'"), (('--','-w'), "'-w'"), (('-ws','10'), "'10'")]:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b'' and token.encode() in p.stderr
        assert b'USAGE:' in p.stderr and b'For more information try --help' in p.stderr

