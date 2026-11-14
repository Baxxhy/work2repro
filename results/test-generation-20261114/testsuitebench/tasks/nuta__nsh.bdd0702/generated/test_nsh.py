import os
import pathlib
import re
import subprocess

import pytest


ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')


def invoke(*args, cwd=None, env=None, input_bytes=None, timeout=8):
    e = os.environ.copy()
    e.update({'HOME': str(cwd or ROOT), 'PATH': '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin'})
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or ROOT, env=e,
                          input=input_bytes, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def cmd(source, *opts, **kw):
    return invoke(*opts, '-c', source, '--norc', **kw)


def test_version_exact():
    p = invoke('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'0.4.2\n', b'')


def test_help_exact_and_help_precedes_version():
    p = invoke('--help', '--version')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'nsh 0.4.2\n') and p.stdout.endswith(b'<FILE>    The file to be executed\n')


def test_invalid_cli_precedes_help():
    p = invoke('--wat', '--version', '--help')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(b"error: Found argument '--wat'")


def test_option_parsing_command_precedence():
    p = invoke('-c', 'echo command', '--norc', '--', 'ignored')
    assert (p.returncode, p.stdout) == (0, b'command\n')


def test_empty_and_final_status():
    assert (cmd('').returncode, cmd('').stdout) == (0, b'')
    p = cmd('false; echo later; false')
    assert (p.returncode, p.stdout) == (1, b'later\n')


def test_syntax_error_is_atomic():
    p = cmd('echo forbidden; if true; then echo missing')
    assert p.returncode == 255 and p.stdout == b''
    assert b'nsh: parse error:' in p.stderr


def test_semicolon_and_comments():
    p = cmd('; ; # comment\necho yes; ;')
    assert (p.returncode, p.stdout) == (0, b'yes\n')


def test_adjacent_semicolons_rejected_atomically():
    p = cmd('echo forbidden;;; echo later')
    assert p.returncode == 255 and p.stdout == b'' and b'parse error' in p.stderr


def test_quotes_and_expansion_spans():
    p = cmd('x=hello; y=world; printf "<%s>|<%s>|<%s>|<%s>\\n" "$x$y" $x$y "" ab" cd"ef')
    assert p.returncode == 0 and p.stdout == b'<helloworld>|<hello>|<world>|<>\n'


def test_default_parameter_defect():
    p = cmd('unset a; b=""; c=keep; printf "%s:%s:%s|" "${a:=A}" "${b:=B}" "${c:=C}"; echo $a$b$c')
    assert (p.returncode, p.stdout) == (0, b'A::keep|A  keep\n')


def test_byte_length_and_substitution_trim():
    p = cmd('v=雪ab; echo ${#v}; x=$(printf "one\\ntwo\\n"); echo "$x"')
    assert (p.returncode, p.stdout) == (0, '5\nonetwo\n'.encode())


def test_arithmetic_and_postincrement():
    p = cmd('x=5; echo $((x++)):$x; echo $((-(8/3)))')
    assert p.returncode == 0 and p.stdout == b'6: 6\n2\n'


def test_arithmetic_division_zero_panics():
    p = cmd('echo $((5/0))')
    assert p.returncode == 101 and p.stdout == b''
    assert p.stderr.startswith(b'nsh: panicked at src/eval.rs:') and p.stderr.endswith(b'https://github.com/nuta/nsh/issues\n')


def test_command_lookup_and_list_operators():
    p = cmd('false && echo no; true || echo yes; missing_cmd')
    assert p.returncode == 1 and p.stdout == b'yes\n'
    assert p.stderr == b"nsh: command not found `missing_cmd'\n"


def test_pipeline_last_status():
    p = cmd('printf x | cat | grep x')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'x\n', b'')


def test_variables_exports_unset_and_env_bytes():
    p = cmd('echo "$ODD"; export NEW=exported; /bin/sh -c "printf %s:$NEW"; unset NEW; echo "$NEW"', env={'ODD': 'a=b c'})
    assert p.returncode == 0 and p.stdout == b'a=b c\nexported:\n'


def test_pwd_not_synthesized_and_cd_does_not_update_vars(tmp_path):
    p = cmd('cd /; printf "<%s>|<%s>|" "$PWD" "$OLDPWD"; pwd', cwd=tmp_path, env={'PWD': '', 'OLDPWD': ''})
    assert p.returncode == 0 and p.stdout == b'<>|<>|/\n'


def test_file_mode_shebang_and_zero(tmp_path):
    f = tmp_path / 'script'
    f.write_text('#!/not/a/real/interpreter\necho "$0"\n')
    p = invoke(str(f), '--norc', cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == (str(f) + '\n').encode()


def test_file_mode_nonexistent_panics(tmp_path):
    p = invoke(str(tmp_path / 'missing'), '--norc', cwd=tmp_path)
    assert p.returncode == 101 and p.stdout == b''
    assert p.stderr.startswith(b'nsh: panicked at src/main.rs:') and b'failed to open the file' in p.stderr


def test_rc_scripts_order_and_norc(tmp_path):
    home = tmp_path / 'home'; xdg = tmp_path / 'xdg'
    (home).mkdir(); (xdg / 'nsh').mkdir(parents=True)
    (home / '.nshrc').write_text('x=first; echo first\n')
    (xdg / 'nsh' / 'nshrc').write_text('x=second; echo second\n')
    env = {'HOME': str(home), 'XDG_CONFIG_HOME': str(xdg)}
    p = invoke('-c', 'echo $x', cwd=tmp_path, env=env)
    assert p.returncode == 0 and p.stdout == b'first\nsecond\nsecond\n'
    q = invoke('-c', 'echo ${x-unset}', '--norc', cwd=tmp_path, env=env)
    assert q.stdout == b'unset\n'


def test_history_created_and_existing_preserved(tmp_path):
    home = tmp_path / 'h'; home.mkdir()
    p = invoke('-c', 'true', '--norc', cwd=tmp_path, env={'HOME': str(home)})
    h = home / '.nsh_history'
    assert p.returncode == 0 and h.is_file() and h.read_bytes() == b''
    h.write_bytes(b'0\t/tmp\tok\n')
    invoke('-c', 'true', '--norc', cwd=tmp_path, env={'HOME': str(home)})
    assert h.read_bytes() == b'0\t/tmp\tok\n'


def test_history_malformed_warns_with_line_number(tmp_path):
    home = tmp_path / 'h'; home.mkdir(); (home / '.nsh_history').write_bytes(b'0\t/tmp\tok\nbroken\n')
    p = invoke('-c', 'echo yes', '--norc', cwd=tmp_path, env={'HOME': str(home)})
    assert p.returncode == 0 and p.stdout == b'yes\n'
    assert p.stderr == b'nsh: nsh: warning: failed to parse ~/.nsh_history: at line 2\n'


def test_redirections_append_and_stderr(tmp_path):
    p = cmd('echo one >a; echo two >>a; echo err 2>e', cwd=tmp_path)
    assert p.returncode == 0 and (tmp_path / 'a').read_bytes() == b'one\ntwo\n'
    assert (tmp_path / 'e').read_bytes() == b''


def test_redirection_failure_does_not_run_command(tmp_path):
    p = cmd('echo nope >/absent/path/file', cwd=tmp_path)
    assert p.returncode != 0
    assert p.stdout == b''


def test_groups_functions_and_local_scope():
    p = cmd('x=outer; f() { local x=inner; echo $x; }; f; echo $x; { y=brace; }; (y=sub); echo $y')
    assert p.returncode == 0 and p.stdout == b'inner\nouter\nbrace\n'


def test_if_while_for_and_continue():
    p = cmd('i=0; while test $i -lt 3; do i=$((i+1)); if test $i -eq 2; then continue; fi; echo $i; done; for x in a b; do echo $x; done')
    assert p.returncode == 0 and p.stdout == b'1\n3\na\nb\n'


def test_elif_defect():
    p = cmd('x=10; if test $x -eq 5; then echo five; elif test $x -eq 10; then echo ten; fi')
    assert p.returncode == 0 and p.stdout == b'five\n'


def test_function_arguments_return_and_shift():
    p = cmd('f() { echo $#:$1:$2; shift; echo $#:$1; return 42; }; f one two; echo status:$?')
    assert p.returncode == 0 and p.stdout == b'2: one: two\n1: one\nstatus: 0\n'


def test_test_builtin_and_bracket_error():
    p = cmd('test x = x; echo $?; [ x = y ]; echo $?')
    assert p.returncode == 0 and b'0' in p.stdout and b'1' in p.stdout
    q = cmd('[ x = x')
    assert q.returncode == 2 and q.stdout == b'' and q.stderr == '[: missing ‘]’\n'.encode()


def test_echo_options_and_escapes():
    p = cmd('echo -ne "a\\nb\\t\\e"; echo -E "\\n"')
    assert p.returncode == 0 and p.stdout == b'a\nb\t\x1b\\n\n'


def test_cd_failure_and_directory_stack(tmp_path):
    (tmp_path / 'a').mkdir(); (tmp_path / 'b').mkdir()
    p = cmd('cd a; cd b; cd -; pwd; cd -; pwd', cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == (str(tmp_path / 'a') + '\n' + str(tmp_path) + '\n').encode()
    q = cmd('cd absent', cwd=tmp_path)
    assert q.returncode == 1 and q.stderr.startswith(b'nsh: cd: No such file or directory')


def test_source_and_eval(tmp_path):
    f = tmp_path / 'src'; f.write_text('z=loaded\n')
    p = cmd(f'source {f}; eval "echo $z"', cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == b'loaded\n'


def test_alias_and_rehash():
    p = cmd("alias show='echo $x'; show extra")
    assert p.returncode == 0 and p.stdout == b'$x extra\n'
    q = cmd('rehash')
    assert q.returncode == 0 and q.stdout == b''


def test_read_assigns_and_eof_keeps_value():
    p = cmd('read x; echo $x', input_bytes=b' lead  text  \n')
    assert p.returncode == 0 and p.stdout == b' lead  text\n'
    q = cmd('x=old; read x; printf "<%s>:%s" "$x" "$?"', input_bytes=b'')
    assert q.returncode == 0 and q.stdout == b'<old>:1'


def test_set_errexit_and_nounset():
    p = cmd('set -e; false; echo no')
    assert p.returncode == 1 and p.stdout == b''
    q = cmd('set -u; echo $MISSING')
    assert q.returncode == 1 and q.stdout == b'' and q.stderr == b"nsh: undefined variable `MISSING'\n"


def test_no_execute_mode():
    p = cmd('set -n; echo no')
    assert p.returncode == 0 and p.stdout == b''


def test_exit_modulo_and_exec_noop():
    assert cmd('exec; echo yes; exit 257').stdout == b'yes\n'
    p = cmd('exit 257; echo no')
    assert p.returncode == 1 and p.stdout == b''


def test_non_tty_stdin_is_not_executed():
    p = invoke(input_bytes=b'echo should-not-run\n')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'', b'nsh: warning: stdout is not a tty\n')


def test_unmatched_glob_and_quoted_glob(tmp_path):
    p = cmd('echo no-such-*', cwd=tmp_path)
    assert p.returncode == 1 and p.stderr == b'nsh: error: no matches\n'
    q = cmd('echo "no-such-*"', cwd=tmp_path)
    assert q.returncode == 0 and q.stdout == b'no-such-*\n'


def test_case_source_order_and_substring_match():
    p = cmd('case abcd in ab) echo first;; abcd) echo second;; esac')
    assert p.returncode == 0 and p.stdout == b'first\n'


def test_background_job_pid_and_wait():
    p = cmd("/bin/sh -c 'echo child' & printf 'pid:%s\\n' $!; wait", timeout=10)
    assert p.returncode == 0 and b'child\n' in p.stdout and re.search(rb'pid:[1-9][0-9]*\n', p.stdout)
    assert b'[1] Done:' in p.stdout and p.stderr == b''


def test_stress_long_pipeline_and_unicode(tmp_path):
    data = '雪' * 10000
    (tmp_path / 'unicode').write_text(data)
    p = cmd('cat unicode | wc -c', cwd=tmp_path)
    assert p.returncode == 0 and p.stdout.strip() == str(len(data.encode())).encode()
