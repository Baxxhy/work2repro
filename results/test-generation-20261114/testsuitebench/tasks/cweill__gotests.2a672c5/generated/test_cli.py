import os
import re
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')

def run(*args, cwd=None, env=None, data=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, env=e, input=data,
                          text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)

def test_help_exact_shape_and_precedence():
    p = run('--help', '--bad')
    assert p.returncode == 0 and not p.stdout
    assert p.stderr.startswith(f'Usage of {EXE}:\n') and p.stderr.endswith('\n')
    assert 'subcommand' not in p.stderr and 'Commands:' not in p.stderr
    q = run('--all', '--help', '--bad')
    assert q.returncode == 0 and not q.stdout and q.stderr.startswith(f'Usage of {EXE}:\n')

def test_version_bypasses_validation():
    p = run('--version', '--ai', '--ai-model=', 'missing.go')
    lines = p.stdout.splitlines()
    assert p.returncode == 0 and len(lines) == 4 and not p.stderr
    assert re.fullmatch(r'gotests \S+', lines[0])
    assert re.match(r'Go version: go\d+\.\d+', lines[1])
    assert lines[2].startswith('Git commit: ') and lines[2][12:]
    assert lines[3].startswith('Build time: ') and lines[3][12:]

def test_flag_diagnostics_and_dashes():
    for args, fragment in [(("--unknown",), 'flag provided but not defined: -unknown'),
                           (("--only",), 'flag needs an argument: -only'),
                           (("--ai-min-cases=bad",), 'invalid value "bad" for flag -ai-min-cases: parse error'),
                           (("--all=x",), 'invalid boolean value')]:
        p = run(*args)
        assert p.returncode != 0 and not p.stdout and fragment in p.stderr and 'Usage of ' in p.stderr

def test_selector_precedes_paths_and_empty_regex_is_not_selector():
    for args in [(), ('bare.go',), ('-i',), ('-only=', 'x.go'), ('-excl=',)]:
        p = run(*args)
        assert p.returncode == 0 and p.stdout == 'Please specify either the -only, -excl, -exported, or -all flag\n'
        assert not p.stderr
    p = run('-all')
    assert p.stdout == 'Please specify a file or directory containing the source\n'

def test_bad_regex_runtime_error():
    p = run('-only', '(invalid', 'x.go')
    assert p.returncode == 0 and p.stdout.startswith('Invalid -only regex: error parsing regexp:')
    assert not p.stderr

def test_version_flag_requires_parse_position():
    # Once -- terminates parsing, version is a path and selector validation still applies.
    p = run('--', '--version')
    assert p.returncode == 0 and p.stdout.startswith('Please specify either')
