import os, subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')

def run(args=(), *, data=None, cwd=None):
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, timeout=10)

def put(p, s):
    p.write_bytes(s.encode())

def test_version_exact():
    r=run(['--version']); assert (r.returncode,r.stdout,r.stderr)==(0,b'tex-fmt 0.5.6\n',b'')

def test_short_version():
    r=run(['-V']); assert r.returncode==0 and r.stdout.startswith(b'tex-fmt') and r.stdout.endswith(b'\n') and not r.stderr

def test_help_short_and_long():
    for a in (['--help'],['-h']):
        r=run(a); assert r.returncode==0 and b'Usage: executable [OPTIONS] [files]...' in r.stdout and not r.stderr

def test_help_after_separator():
    r=run(['--help','--','--bad']); assert r.returncode==0 and b'Usage:' in r.stdout and not r.stderr

def test_unknown_argument_precedes_help():
    r=run(['--unknown','--help']); assert r.returncode==2 and not r.stdout and b"unexpected argument '--unknown' found" in r.stderr

def test_unknown_option_diagnostic():
    r=run(['--unknown-flag']); assert r.returncode==2 and b"unexpected argument '--unknown-flag' found" in r.stderr and b"Usage: executable [OPTIONS] [files]..." in r.stderr and b"-- --unknown-flag" in r.stderr

@pytest.mark.parametrize('args,needle', [(['--wraplen'],b'a value is required'),(['--tabsize','999'],b'0..=255'),(['--wraplen','-1'],b'invalid value'),(['--wraplen','abc'],b"invalid value 'abc'"),(['--tabsize','1.5'],b'invalid value'),(['--completion','bad'],b'invalid value')], ids=['missing-wrap','tab-overflow','negative-wrap','nonnumeric-wrap','nonnumeric-tab','bad-shell'])
def test_invalid_arguments(args,needle):
    r=run(args); assert r.returncode==2 and needle in r.stderr and not r.stdout

@pytest.mark.parametrize('args', [['--wraplen','0'],['--wraplen','1000'],['-vp'],['-l=40']])
def test_valid_argument_forms(args):
    r=run([*args,'--args','--noconfig']); assert r.returncode==0 and b'tex-fmt\n' in r.stdout

def test_args_defaults():
    r=run(['--args','--noconfig']); s=r.stdout.decode(); assert r.returncode==0 and not r.stderr
    for text in ('  check:                   false','  print:                   false','  wrap:                    true','  wraplen:                 80','  wrapmin:                 70','  tabsize:                 2','  tabchar:                 space','  stdin:                   false','  config:                  None','  verbosity:               warn','  lists:                   itemize','  verbatims:               verbatim','  no-indent-envs:          document','  wrap-chars:               '): assert text in s

def test_args_cli_resolution():
    r=run(['--args','--noconfig','--print','--check','--nowrap','--wraplen=1000','--tabsize','4','--usetabs','--stdin','-q','-v','--trace','--files-do-not-exist'])
    # Unknown trailing token is a syntax error; use a real positional filename instead.
    if r.returncode: r=run(['--args','--noconfig','--print','--nowrap','--wraplen=1000','--tabsize','4','--usetabs','--stdin','-q','-v','--trace'])
    assert r.returncode==0 and all(x in r.stdout for x in (b'fail-on-change:          true',b'wrap:                    false',b'wraplen:                 1000',b'tabsize:                 4',b'tabchar:                 tab',b'verbosity:               trace'))

def test_stdin_format_and_empty():
    r=run(['--noconfig','--stdin','--nowrap'],data=b''); assert (r.returncode,r.stdout)==(0,b'\n')
    r=run(['--noconfig','-s','-n'],data=b'hello  \n\n'); assert r.returncode==0 and r.stdout==b'hello\n'

def test_space_and_newline_normalization():
    src=b'one  \r\n\r\n\r\ntwo\r\nthree\n\n\n\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==b'one\n\n\ntwo\nthree\n'

def test_tabs_expanded_and_tabs_preserved():
    r=run(['--noconfig','--stdin','--nowrap','--tabsize','3'],data=b'a\tb\n'); assert r.stdout==b'a   b\n'
    r=run(['--noconfig','--stdin','--nowrap','--usetabs'],data=b'a\tb\n'); assert r.stdout==b'a\tb\n'

def test_unicode_preserved_and_wrap():
    r=run(['--noconfig','--stdin','--wraplen','14'],data='Café こんにちは 世界 😀😀'.encode()); assert r.returncode==0 and r.stdout=='Café こんにちは 世界\n😀😀\n'.encode()

def test_structural_split_multiple_commands():
    r=run(['--noconfig','--stdin','--nowrap'],data=b'Text \\section{S} more \\subsection*{T} and more\n')
    assert r.stdout==b'Text\n\\section{S} more\n\\subsection*{T} and more\n'

def test_structural_split_item_end_and_item_prefix():
    r=run(['--noconfig','--stdin','--nowrap'],data=b'\\item\\item Adjacent\n\\item First \\end{itemize}\n')
    assert r.stdout==b'\\item\n\\item Adjacent\n\\item First\n\\end{itemize}\n'

def test_inline_verb_prevents_structural_split():
    data=b'before \\verb|\\section{No} \\item| after \\section{Yes}\nx \\mintinline{tex}{\\end{x}} y \\part*{P}\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=data); assert r.returncode==0 and r.stdout==data

def test_env_indentation_general_and_document():
    r=run(['--noconfig','--stdin','--nowrap'],data=b'\\begin{document}\n\\begin{equation}\nx\n\\end{equation}\n\\end{document}\n')
    assert r.stdout==b'\\begin{document}\n\\begin{equation}\n  x\n\\end{equation}\n\\end{document}\n'

def test_list_indentation_and_nested_list():
    src=b'\\begin{itemize}\n\\item Outer\ncontinuation\n\\begin{enumerate}\n\\item Inner\n\\end{enumerate}\n\\end{itemize}\n'
    expected=b'\\begin{itemize}\n  \\item Outer\n    continuation\n    \\begin{enumerate}\n      \\item Inner\n    \\end{enumerate}\n\\end{itemize}\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==expected

def test_delimiter_indentation_and_closing_dedent():
    src=b'\\command{\ncontent\n}\nafter\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==b'\\command{\n  content\n}\nafter\n'

def test_comment_content_and_escaped_percent():
    src=b'\\% ordinary % comment {\\section{x}}\nnext\n%% two\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==src

def test_wrap_basics_and_boundary():
    r=run(['--noconfig','--stdin','--wraplen','5','--quiet'],data=b'a b c d'); assert r.stdout==b'a b\nc d\n'
    r=run(['--noconfig','--stdin','--wraplen','5','--quiet'],data=b'12345'); assert r.stdout==b'12345\n'

def test_nowrap_only_disables_wrap():
    r=run(['--noconfig','--stdin','--nowrap'],data=b'\\begin{figure}\n'+b'x'*100+b'\n\\end{figure}\n')
    assert r.stdout==b'\\begin{figure}\n  '+b'x'*100+b'\n\\end{figure}\n'

def test_verbatim_protection_and_unclosed():
    src=b'\\begin{verbatim}\n  \\section{X}   % raw\n\\begin{minted}\nraw\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==b'\\begin{verbatim}\n  \\section{X}   % raw\n\\begin{minted}\nraw\n'

def test_skip_off_on_directives():
    src=b'  a   % tex-fmt: skip\n% tex-fmt: off\n  untouched  \n% tex-fmt: on\n'
    r=run(['--noconfig','--stdin','--nowrap'],data=src); assert r.stdout==b'  a   % tex-fmt: skip\n% tex-fmt: off\n  untouched  \n% tex-fmt: on\n'

def test_inline_comment_wrap_continuation():
    r=run(['--noconfig','--stdin','--wraplen','40','--quiet'],data=b'% This is a very long comment line that definitely exceeds the default wrap length and should be wrapped at a space boundary.')
    assert r.returncode==0 and all(line.startswith(b'%') for line in r.stdout.splitlines()) and len(r.stdout.splitlines())>1

def test_file_modes_and_extension_inference(tmp_path):
    p=tmp_path/'sample'; put(p.with_suffix('.tex'),'  hello  \n')
    r=run(['--noconfig',str(p)],cwd=tmp_path); assert r.returncode==0 and p.with_suffix('.tex').read_bytes()==b'hello\n' and not r.stdout and not r.stderr

def test_print_mode_does_not_write_and_concatenates(tmp_path):
    a=tmp_path/'a.tex'; b=tmp_path/'b.tex'; put(a,' A\n'); put(b,'B\n')
    r=run(['--noconfig','--print',a,b],cwd=tmp_path); assert r.returncode==0 and r.stdout==b'A\nB\n' and a.read_bytes()==b' A\n' and b.read_bytes()==b'B\n'

def test_check_mode_status_and_message(tmp_path):
    p=tmp_path/'x.tex'; put(p,'  x  \n')
    r=run(['--noconfig','--check',p],cwd=tmp_path); assert r.returncode==1 and p.read_bytes()==b'  x  \n' and b'Incorrect formatting.' in r.stderr
    put(p,'x\n'); r=run(['--noconfig','--check',p],cwd=tmp_path); assert r.returncode==0 and not r.stderr

def test_fail_on_change_writes_and_returns_change_status(tmp_path):
    p=tmp_path/'x.tex'; put(p,' x  \n')
    r=run(['--noconfig','--fail-on-change',p],cwd=tmp_path); assert r.returncode==1 and p.read_bytes()==b'x\n'
    r=run(['--noconfig','-f',p],cwd=tmp_path); assert r.returncode==0

def test_missing_file_and_other_file_continues(tmp_path):
    good=tmp_path/'good.tex'; put(good,' ok\n'); missing=tmp_path/'absent'
    r=run(['--noconfig','--print',missing,good],cwd=tmp_path); assert r.returncode==1 and r.stdout==b'ok\n' and b'absent.tex: Could not open file.' in r.stderr and not (tmp_path/'absent.tex').exists()

def test_no_inputs_and_directory_errors(tmp_path):
    r=run(['--noconfig'],cwd=tmp_path); assert r.returncode==1 and b'No files specified.' in r.stderr
    r=run(['--noconfig',tmp_path],cwd=tmp_path); assert r.returncode==1 and b'directory was passed without --recursive' in r.stderr

def test_stdin_rejects_filenames(tmp_path):
    p=tmp_path/'x.tex'; put(p,'x')
    r=run(['--noconfig','--stdin',p],data=b'x',cwd=tmp_path); assert r.returncode==1 and b'Do not provide file name(s) when using --stdin.' in r.stderr

def test_config_values_and_cli_override(tmp_path):
    cfg=tmp_path/'cfg.toml'; put(cfg,'wraplen = 20\ntabsize = 4\ntabchar = "tab"\nwrap = false\n')
    r=run(['--args','--config',cfg,'--wraplen','80','--tabsize','3','--usetabs','--nowrap']); s=r.stdout
    assert r.returncode==0 and b'wraplen:                 80' in s and b'tabsize:                 3' in s and b'tabchar:                 tab' in s and b'wrap:                    false' in s

def test_config_list_extension_order(tmp_path):
    cfg=tmp_path/'cfg.toml'; put(cfg,'lists = ["itemize", "tasks"]\nverbatims = ["minted", "raw"]\nno-indent-envs = ["document", "outer"]\nwrap-chars = ["-", "-"]\n')
    s=run(['--args','--config',cfg]).stdout
    assert b'  lists:                   itemize\n                           tasks\n                           itemize\n                           enumerate' in s
    assert b'  verbatims:               minted\n                           raw\n                           verbatim' in s
    assert b'  no-indent-envs:          document\n                           outer\n                           document' in s

def test_noconfig_ignores_explicit_file_and_retains_path(tmp_path):
    cfg=tmp_path/'missing.toml'
    r=run(['--args','--config',cfg,'--noconfig']); assert r.returncode==0 and str(cfg).encode() in r.stdout and b'wraplen:                 80' in r.stdout

def test_bad_config_errors(tmp_path):
    missing=tmp_path/'no.toml'; r=run(['--args','--config',missing]); assert r.returncode!=0 and b'panicked at src/config.rs' in r.stderr and b'No such file or directory' in r.stderr
    bad=tmp_path/'bad.toml'; put(bad,'wraplen = [\n'); r=run(['--args','--config',bad]); assert r.returncode!=0 and b'Failed to read config file' in r.stderr and b'panicked at src/config.rs' in r.stderr

def test_configured_environment_semantics(tmp_path):
    cfg=tmp_path/'c.toml'; put(cfg,'no-indent-envs = ["outer"]\nlists = ["tasks"]\n')
    src=b'\\begin{outer}\nx\n\\end{outer}\n\\begin{tasks}\n\\item y\n\\end{tasks}\n'
    r=run(['--config',cfg,'--stdin','--nowrap'],data=src); assert r.stdout==b'\\begin{outer}\nx\n\\end{outer}\n\\begin{tasks}\n  \\item y\n\\end{tasks}\n'

def test_recursive_discovery_and_filters(tmp_path):
    (tmp_path/'sub').mkdir(); (tmp_path/'.hidden').mkdir(); (tmp_path/'ignored').mkdir()
    put(tmp_path/'sub'/'a.tex','A'); put(tmp_path/'sub'/'b.bib','B'); put(tmp_path/'sub'/'c.txt','NO'); put(tmp_path/'.hidden'/'h.tex','H'); put(tmp_path/'ignored'/'i.tex','I')
    put(tmp_path/'.ignore','ignored/\n')
    r=run(['--noconfig','--recursive','--print'],cwd=tmp_path)
    assert r.returncode==0 and b'A\n' in r.stdout and b'B\n' in r.stdout and b'NO' not in r.stdout and b'H' not in r.stdout and b'I' not in r.stdout

def test_recursive_default_search_cwd(tmp_path):
    (tmp_path/'deep').mkdir(); put(tmp_path/'deep'/'a.cls','A')
    r=run(['--noconfig','--recursive','--print'],cwd=tmp_path); assert r.returncode==0 and r.stdout==b'A\n'

def test_verbose_trace_and_quiet_logs(tmp_path):
    p=tmp_path/'a.tex'; put(p,'x\n')
    r=run(['--noconfig','--verbose',p],cwd=tmp_path); assert r.returncode==0 and b'INFO: tex-fmt' in r.stderr and b'Formatting started.' in r.stderr and b'Formatting complete.' in r.stderr
    r=run(['--noconfig','--trace','--print',p],cwd=tmp_path); assert b'TRACE: tex-fmt' in r.stderr and b'Line 1 (1).' in r.stderr

def test_unwrappable_warn_and_quiet():
    data=b'hello world this is a test'
    r=run(['--noconfig','--stdin','--wraplen','5'],data=data); assert r.stdout==b'hello\nworld\nthis\nis a\ntest\n' and r.stderr.count(b'Line cannot be wrapped.')==2
    q=run(['--noconfig','--stdin','--wraplen','5','--quiet'],data=data); assert q.stdout==r.stdout and not q.stderr

def test_completion_scripts_exit_without_config():
    for shell in ('bash','elvish','fish','powershell','zsh'):
        r=run(['--config','/missing/config.toml','--completion',shell]); assert r.returncode==0 and not r.stderr and shell.encode() in r.stdout

def test_man_output_shape():
    r=run(['--man','--config','/missing/config.toml']); assert r.returncode==0 and not r.stderr and r.stdout.startswith(b'.ie \\n(.g') and r.stdout.endswith(b'\n') and b'.TH tex-fmt 1' in r.stdout

@pytest.mark.parametrize('args,data,expected', [(['--noconfig','--stdin','--wraplen','0'],b'x',b'x\n'),(['--noconfig','--stdin','--wraplen','80','--nowrap'],b'abc',b'abc\n')],ids=['zero-wrap','nowrap'])
def test_wrap_edge_modes(args,data,expected):
    r=run(args,data=data); assert r.returncode==0 and r.stdout==expected
