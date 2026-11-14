import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')
ESC = b'\x1b'
RED = ESC + b'[0;41m'
GREEN = ESC + b'[0;42m'
RESET = ESC + b'[m'
CMD = ESC + b'[0;38;2;192;0;128m'
VAR = ESC + b'[0;38;2;63;127;207m'
KW = ESC + b'[0;1m'


def run(*args, data=None, cwd=None, env=None):
    return subprocess.run([str(EXE), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=env)


def test_no_arguments_does_not_consume_stdin():
    p = run(data=b'echo $x\n')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'', b'')


def test_empty_operand_reads_stdin_and_deduplicates_it():
    p = run('--transform', '', '', data=b'echo $x\n')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'echo "$x"\n', b'')


def test_version_exact():
    p = run('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'4.3.1\n', b'')


def test_help_exact_block():
    expected = (b'Shellharden: The corrective bash syntax highlighter.\n\n'
      b'Usage:\n\tshellharden [options] [files]\n\tcat files | shellharden [options] \'\'\n\n'
      b'Shellharden is a syntax highlighter and a tool to semi-automate the rewriting\n'
      b'of scripts to ShellCheck conformance, mainly focused on quoting.\n\n'
      b'The default mode of operation is like `cat`, but with syntax highlighting in\n'
      b'foreground colors and suggestive changes in background colors.\n\nOptions:\n'
      b'\t--suggest         Output a colored diff suggesting changes.\n'
      b'\t--syntax          Output syntax highlighting with ANSI colors.\n'
      b'\t--syntax-suggest  Diff with syntax highlighting (default mode).\n'
      b'\t--transform       Output suggested changes.\n\t--check           No output; exit with 2 if changes are suggested.\n'
      b'\t--replace         Replace file contents with suggested changes.\n'
      b'\t--                Don\'t treat further arguments as options.\n'
      b'\t-h|--help         Show help text.\n\t--version         Show version.\n\n'
      b'The changes suggested by Shellharden inhibits word splitting and indirect\n'
      b'pathname expansion. This will make your script ShellCheck compliant in terms of\n'
      b'quoting. Whether your script will work afterwards is a different question:\n'
      b'If your script was using those features on purpose, it obviously won\'t anymore!\n\n'
      b'Every script is possible to write without using word splitting or indirect\n'
      b'pathname expansion, but it may involve doing things differently.\n'
      b'See the accompanying file how_to_do_things_safely_in_bash.md or online:\n'
      b'https://github.com/anordal/shellharden/blob/master/how_to_do_things_safely_in_bash.md\n\n')
    p = run('--help')
    assert (p.returncode, p.stdout, p.stderr) == (0, expected, b'')


@pytest.mark.parametrize('option', ['-x', '--transfrom', '--name=value', '-long', '---long'], ids=['short','typo','equals','long-short','triple-dash'])
def test_invalid_options_stop_with_exact_error(option):
    p = run(option)
    assert (p.returncode, p.stdout, p.stderr) == (3, b'', option.encode() + b': No such option.\n')


def test_invalid_option_before_help_is_error():
    p = run('--bad', '--help')
    assert p.returncode == 3 and p.stdout == b'' and b'No such option' in p.stderr


def test_dash_is_not_stdin_and_double_dash_quotes_options_as_paths(tmp_path):
    p = run('-')
    assert p.returncode == 3 and p.stdout == b''
    file = tmp_path / '--help'
    file.write_bytes(b'echo $v\n')
    p = run('--transform', '--', str(file))
    assert p.returncode == 0 and p.stdout == b'echo "$v"\n'


def test_bare_transform_is_filename_and_paths_with_spaces_work(tmp_path):
    f = tmp_path / 'transform with spaces'
    f.write_bytes(b'echo $v\n')
    p = run('--transform', str(f))
    assert (p.returncode, p.stdout, p.stderr) == (0, b'echo "$v"\n', b'')


def test_modes_are_forward_only_and_later_modes_override(tmp_path):
    f = tmp_path / 'f'; f.write_bytes(b'echo $v\n')
    p = run(str(f), '--transform', str(f))
    assert p.returncode == 0
    # First operand renders in default mode; second in transform mode.
    assert p.stdout.count(b'echo ') == 2 and b'\x1b[' in p.stdout
    p = run('--transform', str(f))
    assert p.stdout == b'echo "$v"\n'


def test_help_and_version_do_not_suppress_later_files(tmp_path):
    f = tmp_path / 'f'; f.write_bytes(b'echo ok\n')
    p = run('--version', str(f))
    assert p.returncode == 0 and p.stdout.startswith(b'4.3.1\n') and p.stdout.endswith(b'echo ok\n')


@pytest.mark.parametrize('source,expected', [
    (b'echo $a $b\n', b'echo "$a" "$b"\n'),
    (b'$cmd arg\n', b'"$cmd" arg\n'),
    (b'echo $a$b\n', b'echo "$a$b"\n'),
    (b'echo $dir/$subdir/$file.txt\n', b'echo "$dir/$subdir/$file".txt\n'),
    (b'echo path/$file/more\n', b'echo path/"$file"/more\n'),
    (b'echo foo$bar\n', b'echo foo"$bar"\n'),
    (b'echo ${foo}\n', b'echo "$foo"\n'),
    (b'echo ${foo}bar\n', b'echo "${foo}"bar\n'),
    (b'echo a${b}c\n', b'echo a"${b}"c\n'),
    (b'echo $a"string"\n', b'echo "${a}string"\n'),
    (b'echo "$a"$b\n', b'echo "$a""$b"\n'),
    (b'echo ${0}\n', b'echo "${0}"\n'),
    (b'echo $*\n', b'echo "$@"\n'),
    (b'echo $@\n', b'echo "$@"\n'),
])
def test_core_word_rewrites(source, expected):
    p = run('--transform', '', data=source)
    assert p.returncode == 0 and p.stdout == expected


def test_eof_simple_variable_is_braced_and_no_newline_added():
    p = run('--transform', '', data=b'echo $value')
    assert p.stdout == b'echo "${value}"'


def test_rewrite_is_idempotent():
    first = run('--transform', '', data=b'echo $a ${b} $(cat $file)\n')
    second = run('--transform', '', data=first.stdout)
    assert first.returncode == second.returncode == 0 and second.stdout == first.stdout


@pytest.mark.parametrize('source,expected', [
    (b'value=$other\n', b'value=$other\n'),
    (b'local value=$other\n', b'local value=$other\n'),
    (b'echo $(( $a + b ))\n', b'echo $(( $a + b ))\n'),
    (b'[[ $a == *.txt ]]\n', b'[[ $a == *.txt ]]\n'),
    (b'case $value in $pattern) :;; esac\n', b'case $value in $pattern) :;; esac\n'),
    (b'array=($list)\n', b'array=("$list")\n'),
    (b'array=($(list))\n', b'array=("$(list)")\n'),
    (b'declare value=$other\n', b'declare value=$other\n'),
    (b'declare -x value=$other\n', b'declare -x value="$other"\n'),
    (b'x=$(cat $file)\n', b'x=$(cat "$file")\n'),
    (b'x=${outer:-$(cat $file)}\n', b'x=${outer:-$(cat $file)}\n'),
    (b'echo ${outer:-${inner:-$(cat $file)}}\n', b'echo "${outer:-${inner:-$(cat $file)}}"\n'),
])
def test_context_specific_quoting(source, expected):
    p = run('--transform', '', data=source)
    assert p.returncode == 0 and p.stdout == expected


@pytest.mark.parametrize('source,expected', [
    (b'echo $0 $9 $? $# $$ $! $-\n', b'echo "$0" "$9" $? $# $$ $! "$-"\n'),
    (b'echo ${v:-$x} ${v#pat} ${v^^}\n', b'echo "${v:-$x}" "${v#pat}" "${v^^}"\n'),
    (b'echo ${#v} ${!v} ${!array[@]}\n', b'echo ${#v} ${!v} ${!array[@]}\n'),
    (b'echo ${a[index]} ${a[@]} ${a[@]:1:2}\n', b'echo "${a[index]}" "${a[@]}" "${a[@]:1:2}"\n'),
    (b'echo ${a[*]}\n', b'echo "${a[@]}"\n'),
    (b'echo "${0}"\n', b'echo "${0}"\n'),
])
def test_parameter_and_array_forms(source, expected):
    p = run('--transform', '', data=source)
    assert p.returncode == 0 and p.stdout == expected


def test_for_list_sole_expansion_is_array_form():
    p = run('--transform', '', data=b'for x in $items; do echo $x; done\n')
    assert p.stdout == b'for x in "${items[@]}"; do echo "$x"; done\n'


def test_for_list_multiple_expansions_keep_individual_words():
    p = run('--transform', '', data=b'for x in $a $b; do :; done\n')
    assert p.stdout == b'for x in "$a" "$b"; do :; done\n'


@pytest.mark.parametrize('source,expected', [
    (b'echo $(date)\n', b'echo "$(date)"\n'),
    (b'echo $(cat $file)\n', b'echo "$(cat "$file")"\n'),
    (b'echo $(outer $(inner $x))\n', b'echo "$(outer "$(inner "$x")")"\n'),
    (b'echo `pwd`\n', b'echo "$PWD"\n'),
    (b'dir=$(pwd)\n', b'dir=$PWD\n'),
    (b'echo $(pwd)/bin\n', b'echo "$PWD"/bin\n'),
    (b'echo $(pwd)extra\n', b'echo "${PWD}"extra\n'),
    (b'dir=`uname -a`\n', b'dir=`uname -a`\n'),
    (b'dir=`pwd`suffix\n', b'dir=`pwd`suffix\n'),
])
def test_command_substitution_and_pwd(source, expected):
    p = run('--transform', '', data=source)
    assert p.returncode == 0 and p.stdout == expected


def test_process_substitution_contents_are_transformed():
    p = run('--transform', '', data=b'cat <(echo $x)\n')
    assert p.stdout == b'cat <(echo "$x")\n'


def test_redirection_and_here_string_words():
    p = run('--transform', '', data=b'cat < $input > $output\ncat <<< $value\n')
    assert p.stdout == b'cat < "$input" > "$output"\ncat <<< "$value"\n'


def test_heredoc_body_is_literal_but_command_is_rewritten():
    src = b'cat > $out <<\'EOF\'\n$x $(cmd)\nEOF\necho $y\n'
    p = run('--transform', '', data=src)
    assert p.stdout == b'cat > "$out" <<\'EOF\'\n$x $(cmd)\nEOF\necho "$y"\n'


def test_heredoc_redirector_disables_later_same_line_words():
    p = run('--transform', '', data=b'cat <<EOF $arg\n$x\nEOF\n')
    assert p.stdout == b'cat <<EOF $arg\n$x\nEOF\n'


def test_multiple_heredoc_limited_first_body_only():
    src = b"cat <<'ONE' <<-TWO\n$x\nONE\n\t$y\n\tTWO\n"
    p = run('--transform', '', data=src)
    assert p.stdout == b"cat <<'ONE' <<-TWO\n$x\nONE\n\t\"$y\"\n\tTWO\n"


def test_suggest_exact_inline_diff():
    p = run('--suggest', '', data=b'echo $foo\n')
    assert p.stdout == b'echo ' + GREEN + b'"' + RESET + b'$foo' + GREEN + b'"' + RESET + b'\n'


def test_suggest_removal_addition_boundary_is_minimal():
    p = run('--suggest', '', data=b'echo ${var}\n')
    assert p.stdout == b'echo ' + GREEN + b'"' + RESET + b'$' + RED + b'{' + RESET + b'var' + RED + b'}' + GREEN + b'"' + RESET + b'\n'


def test_syntax_exact_command_and_variable_palette():
    p = run('--syntax', '', data=b'echo $foo\n')
    assert p.stdout == CMD + b'echo' + RESET + b' ' + VAR + b'$foo' + RESET + b'\n'


def test_default_mode_exact_syntax_diff_overlay():
    p = run('', data=b'echo $foo\n')
    assert p.stdout == CMD + b'echo' + RESET + b' ' + GREEN + b'"' + CMD + b'$foo' + GREEN + b'"' + RESET + b'\n'


def test_check_status_silent_changed_and_canonical():
    changed = run('--check', '', data=b'echo $x\n')
    canonical = run('--check', '', data=b'echo "$x"\n')
    assert (changed.returncode, changed.stdout, changed.stderr) == (2, b'', b'')
    assert (canonical.returncode, canonical.stdout, canonical.stderr) == (0, b'', b'')


def test_concatenation_multiple_operands_and_mode_switch(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; a.write_bytes(b'echo a\n'); b.write_bytes(b'echo b\n')
    p=run('--transform', str(a), str(b))
    assert p.stdout == b'echo a\necho b\n'


def test_environment_and_rc_do_not_override_arguments(tmp_path):
    f=tmp_path/'f'; f.write_bytes(b'echo $v\n')
    (tmp_path/'.shellhardenrc').write_text('--syntax\n')
    e=os.environ.copy(); e.update({'SHELLHARDEN_MODE':'syntax','NO_COLOR':'1','CLICOLOR':'0','SHELL':'/bin/false'})
    p=run('--transform',str(f),cwd=tmp_path,env=e)
    assert p.stdout == b'echo "$v"\n' and p.stderr == b''


def test_missing_file_diagnostic_and_later_file_continues(tmp_path):
    missing=tmp_path/'missing'; good=tmp_path/'good'; good.write_bytes(b'echo $v\n')
    p=run('--transform',str(missing),str(good))
    assert p.returncode == 1 and p.stdout == b'echo "$v"\n'
    assert p.stderr == f'{missing}: No such file or directory (os error 2)\n'.encode()


def test_check_missing_file_reports_io_error():
    p=run('--check','/workspace/eval/definitely-missing')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'/workspace/eval/definitely-missing: No such file or directory (os error 2)\n'


def test_directory_diagnostic_and_rendering_newline(tmp_path):
    p=run('--transform',str(tmp_path))
    assert p.returncode == 1 and p.stdout == b'\n'
    assert p.stderr == f'{tmp_path}: Is a directory (os error 21)\n'.encode()
    p=run('--check',str(tmp_path))
    assert p.returncode == 1 and p.stdout == b''


@pytest.mark.parametrize('source', [b"echo 'open", b'echo "open', b'echo $(open', b'echo $((1+2)', b'echo ${v', b'[[ x', b'cat <<EOF\nx\n', b'echo x\\'])
def test_unexpected_eof_diagnosed_with_extra_newline(source):
    p=run('--transform','',data=source)
    assert p.returncode == 1 and p.stdout == source + b'\n'
    assert p.stderr.startswith(b': Unexpected end of file\n')
    assert b'sytactic scopes.' in p.stderr


def test_check_parse_issue_is_silent_status_two():
    p=run('--check','',data=b"echo 'open")
    assert (p.returncode,p.stdout,p.stderr)==(2,b'',b'')


def test_replace_success_preserves_mode_and_updates_content(tmp_path):
    f=tmp_path/'script'; f.write_bytes(b'#!/bin/bash\necho $v\n'); f.chmod(0o751)
    p=run('--replace',str(f))
    assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'')
    assert f.read_bytes()==b'#!/bin/bash\necho "$v"\n' and f.stat().st_mode & 0o777 == 0o751


def test_replace_follows_symlink_and_is_idempotent(tmp_path):
    target=tmp_path/'target'; link=tmp_path/'link'; target.write_bytes(b'echo $v\n'); link.symlink_to(target)
    p=run('--replace',str(link)); assert p.returncode==0 and link.is_symlink()
    assert target.read_bytes()==b'echo "$v"\n'
    p=run('--replace',str(link)); assert p.returncode==0 and target.read_bytes()==b'echo "$v"\n'


def test_replace_eof_braces_without_final_newline(tmp_path):
    f=tmp_path/'f'; f.write_bytes(b'echo $value')
    p=run('--replace',str(f))
    assert p.returncode==0 and p.stdout==b'' and f.read_bytes()==b'echo "${value}"'


def test_replace_parse_failure_leaves_file_unchanged(tmp_path):
    f=tmp_path/'f'; original=b"echo 'open"; f.write_bytes(original)
    p=run('--replace',str(f))
    assert p.returncode==1 and p.stdout==b'' and f.read_bytes()==original


def test_replace_batch_processes_files_after_error(tmp_path):
    bad=tmp_path/'bad'; good=tmp_path/'good'; bad.write_bytes(b"echo 'x"); good.write_bytes(b'echo $v\n')
    p=run('--replace',str(bad),str(good))
    assert p.returncode==1 and good.read_bytes()==b'echo "$v"\n' and bad.read_bytes()==b"echo 'x"


def test_replace_stdin_writes_to_stdout():
    p=run('--replace','',data=b'echo $x\n')
    assert (p.returncode,p.stdout,p.stderr)==(0,b'echo "$x"\n',b'')


def test_replace_preserves_crlf_unicode_and_comments(tmp_path):
    f=tmp_path/'f'; f.write_bytes('#!/bin/bash\r\n# café\r\necho $x # note\r\n'.encode())
    p=run('--replace',str(f))
    assert p.returncode==0
    assert f.read_bytes()=='#!/bin/bash\r\n# café\r\necho "$x" # note\r\n'.encode()


def test_long_name_streaming_boundary_is_well_formed():
    name=b'x'*1000
    p=run('--transform','',data=b'echo $'+name+b'\n')
    expected=b'echo "${'+name[:127]+b'}'+(name[127:895]+b'}')+name[895:]+b'}"\n'
    assert p.stdout==expected


def test_10000_byte_named_and_stdin_boundary(tmp_path):
    src=b'echo $'+b'x'*10000+b'\n'; f=tmp_path/'long'; f.write_bytes(src)
    stdin=run('--transform','',data=src); named=run('--transform',str(f))
    assert len(stdin.stdout)==len(named.stdout)==10089
    assert stdin.stdout != named.stdout and stdin.stdout[:8257]==named.stdout[:8257]
    replaced=run('--replace',str(f)); assert replaced.returncode==0 and f.read_bytes()==named.stdout


def test_unbraced_multidigit_positional_is_fatal():
    p=run('--transform','',data=b'echo $10\n')
    assert p.returncode==1 and p.stdout==b'echo \n'
    assert p.stderr.startswith(b': Unsupported syntax: Syntactic pitfall\necho $10\n     ^^^\n')
    assert b'fist' in p.stderr and b'${10}' in p.stderr


def test_braced_multidigit_positional_is_supported():
    p=run('--transform','',data=b'echo ${10}\n')
    assert p.returncode==0 and p.stdout==b'echo "${10}"\n'


def test_boolean_tests_and_case_rewrites():
    src=b'[ -z $v ]\ntest -n "$v"\n[ x$foo = xbar ]\n[ x$a = y ]\ncase $v in x|$pattern) echo $x;; esac\n'
    p=run('--transform','',data=src)
    assert p.stdout==b'[ "$v" = "" ]\ntest "$v" != ""\n[ "$foo" = bar ]\n[ x"$a" = y ]\ncase $v in x|$pattern) echo "$x";; esac\n'


def test_case_missing_terminator_inserts_double_semicolon():
    p=run('--transform','',data=b'case $x in a) echo $y esac\n')
    assert p.stdout==b'case $x in a) echo "$y" ;; esac\n'


def test_basic_control_structures_preserve_structure_and_quote_local_words():
    src=b'if [ -f "$file" ]; then\n  for i in 1 2; do echo $i; done\nfi\n'
    p=run('--transform','',data=src)
    assert p.stdout==b'if [ -f "$file" ]; then\n  for i in 1 2; do echo "$i"; done\nfi\n'

