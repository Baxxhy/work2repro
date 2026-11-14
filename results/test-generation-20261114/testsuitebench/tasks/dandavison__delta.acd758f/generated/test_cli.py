import os, subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')
BASE_ENV = {**os.environ, 'NO_COLOR':'1', 'TERM':'dumb', 'COLUMNS':'80', 'DELTA_PAGER':'cat'}

def run(*args, data=b'', env=None, cwd=None):
    e = dict(BASE_ENV); e.update(env or {})
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=cwd)

def visible(b):
    import re
    return re.sub(rb'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))', b'', b).decode('utf-8','replace')

def test_empty_and_plain_passthrough():
    assert run().returncode == 0 and run().stdout == b''
    p=run(data=b'ordinary text\nsecond line\n')
    assert p.returncode == 0 and b'ordinary text\nsecond line\n' in p.stdout

def test_version_alias_precedes_bad_operands():
    for flag in ('--version','-V'):
        p=run(flag,'extra','operands')
        assert (p.returncode,p.stdout,p.stderr)==(0,b'delta 0.18.2\n',b'')

def test_help_contract_and_short_help():
    p=run('--help'); q=run('-h')
    assert p.returncode==q.returncode==0 and not p.stderr and not q.stderr
    assert p.stdout.startswith(b'A viewer for git and diff output\n\nUsage: delta [OPTIONS] [MINUS_FILE] [PLUS_FILE]\n')
    for s in (b'Arguments:',b'Options:',b'--show-config',b'--show-syntax-themes',b'--generate-completion',b'Git config',b'Features',b'Styles',b'Colors',b'Line Numbers',b'Support',b"delta -h"):
        assert s in p.stdout
    assert b'Options:' in q.stdout and b'--show-colors' in q.stdout and b"see more with '--help'" in q.stdout and len(q.stdout)<len(p.stdout)

def test_parser_errors_and_option_grammar():
    cases=[(['--not-an-option'],b"unexpected argument '--not-an-option' found"),(['--width'],b'value is required'),(['--width','80','--width','90'],b'cannot be used multiple times'),(['a','b','c'],b'unexpected argument ')]
    for args, msg in cases:
        p=run(*args); assert p.returncode==2 and msg in p.stderr and b'Usage: executable' in p.stderr
    assert run('-ns').returncode==run('-n','-s').returncode==0
    assert run('--dark','--light').returncode==2

def test_options_accept_documented_types():
    args=['--color-only','--dark','--diff-highlight','--hyperlinks','--line-numbers','--navigate','--no-gitconfig','--paging=never','--true-color=never','--grep-output-type=classic','--inspect-raw-lines=false','--line-fill-method=ansi','--tabs=0','--max-line-length=0','--max-line-distance=-1','--wrap-max-lines=unlimited','--wrap-right-percent=50','--width=variable','--file-style=blue','--default-language=python']
    p=run(*args); assert p.returncode==0, p.stderr
    for arg in ('--paging=invalid','--inspect-raw-lines=invalid','--generate-completion=bad'):
        p=run(arg); assert p.returncode==2 and b'possible values' in p.stderr

def test_config_precedence_and_show_config(tmp_path):
    cfg=tmp_path/'cfg'; cfg.write_text('[delta]\nfile-style = omit\nline-numbers = true\n')
    p=run('--config',str(cfg),'--file-style=blue','--show-config')
    assert p.returncode==0 and b'line-numbers' in p.stdout and b'blue' in p.stdout
    p=run('--config',str(cfg),'--no-gitconfig','--show-config')
    assert p.returncode==0
    bad=tmp_path/'bad'; bad.write_text('not valid [')
    p=run('--config',str(bad)); assert p.returncode!=0 and (b'failed to read git config' in p.stderr or b'failed to parse' in p.stderr)

def test_diff_normal_and_raw_modes():
    patch=b'--- a/file.txt\n+++ b/file.txt\n@@ -1,3 +1,3 @@\n line one\n-line three\n+line THREE\n line four\n'
    p=run('--no-gitconfig','--paging=never',data=patch); v=visible(p.stdout)
    assert p.returncode==0 and 'a/file.txt ⟶   b/file.txt' in v and 'line THREE' in v and '@@' not in v
    q=run('--no-gitconfig','--raw',data=patch); assert b'@@ -1,3 +1,3 @@' in q.stdout and b'--- a/file.txt' in q.stdout
    c=run('--no-gitconfig','--color-only',data=patch); assert b'@@ -1,3 +1,3 @@' in c.stdout and b'--- a/file.txt' in c.stdout

def test_git_headers_and_paths():
    p=run('--no-gitconfig',data=b'diff --git a/src/a.py b/src/a.py\nindex 1..2 100644\n--- a/src/a.py\n+++ b/src/a.py\n@@ -1 +1 @@\n-x\n+y\n')
    v=visible(p.stdout); assert 'src/a.py' in v and 'diff --git' not in v and 'index 1..2' not in v
    p=run('--no-gitconfig',data=b'--- a/foo/./bar/../baz.txt\n+++ b/foo//baz.txt\n@@ -1 +1 @@\n-a\n+b\n')
    assert 'a/foo/./bar/../baz.txt ⟶   b/foo//baz.txt' in visible(p.stdout)

def test_hunks_zero_counts_markers_and_line_numbers():
    p=run('--no-gitconfig',data=b'--- x\n+++ x\n@@ -1,0 +1,0 @@\n')
    assert '───┐' not in visible(p.stdout)
    p=run('--no-gitconfig','--line-numbers',data=b'--- x\n+++ x\n@@ -1 +1 @@\n-a\n+b\n')
    v=visible(p.stdout); assert '1:' in v and '1' in v and '2' in v
    p=run('--no-gitconfig','--keep-plus-minus-markers',data=b'--- x\n+++ x\n@@ -1 +1 @@\n-a\n+b\n')
    assert '-a' in visible(p.stdout) and '+b' in visible(p.stdout)

def test_line_pair_emphasis_and_buffer():
    d=b'--- x.py\n+++ x.py\n@@ -1 +1 @@\n-The quick brown fox\n+The quick red fox\n'
    normal=run('--no-gitconfig','--true-color=always',data=d)
    off=run('--no-gitconfig','--line-buffer-size=0','--true-color=always',data=d)
    assert b'48;2;144;16;17' in normal.stdout and b'48;2;0;96;0' in normal.stdout
    assert normal.stdout != off.stdout

def test_width_validation():
    for arg in ('--width=-5000','-w=-5000','-w-5000'):
        p=run(arg); assert p.returncode==2 and b'current terminal width of 80 minus 5000 is negative' in p.stderr
    assert run('--width','-5000','--no-gitconfig').returncode==2

def test_list_and_completion_actions():
    p=run('--list-syntax-themes'); assert p.returncode==0 and b'dark\t1337\n' in p.stdout and b'light\tGitHub' in p.stdout
    p=run('--list-languages'); assert p.returncode==0 and b'Python' in p.stdout and b'Rust' in p.stdout and len(p.stdout.splitlines())>50
    expectations={'bash':[b'_delta()',b'COMPREPLY',b'--show-config'], 'zsh':[b'#compdef',b'_arguments'], 'fish':[b'complete -c delta'], 'powershell':[b'using namespace',b'Register-ArgumentCompleter'], 'elvish':[b'use builtin',b'edit:completion:arg-completer']}
    for shell,need in expectations.items():
        p=run('--generate-completion',shell); assert p.returncode==0 and p.stdout
        for x in need: assert x in p.stdout

def test_show_colors_and_syntax_previews():
    p=run('--show-colors'); assert p.returncode==0 and b'Blue' in p.stdout and b'Red' in p.stdout and b'Green' in p.stdout and b'steelblue' in p.stdout and b'export function color()' in visible(p.stdout)
    p=run('--show-syntax-themes','--dark',data=b'fn custom() {}\n'); assert p.returncode==0 and b'Syntax theme:' in p.stdout and b'custom' in p.stdout

def test_parse_ansi_lines():
    p=run('--parse-ansi',data=b'Plain \x1b[31mRed\x1b[0m\n\x1b[0m')
    assert p.returncode==0 and b'(normal)Plain ' in p.stdout and b'(\x1b[31mred\x1b[0m)\x1b[31mRed' in p.stdout and p.stdout.endswith(b'\n\n')

def test_diff_stat_conflicts_binary_and_passthrough():
    p=run('--no-gitconfig',data=b' src/a.py | 2 +-\n 1 file changed, 1 insertion(+), 1 deletion(-)\n')
    assert 'src/a.py | 2 +-' in visible(p.stdout) and '1 file changed' in visible(p.stdout)
    binary=b'Binary files a/image.png and b/image.png differ\n'
    assert run('--no-gitconfig',data=binary).stdout==binary
    conflict=b'--- x.txt\n+++ x.txt\n@@ -1,3 +1,5 @@\n context\n++<<<<<<< ours\n++our line\n++=======\n++their line\n++>>>>>>> theirs\n context\n'
    p=run('--no-gitconfig',data=conflict); assert 'ours' in visible(p.stdout) and 'theirs' in visible(p.stdout)

def test_grep_and_blame_recognition():
    p=run('--no-gitconfig',data=b'file-name_2.0.py:7:print("hello")\n')
    assert 'file-name_2.0.py' in visible(p.stdout) and 'print' in visible(p.stdout)
    blame=b'abcdef1234567890abcdef1234567890abcdef12 (Jane Doe 1710000000 7) print(1)\nordinary\n'
    p=run('--no-gitconfig','--blame-timestamp-output-format=%Y',data=blame)
    assert 'Jane Doe' in visible(p.stdout) and 'print(1)' in visible(p.stdout) and 'ordinary' in visible(p.stdout)

def test_direct_comparison(tmp_path):
    a=tmp_path/'a'; b=tmp_path/'b'; a.write_text('same\n'); b.write_text('same\n')
    assert run('--no-gitconfig',str(a),str(b)).returncode==0
    b.write_text('different\n'); p=run('--no-gitconfig',str(a),str(b)); assert p.returncode==1 and 'different' in visible(p.stdout)
    p=run('/dev/null','/nonexistent_xyz_123.txt'); assert p.returncode==1 and p.stdout==b'' and p.stderr==b"git diff: error: Could not access '/nonexistent_xyz_123.txt'\n"
    p=run('--diff-args="bad',str(a),str(b)); assert p.returncode==2 and b'Failed to parse diff args' in p.stderr

def test_external_command_routing():
    p=run('git','config','--list'); assert p.returncode in (0,128) # external command status is retained
    p=run('--bad','git','status'); assert p.returncode==2

def test_unicode_invalid_bytes_and_crlf_recover():
    data=b'plain\r\n\xff\x00tail\n--- a/x\n+++ b/x\n@@ -1 +1 @@\n-hello\n+world\n'
    p=run('--no-gitconfig',data=data)
    assert p.returncode==0 and b'plain\n' in p.stdout and '�' in visible(p.stdout) and 'world' in visible(p.stdout)

def test_hyperlinks_navigation_and_custom_labels():
    patch=b'--- a/a b.txt\n+++ b/a b.txt\n@@ -1 +1 @@\n-old\n+new\n'
    p=run('--no-gitconfig','--hyperlinks','--navigate','--file-modified-label=STOP: ',data=patch)
    assert p.returncode==0 and b'\x1b]8;;file://' in p.stdout and 'STOP: a b.txt' in visible(p.stdout) and '•' in visible(p.stdout)
    p=run('--no-gitconfig','--navigate',data=b'--- x\n+++ x\n@@ -1,0 +1,0 @@\n')
    assert 'Δ' in visible(p.stdout) and '•' not in visible(p.stdout)

def test_side_by_side_and_width_truncation():
    patch=b'--- a.txt\n+++ b.txt\n@@ -1 +1 @@\n-a very long removed line\n+a very long added line\n'
    p=run('--no-gitconfig','--side-by-side','--width=40',data=patch)
    assert p.returncode==0 and 'a very long removed line' in visible(p.stdout) and 'a very long added line' in visible(p.stdout)
    p=run('--no-gitconfig','--max-line-length=5',data=patch)
    assert p.returncode==0 and len(p.stdout)<10000

def test_color_only_preserves_raw_headers_and_markers():
    patch=b'diff --git a/f b/f\nindex 1..2 100644\n--- a/f\n+++ b/f\n@@ -1 +1 @@\n-a\n+b\n'
    p=run('--no-gitconfig','--color-only',data=patch)
    for x in (b'diff --git',b'index 1..2',b'@@ -1 +1 @@',b'--- a/f',b'+++ b/f'): assert x in p.stdout

def test_paging_passthrough_and_missing_pager_fallback():
    patch=b'--- x\n+++ x\n@@ -1 +1 @@\n-a\n+b\n'
    direct=run('--no-gitconfig','--paging=never',data=patch)
    for args,env in [(('--paging=always','--pager=cat'),{}),(('--paging=always',),{'PAGER':'cat'}),(('--paging=always',),{'DELTA_PAGER':'cat'}),(('--paging=always','--pager=missing-pager-command-xyz'),{})]:
        p=run('--no-gitconfig',*args,data=patch,env=env)
        assert p.returncode==0 and p.stdout==direct.stdout
    p=run('--no-gitconfig','--paging=always','--pager=delta',data=patch)
    assert p.returncode!=0 and b'non-terminating recursion' in p.stderr and b'delta is not an appropriate value for $PAGER' in p.stderr

def test_raw_ansi_and_color_styles():
    p=run('--parse-ansi',data=b'\x1b[1;4;31mX\x1b[0m\n')
    assert b'bold ul red' in p.stdout
    p=run('--no-gitconfig','--true-color=always',data=b'--- x.py\n+++ x.py\n@@ -1 +1 @@\n-a\n+b\n')
    assert b'48;2;144;16;17' in p.stdout and b'48;2;0;96;0' in p.stdout
    p=run('--no-gitconfig','--true-color=never',data=b'--- x.py\n+++ x.py\n@@ -1 +1 @@\n-a\n+b\n')
    assert b'48;5;124' in p.stdout and b'48;5;28' in p.stdout
    p=run('--no-gitconfig','--plus-style=not-a-style',data=b'')
    assert p.returncode==2 and p.stdout==b'' and b'Style key not found in git config: delta.not-a-style' in p.stderr
