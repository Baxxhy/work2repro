import json, os
from pathlib import Path
from conftest import records


def test_filter_terminator_and_missing_continuation(invoke,tmp_path):
    (tmp_path/'a.c').write_text('int alpha;\n'); (tmp_path/'b.c').write_text('int beta;\n')
    p=invoke('--filter','--filter-terminator=END\n','-o','ignored',input='a.c\nmissing.c\nb.c\n')
    assert p.returncode==0 and 'alpha' in p.stdout and 'beta' in p.stdout and p.stdout.count('END\n')==3
    assert 'cannot open input file "missing.c"' in p.stderr and 'filter mode ignores' in p.stderr

def test_list_and_describe_catalog(invoke):
    p=invoke('--list-languages'); assert p.returncode==0 and '#LANGUAGE' in p.stdout and 'Python' in p.stdout and 'JavaScript' in p.stdout
    p=invoke('--list-kinds=C'); assert p.stdout.startswith('d  macro definitions') and 'function' in p.stdout
    p=invoke('--describe-language=C'); assert p.stdout.startswith('About C language') and 'enabled: yes' in p.stdout and 'version: 2.2' in p.stdout
    assert invoke('--list-kinds=InvalidLang').returncode==1
    assert invoke('--list-output-formats').returncode==0

def test_option_files_and_startup_sort(invoke,tmp_path):
    (tmp_path/'x.c').write_text('int beta;\nint alpha;\n')
    opt=tmp_path/'options file'; opt.write_text('--sort=no\n')
    p=invoke('--options='+str(opt),'-o','-','x.c'); assert [r[0] for r in records(p.stdout)]==['beta','alpha']
    d=tmp_path/'.ctags.d'; d.mkdir(); (d/'01.ctags').write_text('--sort=no\n')
    p=invoke('-o','-','x.c'); assert [r[0] for r in records(p.stdout)]==['beta','alpha']
    p=invoke('--options=NONE','-o','-','x.c'); assert 'No options will be read' in p.stderr

def test_recursion_and_exclusions(invoke,tmp_path):
    (tmp_path/'main.c').write_text('int main_tag;\n'); (tmp_path/'src').mkdir(); (tmp_path/'src'/'a.c').write_text('int src_tag;\n')
    (tmp_path/'test').mkdir(); (tmp_path/'test'/'b.c').write_text('int test_tag;\n')
    p=invoke('-R','.','--exclude=test/*','-o','-',cwd=tmp_path)
    assert p.returncode==0 and 'main.c' in p.stdout and 'src/a.c' in p.stdout and 'test/b.c' not in p.stdout

def test_etags_sections_and_bytes(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('int alpha;\n')
    p=invoke('-e','-o','-',f); assert p.returncode==0 and '\x0c' in p.stdout and 'x.c,' in p.stdout and '\x7f' in p.stdout and '\x01' in p.stdout
    header=p.stdout.split('\n',1)[0]; count=int(header.split(',')[1]); entry=p.stdout.split('\n',1)[1]
    assert len(entry.encode())==count

def test_interactive_protocol(invoke,tmp_path):
    p=invoke('--_interactive',input='{"command":"generate-tags","filename":"none.py","size":0}\nBAD\n{"command":"wat"}\n')
    assert p.returncode==0
    objs=[json.loads(x) for x in p.stdout.splitlines()]
    assert objs[0]=={'_type':'program','name':'Universal Ctags','version':'6.2.0'}
    assert {'_type':'completed','command':'generate-tags'} in objs
    assert any(o.get('message')=='invalid json' for o in objs) and any(o.get('message')=='unknown command name' for o in objs)

def test_python_and_cpp_extensions(invoke,tmp_path):
    py=tmp_path/'x.py'; py.write_text('@staticmethod\ndef f(): pass\nclass Child(Base):\n    @property\n    def value(self): return 1\n')
    p=invoke('--fields-Python=+{decorators}','--fields=+i','-o','-',py)
    assert p.returncode==0 and 'decorators:staticmethod' in p.stdout and 'decorators:property' in p.stdout and 'inherits:Base' in p.stdout
    cpp=tmp_path/'x.cpp'; cpp.write_text('class MyClass { public: int method(int x) { return x; } };\n')
    p=invoke('--_xformat=%N %K %Z','-x',cpp)
    assert 'method function MyClass' in p.stdout

def test_response_pattern_lists_and_totals(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('int a;\nint b;\n')
    excludes=tmp_path/'exclude'; excludes.write_text('x.c\n')
    assert 'a' not in invoke('--exclude=@'+str(excludes),'-o','-',f).stdout
    p=invoke('--totals=yes','-o','-',f); assert p.returncode==0 and '1 file' in p.stderr and '2 tags' in p.stderr
