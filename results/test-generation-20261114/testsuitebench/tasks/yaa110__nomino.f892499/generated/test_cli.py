import json, os, subprocess
from pathlib import Path
import pytest

EXE = '/workspace/executable'

def run(args=(), cwd=None):
    return subprocess.run([EXE, *map(str,args)], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def tree(tmp_path, files):
    for name, data in files.items():
        p=tmp_path/name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data if isinstance(data,bytes) else data.encode())

def test_version():
    p=run(['--version']); assert (p.returncode,p.stdout,p.stderr)==(0,b'nomino 1.6.4\n',b'')

def test_short_help():
    p=run(['-h']); assert p.returncode==0 and p.stderr==b''
    assert p.stdout.startswith(b'Batch rename utility for developers\n\nUsage: executable')
    assert b'--from-file' in p.stdout and p.stdout.endswith(b'\n')

def test_help_precedes_bad_option():
    p=run(['--help','--definitely-not-a-flag']); assert p.returncode==0 and b'Options:' in p.stdout and p.stderr==b''

@pytest.mark.parametrize('args,parts', [(['--bogus'],["unexpected argument '--bogus'",'For more information']),(['--nonexistent-flag'],['unexpected argument','a similar argument exists']),(['--dir'],["a value is required for '--dir <PATH>'"]),(['--regex'],["a value is required for '--regex <PATTERN>'"]),(['--depth','foo'],["invalid value 'foo' for '--depth <DEPTH>'"]),(['--depth','-1'],["unexpected argument '-1'","use '-- -1'"]),(['--depth=-1'],["invalid value '-1' for '--depth <DEPTH>'"])])
def test_parser_diagnostics(args,parts):
    p=run(args); assert p.returncode==2 and p.stdout==b''
    s=p.stderr.decode(); assert all(x in s for x in parts)

def test_sort_invalid_exact():
    p=run(['-s','invalid','x']); assert p.returncode==2 and p.stdout==b''
    assert p.stderr.decode().strip()=="error: invalid value 'invalid' for '--sort <ORDER>'\n  [possible values: asc, desc]\n\nFor more information, try '--help'."

@pytest.mark.parametrize('args', [[],['out'],['-t','-d','/tmp']])
def test_missing_mode(args):
    p=run(args); assert p.returncode==1 and b"one of 'regex', 'sort', 'map' or 'SOURCE' options must be set." in p.stderr

def test_positional_conflict():
    p=run(['-s','asc','source','out']); assert p.returncode==1 and p.stderr==b'error: optional SOURCE must be used without setting regex, map or sort flags\n'

def test_sort_extensions_and_generated_map(tmp_path):
    tree(tmp_path, {'a.txt':'a','b.txt':'b'})
    p=run(['-s','ASC','-d',tmp_path,'-t','-g','undo.json','{:2}'])
    assert p.returncode==0 and b'01.txt' in p.stdout and b'02.txt' in p.stdout
    assert json.loads((tmp_path/'undo.json').read_text())=={'01.txt':'a.txt','02.txt':'b.txt'}

def test_sort_no_extension_actual_and_bytes(tmp_path):
    tree(tmp_path, {'a.txt':b'\x00\xff','b.txt':b'other'})
    p=run(['--dir',tmp_path,'-s','asc','-E','{:2}'])
    assert p.returncode==0 and (tmp_path/'01').read_bytes()==b'\x00\xff' and (tmp_path/'02').read_bytes()==b'other'

def test_sort_natural_and_descending(tmp_path):
    tree(tmp_path, {'file1':'','file2':'','file10':'','file20':''})
    p=run(['-d',tmp_path,'-s','desc','-t','file_{}'])
    assert p.returncode==0
    assert p.stdout.index(b'file20') < p.stdout.index(b'file10') < p.stdout.index(b'file2') < p.stdout.index(b'file1')

def test_regex_subgroups_unicode_and_formatting(tmp_path):
    tree(tmp_path, {'café.txt':'x','Café.txt':'y','S01E05.mkv':'z'})
    p=run(['-d',tmp_path,'-r',r'S(?<season>\d+)E(?P<ep>\d+)\.mkv','Season{season}_Episode{ep}','-t'])
    assert p.returncode==0 and b'S01E05.mkv' in p.stdout and b'Season01_Episode05.mkv' in p.stdout
    q=run(['-d',tmp_path,'café','{0}_processed','-t'])
    assert q.returncode==0 and b'café.txt' in q.stdout and b'café_processed.txt' in q.stdout and b'Café.txt' not in q.stdout

def test_regex_auto_index_padding_and_absent_groups(tmp_path):
    tree(tmp_path, {'file_1_a.txt':'x'})
    p=run(['-d',tmp_path,'-r',r'file_(\d+)_([a-z])','{2}_{:3}_{99:2}','-t'])
    assert p.returncode==0 and b'a_001_.txt' in p.stdout

def test_positional_regex_alias_and_leading_hyphens(tmp_path):
    tree(tmp_path, {'--odd.txt':'x'})
    p=run(['-d',tmp_path,'--','(odd)','new_{1}','-t'])
    assert p.returncode==0 and b'--odd.txt' in p.stdout

def test_depth_and_max_depth(tmp_path):
    tree(tmp_path, {'file1.txt':'','a/file2.txt':'','a/b/file3.txt':'','a/b/c/file4.txt':''})
    p=run(['-d',tmp_path,'-r','file(\d+)','X{}','--depth','2','-t'])
    assert p.returncode==0 and b'a/file2.txt' in p.stdout and b'file1.txt' not in p.stdout and b'file3.txt' not in p.stdout
    q=run(['-d',tmp_path,'-r','file(\d+)','X{}','--max-depth','2','-t'])
    assert q.returncode==0 and b'file1.txt' in q.stdout and b'a/file2.txt' in q.stdout and b'file3.txt' not in q.stdout

def test_dry_run_no_move_and_quiet(tmp_path):
    tree(tmp_path, {'file1.txt':'data'})
    p=run(['-d',tmp_path,'-t','-r','file(\d+)','renamed_{}'])
    assert p.returncode==0 and b'renamed_1.txt' in p.stdout and (tmp_path/'file1.txt').exists()
    q=run(['-d',tmp_path,'-t','-q','-r','file(\d+)','renamed_{}'])
    assert q.returncode==0 and q.stdout==b''

def test_identity_map_and_undo_map(tmp_path):
    tree(tmp_path, {'file1.txt':'data'})
    p=run(['-d',tmp_path,'-r','file(\d+)','file{}','-g','undo.json'])
    assert p.returncode==0 and (tmp_path/'file1.txt').read_bytes()==b'data'
    assert json.loads((tmp_path/'undo.json').read_text())=={'file1.txt':'file1.txt'}

def test_map_literal_paths_and_alias(tmp_path):
    tree(tmp_path, {'src/é.txt':b'abc'})
    (tmp_path/'map.json').write_text(json.dumps({'src/é.txt':'nested/文件.txt'},ensure_ascii=False))
    p=run(['--dir',tmp_path,'--from-file','map.json','-k'])
    assert p.returncode==0 and (tmp_path/'nested/文件.txt').read_bytes()==b'abc'

def test_map_missing_source_continues(tmp_path):
    tree(tmp_path, {'have':'yes'})
    (tmp_path/'m.json').write_text('{"have":"done", "absent":"gone"}')
    p=run(['-d',tmp_path,'-m','m.json'])
    assert p.returncode==1 and (tmp_path/'done').read_text()=='yes' and b"unable to rename 'absent'" in p.stderr

def test_map_malformed_and_missing_file(tmp_path):
    p=run(['-d',tmp_path,'-m','no.json']); assert p.returncode==1 and b'No such file or directory' in p.stderr
    (tmp_path/'bad').write_text('not valid json at all')
    q=run(['-d',tmp_path,'-m','bad']); assert q.returncode==1 and b'expected ident at line 1 column 2' in q.stderr

def test_mkdir_in_dry_run(tmp_path):
    tree(tmp_path, {'f1.txt':'x'})
    p=run(['-d',tmp_path,'-t','-k','-r','f(\d+)','out/a/b/renamed_{}'])
    assert p.returncode==0 and (tmp_path/'out/a/b').is_dir() and (tmp_path/'f1.txt').exists()

def test_missing_parent_failure_omits_table(tmp_path):
    tree(tmp_path, {'file1.txt':'x'})
    p=run(['-d',tmp_path,'-r','file(\d+)','missing/renamed_{}'])
    assert p.returncode==1 and p.stdout==b'' and b'No such file or directory' in p.stderr

def test_extension_rule_and_no_extension(tmp_path):
    tree(tmp_path, {'file.tar.gz':'x'})
    p=run(['-d',tmp_path,'-r','file','archive_file.tar.gz','-t'])
    assert p.returncode==0 and b'archive_file.tar.gz.gz' in p.stdout
    q=run(['-d',tmp_path,'-E','-r','(.+)','{1}_renamed','-t'])
    assert q.returncode==0 and b'file.tar.gz_renamed' in q.stdout

@pytest.mark.parametrize('fmt,msg', [('x}','an unopened placeholder could not be closed'),('{x','all opened placeholders must be closed'),('{1:abc}',"unable to parse padding of 'abc'"),(r'\a',"invalid escape character of 'a' at '1'")], ids=['extra-close','missing-close','bad-padding','bad-escape'])
def test_output_format_errors(tmp_path,fmt,msg):
    tree(tmp_path, {'file1.txt':'x'})
    p=run(['-d',tmp_path,'-r','file(\d+)',fmt,'-t'])
    assert p.returncode==1 and msg.encode() in p.stderr and p.stdout==b''

def test_collision_without_overwrite(tmp_path):
    tree(tmp_path, {'f1.mkv':'1','f2.mkv':'2','target.mkv':'old'})
    p=run(['-d',tmp_path,'-r','f(\d+)','target','-t'])
    assert p.returncode==0 and b'_target.mkv' in p.stdout and (tmp_path/'f1.mkv').exists()

def test_overwrite_collapses_duplicate_targets(tmp_path):
    tree(tmp_path, {'f1':'one','f2':'two'})
    p=run(['-d',tmp_path,'-w','-r','f(\d+)','same'])
    assert p.returncode==0 and (tmp_path/'same').exists() and not (tmp_path/'_same').exists()

def test_static_dry_run_retains_later_source(tmp_path):
    tree(tmp_path, {'file1.txt':'','file2.txt':'','file3.txt':''})
    p=run(['-d',tmp_path,'-t','-r','file\d+','static_name'])
    assert p.returncode==0 and p.stdout.count(b' -> ') == 1 and b'file3.txt' in p.stdout

def test_unicode_report_and_actual_rename(tmp_path):
    tree(tmp_path, {'файл.txt':b'bytes','文件.txt':b'wide','file_😀.txt':b'emoji'})
    p=run(['-d',tmp_path,'-t','-r','(файл|文件|file_😀)','新_{1}'])
    assert p.returncode==0 and '文件'.encode() in p.stdout and '😀'.encode() in p.stdout
    q=run(['-d',tmp_path,'-r','(файл)','новый_{1}'])
    assert q.returncode==0 and (tmp_path/'новый_файл.txt').read_bytes()==b'bytes'

def test_no_matches_silent(tmp_path):
    tree(tmp_path, {'x':'x'})
    p=run(['-d',tmp_path,'-r','absent','x'])
    assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'')

def test_invalid_regex_examples(tmp_path):
    for pat, phrase in [('[a-','unclosed character class'),('(','unclosed group'),('*','repetition operator missing expression')]:
        p=run(['-d',tmp_path,'-r',pat,'x']); assert p.returncode==1 and phrase.encode() in p.stderr
