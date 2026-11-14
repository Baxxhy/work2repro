import os, re, subprocess
from pathlib import Path
import pytest

BIN = '/workspace/executable'

def run(args, data=None, cwd=None, env=None):
    return subprocess.run([BIN, *map(str,args)], input=data, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, cwd=cwd, env=env, timeout=15)

def test_no_arguments_exact():
    p=run([]); assert (p.returncode,p.stdout,p.stderr)==(2,b'',b'rg: ripgrep requires at least one pattern to execute a search\n')

def test_version_formats():
    p=run(['-V']); assert p.returncode==0 and p.stderr==b''
    assert re.fullmatch(rb'ripgrep 14\.1\.1 \(rev [0-9a-f]+\)\n',p.stdout)
    q=run(['--version']); assert q.returncode==0 and b'features:-pcre2\nsimd(compile):' in q.stdout and q.stdout.endswith(b'PCRE2 is not available in this build of ripgrep.\n')

def test_help_terminal_precedence():
    p=run(['bad[','/definitely/missing','--help']); assert p.returncode==0 and p.stderr==b'' and b'USAGE:' in p.stdout
    assert all(x in p.stdout for x in [b'INPUT OPTIONS:',b'SEARCH OPTIONS:',b'FILTER OPTIONS:',b'OUTPUT OPTIONS:',b'OUTPUT MODES:',b'LOGGING OPTIONS:',b'OTHER BEHAVIORS:'])

def test_type_list_matches_normative_asset():
    p=run(['--type-list','ignored']); assert p.returncode==0 and p.stderr==b'' and p.stdout==Path('/workspace/eval/type-list.txt').read_bytes()

def test_stdin_and_empty_regex():
    p=run(['needle','-'],b'needle\nnope'); assert p.returncode==0 and p.stdout==b'needle\n' and not p.stderr
    q=run(['','-'],b'a\n\n'); assert q.returncode==0 and q.stdout==b'a\n\n'

def test_empty_pattern_file_is_no_match(tmp_path):
    pats=tmp_path/'empty'; pats.write_bytes(b''); data=tmp_path/'data'; data.write_text('anything\n')
    p=run(['-f',pats,data]); assert p.returncode==1 and p.stdout==b'' and p.stderr==b''

def test_pattern_sources_union_and_unterminated_final_line(tmp_path):
    f=tmp_path/'pats'; f.write_bytes(b'alpha\nbeta')
    d=tmp_path/'data'; d.write_text('alpha\nbeta\ngamma\n')
    p=run(['-e','gamma','-f',f,d]); assert p.returncode==0 and p.stdout==b'alpha\nbeta\ngamma\n'

def test_regex_unicode_posix_and_errors(tmp_path):
    f=tmp_path/'x'; f.write_text('abc\n123\n-_\n')
    p=run(['[[:alpha:]]',f]); assert (p.returncode,p.stdout,p.stderr)==(0,b'abc\n',b'')
    q=run(['(','missing']); assert q.returncode==2 and q.stdout==b'' and b'unclosed group' in q.stderr

def test_fixed_word_line_and_case_modes(tmp_path):
    f=tmp_path/'x'; f.write_text('Foo.bar\nfoobar\nfoo\n')
    assert run(['-F','Foo.','-x',f]).returncode==1
    assert run(['-F','Foo.bar','-x',f]).stdout==b'Foo.bar\n'
    assert run(['-w','foo',f]).stdout==b'foo\n'
    assert run(['-i','FOO',f]).stdout==b'Foo.bar\nfoobar\nfoo\n'

def test_only_matching_counts_and_zero_width(tmp_path):
    f=tmp_path/'x'; f.write_text('foo bar foo\n')
    assert run(['-o','foo',f]).stdout==b'foo\nfoo\n'
    assert run(['-c','-o','foo',f]).stdout==b'2\n'
    assert run(['-o','^|$',f]).stdout==b'\n\n'

def test_context_merging_and_max_count(tmp_path):
    f=tmp_path/'x'; f.write_text('hit\na\nhit\nb\nc\nhit\n')
    p=run(['-C1','hit',f]); assert p.stdout.count(b'hit')==3 and p.stdout.count(b'--\n')==1
    assert run(['-m1','-c','hit',f]).stdout==b'1\n'

def test_final_unterminated_line_and_record_output(tmp_path):
    f=tmp_path/'x'; f.write_bytes(b'no\nhit')
    assert run(['hit',f]).stdout==b'hit\n'
    assert run(['-n','hit',f]).stdout==b'2:hit\n'

def test_json_events_are_valid_and_compact(tmp_path):
    import json
    f=tmp_path/'x'; f.write_text('a hit\nno\n')
    p=run(['--json','hit',f]); assert p.returncode==0 and not p.stderr
    objs=[json.loads(x) for x in p.stdout.splitlines()]
    assert [x['type'] for x in objs]==['begin','match','end','summary']

def test_files_and_file_list_modes(tmp_path):
    (tmp_path/'a').write_text('hit'); (tmp_path/'b').write_text('no')
    p=run(['-l','hit',tmp_path]); assert p.returncode==0 and p.stdout.count(b'a')>=1 and b'b' not in p.stdout
    q=run(['--files',tmp_path]); assert q.returncode==0 and b'a' in q.stdout and b'b' in q.stdout

def test_hidden_glob_type_filtering(tmp_path):
    (tmp_path/'a.py').write_text('hit'); (tmp_path/'a.txt').write_text('hit'); (tmp_path/'.hidden').write_text('hit')
    assert run(['-l','hit',tmp_path]).stdout.count(b'\n')==2
    assert run(['--hidden','-g','*.py','-l','hit',tmp_path]).stdout.strip().endswith(b'a.py')
    assert run(['-t','python','-l','hit',tmp_path]).stdout.strip().endswith(b'a.py')

def test_ignore_rules_and_unrestricted(tmp_path):
    (tmp_path/'.ignore').write_text('skip\n'); (tmp_path/'skip').write_text('hit'); (tmp_path/'keep').write_text('hit')
    assert b'skip' not in run(['-l','hit',tmp_path]).stdout
    assert b'skip' in run(['-uuu','-l','hit',tmp_path]).stdout

def test_explicit_missing_path_error():
    p=run(['hit','/nonexistent/path']); assert p.returncode==2 and p.stdout==b'' and p.stderr==b'rg: /nonexistent/path: IO error for operation on /nonexistent/path: No such file or directory (os error 2)\n'

def test_config_prepend_and_no_config(tmp_path):
    f=tmp_path/'data'; f.write_text('hit\nhit\n'); c=tmp_path/'cfg'; c.write_text('--max-count=1\n')
    env=os.environ.copy(); env['RIPGREP_CONFIG_PATH']=str(c)
    assert run(['hit',f],env=env).stdout==b'hit\n'
    assert run(['--no-config','hit',f],env=env).stdout==b'hit\nhit\n'

def test_generate_completion_bytes():
    for kind in ['bash','fish','powershell','zsh']:
        p=run(['--generate','complete-'+kind]); assert p.returncode==0 and p.stderr==b''
        assert p.stdout==Path('/workspace/eval/completion-'+kind+'.txt').read_bytes()

def test_generate_unknown_choice_exact():
    p=run(['--generate=complete-unknown']); assert (p.returncode,p.stdout,p.stderr)==(2,b'',b"rg: error parsing flag --generate: choice 'complete-unknown' is unrecognized\n")

def test_encoding_bom_and_none(tmp_path):
    f=tmp_path/'x'; f.write_bytes(b'\xef\xbb\xbfhit\n')
    assert run(['-o','^hit',f]).stdout==b'hit\n'
    assert run(['-E','none','-o','^hit',f]).returncode==1

def test_multiline_dotall(tmp_path):
    f=tmp_path/'x'; f.write_text('a\nb\n')
    assert run(['-U','a\\nb',f]).returncode==0
    assert run(['-U','-U','--multiline-dotall','a.b',f]).returncode==0

def test_color_and_quiet(tmp_path):
    f=tmp_path/'x'; f.write_text('hit\n')
    p=run(['--color=always','hit',f]); assert b'\x1b[1m\x1b[31m' in p.stdout
    q=run(['-q','hit',f]); assert q.returncode==0 and q.stdout==b''

def test_debug_logging_preserves_result(tmp_path):
    f=tmp_path/'x'; f.write_text('hit\n')
    p=run(['--debug','hit',f]); assert p.returncode==0 and p.stdout==b'hit\n' and p.stderr.startswith(b'rg: DEBUG|')
