import json
import os
import pathlib
import subprocess

import pytest


EVAL = pathlib.Path(__file__).resolve().parent
BIN = pathlib.Path('/workspace/executable')
FIX = EVAL / 'fixtures'


def run(*args, cwd=None, env=None, input=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd or EVAL, env=e,
                          input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def source(tmp_path, text, name='demo.sh'):
    p = tmp_path / name
    p.write_text(text, encoding='utf-8')
    return p


def eval_script(path, *args, env=None, cwd=None):
    r = run('--argc-eval', path, *args, env=env, cwd=cwd)
    assert r.returncode == 0
    return r.stdout


def evaluated(path, *args, env=None, cwd=None):
    code = eval_script(path, *args, env=env, cwd=cwd)
    return subprocess.run(['/usr/bin/bash', '-c', code], cwd=cwd or EVAL,
                          env={**os.environ, **(env or {})}, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def test_version_and_exact_help():
    r = run('--argc-version')
    assert (r.returncode, r.stdout, r.stderr) == (0, b'argc 1.23.0\n', b'')
    r = run('--argc-help')
    assert r.returncode == 0 and r.stderr == b''
    assert r.stdout.startswith(b'A bash cli framework, also a bash-based command runner')
    assert b'argc --argc-parallel <FILE> <ARGS~>' in r.stdout
    assert r.stdout.endswith(b'\n\n')


def test_unknown_internal_option():
    r = run('--argc-not-real')
    assert r.returncode == 1 and r.stdout == b''
    assert r.stderr == b'Unknown option `--argc-not-real`\n'


def test_eval_missing_and_load_error():
    assert run('--argc-eval').stdout == b"echo 'Error: No script file provided'\nexit 1\n"
    r = run('--argc-eval', '/no/such/eval-source.sh')
    assert r.returncode == 0
    assert r.stdout == b"echo 'Error: Failed to load script at '\\''/no/such/eval-source.sh'\\'''\nexit 1\n"


def test_directives_parse_function_forms_namespaces_and_aliases(tmp_path):
    p = source(tmp_path, '''# @describe Demo
# root detail
# @alias one,o
# @cmd first
foo_bar () { printf '%s' "$1"; }
# @cmd Parent
parent() { :; }
# @cmd second
parent::child() { echo child; }
# @cmd deep
parent::child::leaf () { :; }
''')
    obj = json.loads(run('--argc-export', p).stdout)
    assert obj['describe'] == 'Demo\nroot detail'
    assert [x['name'] for x in obj['subcommands']] == ['foo_bar', 'parent']
    assert obj['subcommands'][0]['aliases'] == ['foo-bar', 'one', 'o']
    assert obj['subcommands'][1]['subcommands'][0]['subcommands'][0]['name'] == 'leaf'


@pytest.mark.parametrize('tag,line', [('arg', 3), ('flag', 3), ('option', 3)], ids=['orphan-arg','orphan-flag','orphan-option'])
def test_orphan_parameters_after_function_are_source_errors(tmp_path, tag, line):
    p = source(tmp_path, f'helper() {{ :; }}\n# @{tag} --x\n')
    r = run('--argc-eval', p)
    assert r.returncode == 0
    assert f'@{tag}(line 2)'.encode() in r.stdout and b'exit 1' in r.stdout


def test_unknown_directive_and_missing_nested_parent(tmp_path):
    p = source(tmp_path, '# comment\n# @wat value\n')
    assert run('--argc-eval', p).stdout == b"echo 'Error: @wat(line 2) is unknown tag'\nexit 1\n"
    p = source(tmp_path, 'x() { :; }\nnope::kid() { :; }\n')
    r = run('--argc-export', p)
    assert r.returncode != 0 and b'nope::kid(line 2) lack of parent command' in r.stderr


def test_flags_aliases_repeat_and_plus_identifier(tmp_path):
    p = source(tmp_path, '''# @flag -v --verbose Verbose
# @flag --count* Count
# @flag +o +output Output
main() { printf '%s|%s|%s' "$argc_verbose" "$argc_count" "$argc_plus_output"; }
''')
    r = evaluated(p, '-v', '--count', '--count', '+o')
    assert r.returncode == 0 and r.stdout == b'1|2|1'
    assert evaluated(p, '--count=1').stderr.startswith(b'error: flag `--count` don\'t accept any value')
    assert evaluated(p, '-v', '-v').returncode == 1
    assert evaluated(p, '--output').returncode == 1


def test_options_defaults_env_and_assignment(tmp_path):
    p = source(tmp_path, '''# @option -o --output=default $OUT <FILE> Output
# @option --mode: <MODE> Mode
main() { printf '<%s>|<%s>' "$argc_output" "$argc_mode"; }
''')
    assert evaluated(p).stdout == b'<default>|<>'
    assert evaluated(p, '--output', 'x y', '--mode=fast').stdout == b'<x y>|<fast>'
    assert evaluated(p, '--mode:fast').returncode == 1
    assert evaluated(p, '--mode', 'fast').returncode == 1


def test_positional_variadic_and_shell_safe_roundtrip(tmp_path):
    p = source(tmp_path, '''# @arg head!
# @arg tail~
main() { printf '%s\\n' "$argc_head" "${argc_tail[0]}" "${argc_tail[1]}"; }
''')
    value = "$(touch SHOULD_NOT_EXIST) ' $\\\n雪"
    r = evaluated(p, value, '--', '--odd', value)
    assert r.returncode == 0 and value.encode() in r.stdout
    assert not (tmp_path / 'SHOULD_NOT_EXIST').exists()


def test_choices_and_required_validation(tmp_path):
    p = source(tmp_path, '''# @option --color[red|blue] <COLOR> Color
# @arg file! <FILE> Input
main() { :; }
''')
    bad = evaluated(p, '--color', 'RED', 'x')
    assert bad.returncode == 1 and b'possible values: red, blue' in bad.stderr
    missing = evaluated(p, '--color', 'red')
    assert b'the following required arguments were not provided' in missing.stderr
    assert evaluated(p, '--color', 'blue', 'f').returncode == 0


def test_eval_protocol_help_version_and_handler_order(tmp_path):
    p = source(tmp_path, '''# @version 2.1.0
_argc_before() { :; }
# @option --name <NAME> Name
# @cmd Child
child() { :; }
main() { :; }
_argc_after() { :; }
''', 'metadata.sh')
    r = run('--argc-eval', p, '--help')
    assert r.returncode == 0 and b"command cat >&2 <<-'EOF' " in r.stdout
    assert b'Print help' in r.stdout
    assert b'_argc_before' in run('--argc-eval', p, 'child').stdout
    assert b'argc__fn=main' in run('--argc-eval', p).stdout
    assert b'metadata 2.1.0' in evaluated(p, '--version').stderr


def test_export_order_metadata_and_parameter_shape(tmp_path):
    p = source(tmp_path, '''# @version 2.5.0
# @meta author Ada
# @meta custom some value
# @flag -v --verbose* Verbose
# @option --tags+, <TAG> Tags
# @arg input! <FILE> Input
main() { :; }
''')
    r = run('--argc-export', p)
    assert r.returncode == 0 and r.stderr == b'' and r.stdout.endswith(b'\n')
    o = json.loads(r.stdout)
    assert o['version'] == '2.5.0' and o['metadata'] == {'author':'Ada','custom':'some value'}
    assert [x['id'] for x in o['flag_options'][:2]] == ['verbose','tags']
    assert o['flag_options'][1]['delimiter'] == ','
    assert o['positionals'][0]['required'] is True


def test_export_rejects_missing_dynamic_function(tmp_path):
    p = source(tmp_path, '# @option --out=`missing_fn` Output\nmain() { :; }\n')
    r = run('--argc-export', p)
    assert r.returncode == 1 and b'missing_fn(line 1) is missing' in r.stderr


@pytest.mark.parametrize('fixture', ['build-simple','build-complex','build-dotenv','build-hooks','build-bind-env','build-required-default','build-default-subcommand','build-choice-env','build-bind-delimiter'], ids=['simple','complex','dotenv','hooks','env','required-default','default-subcommand','choice-env','delimiter'])
def test_build_golden_fixtures(fixture):
    r = run('--argc-build', FIX / f'{fixture}.sh')
    assert r.returncode == 0 and r.stderr == b''
    assert r.stdout == (FIX / f'{fixture}.golden').read_bytes()


@pytest.mark.parametrize('shell', ['bash','zsh','fish','nushell','powershell','elvish'], ids=['bash','zsh','fish','nushell','powershell','elvish'])
def test_completion_adapter_golden(shell):
    r = run('--argc-completions', shell, 'simple')
    assert r.returncode == 0 and r.stderr == b''
    assert r.stdout == (FIX / f'completion-{shell}.golden').read_bytes()


def test_completions_shell_validation_and_generic():
    assert run('--argc-completions').stderr.startswith(b'Usage: argc --argc-completions')
    assert run('--argc-completions','invalid').returncode == 1
    assert run('--argc-completions','generic').stdout == b''


def test_compgen_forgiving_protocol_and_static_candidates(tmp_path):
    p = source(tmp_path, '''# @cmd First
cmd1() { :; }
# @alias one,o
# @cmd Second
cmd2() { :; }
''')
    for words in [(), ('',), ('list',)]:
        r = run('--argc-compgen','bash',p,*words)
        assert r.returncode == 0 and r.stdout == r.stderr == b''
    r = run('--argc-compgen','generic',p,'demo','')
    assert b'cmd1\t/color:magenta' in r.stdout and b'one\t/color:magenta' in r.stdout
    assert b'\no\t' not in r.stdout and b'cmd2\t' in r.stdout and b'help\t' in r.stdout
    r = run('--argc-compgen','bad',p,'demo','')
    assert r.returncode == 0 and not r.stdout and not r.stderr


def test_compgen_assignments_and_builtin_shell_kind():
    p = source(EVAL, '# @option --mode[fast|slow] <MODE> Mode\nmain() { :; }\n', 'opts_fixture.sh')
    r = run('--argc-compgen','generic',p,'demo','--mode=s')
    assert r.stdout == b'slow\t/color:default\n'
    r = run('--argc-compgen','generic','___compgen_kind___','shell','')
    assert r.stdout == b'bash\telvish\tfish\tnushell\tpowershell\txonsh\tzsh\ttcsh\n'


def test_direct_file_kind_is_empty_and_path_kind_is_silent_directive(tmp_path):
    (tmp_path/'visible.txt').write_text('x')
    f = run('--argc-compgen','bash','___compgen_kind___','file','vis',cwd=tmp_path)
    assert f.returncode == 0 and f.stdout == f.stderr == b''
    r = run('--argc-compgen','generic','___compgen_kind___','path','vis',cwd=tmp_path)
    assert r.stdout == b'__argc_value=path\t/color:default\n'


def test_mangen_structure_and_argument_errors(tmp_path):
    p = source(tmp_path, '''# @describe Root
# @arg input! <FILE> Input
main() { :; }
# @cmd Child
child() { :; }
''', 'man-demo.sh')
    out = tmp_path/'manuals'
    r = run('--argc-mangen',p,out)
    assert r.returncode == 0 and r.stderr == b''
    pages = sorted(out.glob('*.1'))
    assert len(pages) == 2
    root = (out/'man-demo.1').read_text()
    assert '.TH MAN-DEMO 1  "man-demo 0.0.0" ' in root
    assert '.SH SYNOPSIS' in root and '.SH OPTIONS' in root
    assert run('--argc-mangen',p).stderr == b'No output dir\n'


def test_create_default_template_collision_and_custom_name(tmp_path):
    r = run('--argc-create',cwd=tmp_path)
    assert r.returncode == 0 and r.stdout == b'Argcfile.sh has been successfully created.\n'
    assert (tmp_path/'Argcfile.sh').read_text().startswith('#!/usr/bin/env bash\n\nset -e\n')
    before = (tmp_path/'Argcfile.sh').read_bytes()
    r = run('--argc-create','hello',cwd=tmp_path)
    assert r.returncode == 1 and (tmp_path/'Argcfile.sh').read_bytes() == before
    custom = tmp_path/'custom'
    r = run('--argc-create','hello',cwd=tmp_path,env={'ARGC_SCRIPT_NAME':str(custom)})
    assert r.returncode == 0 and custom.exists()


def test_script_path_and_shell_path(tmp_path):
    (tmp_path/'argcfile').write_text('#!/bin/sh\n')
    r = run('--argc-script-path',cwd=tmp_path,env={'ARGC_SCRIPT_NAME':'absent'})
    assert r.returncode == 0 and pathlib.Path(r.stdout.decode().strip()) == tmp_path/'argcfile'
    r = run('--argc-shell-path')
    assert r.returncode == 0 and r.stdout == b'/usr/bin/bash\n'
    custom = tmp_path/'not-executable'; custom.write_text('x')
    r = run('--argc-shell-path',env={'ARGC_SHELL_PATH':str(custom)})
    assert r.returncode == 0 and r.stdout == (str(custom)+'\n').encode()
    r = run('--argc-shell-path',env={'ARGC_SHELL_PATH':str(tmp_path/'missing')})
    assert r.returncode == 1 and b'Invalid ARGC_SHELL_PATH' in r.stderr


def test_task_runner_nearest_script_custom_fallback_and_exit(tmp_path):
    (tmp_path/'Argcfile.sh').write_text('echo first\nexit 7\n')
    child = tmp_path/'child'; child.mkdir()
    r = run(cwd=child,env={'ARGC_SCRIPT_NAME':'absent'})
    assert r.returncode == 7 and r.stdout == b'first\n'
    (child/'argcfile').write_text('echo near\n')
    assert run(cwd=child).stdout == b'near\n'


def test_run_preserves_arguments_and_status(tmp_path):
    p = source(tmp_path, 'printf "<%s>\\n" "$@"\nexit 9\n')
    r = run('--argc-run',p,'a b','$(echo nope)','雪')
    assert r.returncode == 9 and r.stdout == '<a b>\n<$(echo nope)>\n<雪>\n'.encode()
    assert run('--argc-run').stderr == b'No script file provided\n'


def test_parallel_setup_and_raw_groups(tmp_path):
    p = source(tmp_path, '''eval "$(argc --argc-eval "$0" "$@")"
# @cmd Work
work() { printf '[%s][%s]\\n' "$1" "$2"; }
# @cmd Fail
fail() { echo bad >&2; return 1; }
''')
    r = run('--argc-parallel',p,'work','a b','x',':::',':::', 'fail',':::',cwd=tmp_path)
    assert r.returncode == 1 and r.stdout == b'[a b][x]\n' and r.stderr == b'bad\n'
    assert run('--argc-parallel',p).stderr.startswith(b'Usage: argc --argc-parallel')
    plain = source(tmp_path,'echo plain\n','plain.sh')
    r=run('--argc-parallel',plain,'x')
    assert r.returncode == 1 and b'Parallel only available' in r.stderr


def test_metadata_requirements_and_default_subcommand_is_not_dispatch(tmp_path):
    p = source(tmp_path, '''# @arg one
# @meta default-subcommand child
# @cmd Child
child() { :; }
''')
    assert b'[ONE]' in evaluated(p,'--help').stderr
    bad = evaluated(p,'value')
    assert bad.returncode == 1 and b'requires a subcommand' in bad.stderr


def test_inherit_override_options_and_unknown_option(tmp_path):
    p=source(tmp_path, '''# @meta inherit-flag-options
# @option --global[a|b] <GLOBAL> Parent
# @cmd Child
# @option --global[x|y] <GLOBAL> Child
child() { :; }
''')
    assert evaluated(p,'--global','a','child').returncode == 0
    assert b'possible values: a, b' in evaluated(p,'--global','x','child').stderr
    assert evaluated(p,'child','--global','x').returncode == 0
    assert b'possible values: x, y' in evaluated(p,'child','--global','a').stderr
    q=source(tmp_path,'# @option --oa <X>\nmain() { echo "$argc__positionals"; }\n','q.sh')
    r=evaluated(q,'--oa','v1','v2'); assert r.returncode == 0
    assert evaluated(q,'--oa','v1','--odd').returncode == 1


def test_env_required_defaults_and_flag_boolean(tmp_path):
    p=source(tmp_path, '''# @env TOKEN! Required
# @flag --verbose $VERBOSE Verbose
main() { printf '%s|%s' "$TOKEN" "$argc_verbose"; }
''')
    assert b'required environments' in evaluated(p).stderr
    assert evaluated(p,env={'TOKEN':'','VERBOSE':'true'}).stdout == b'|1'
    assert evaluated(p,'--verbose',env={'TOKEN':'ok','VERBOSE':'nonsense'}).stdout == b'ok|1'
    assert evaluated(p,env={'TOKEN':'ok','VERBOSE':'false'}).stdout == b'ok|'


def test_numeric_positionals_terminator_and_too_many(tmp_path):
    p=source(tmp_path,'# @arg count!\nmain() { printf "%s" "$argc_count"; }\n')
    assert evaluated(p,'-456').stdout == b'-456'
    q=source(tmp_path,'# @flag --yes\n# @arg head!\n# @arg tail~\nmain() { printf "%s|%s|%s" "$argc_yes" "$argc_head" "${argc_tail[0]}"; }\n','term.sh')
    assert evaluated(q,'start','--','--yes').stdout == b'|start|--'
    x=source(tmp_path,'# @arg one!\nmain() { :; }\n','finite.sh')
    assert evaluated(x,'a','b').returncode == 1
