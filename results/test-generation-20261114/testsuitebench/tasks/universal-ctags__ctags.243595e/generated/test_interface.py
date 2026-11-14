import json, os
from pathlib import Path
from conftest import EXE, records


def test_version_and_help(invoke):
    p=invoke('--version'); assert p.returncode==0
    for s in ('Universal Ctags','6.2.0','URL: https://ctags.io/','Compiled:','Output version:','Optional compiled features:'): assert s in p.stdout
    h=invoke('-?'); assert all(s in h.stdout for s in ('Usage:','[options]','Input/Output Options','--help','--help-full'))
    assert '--_interactive' in invoke('--help-full').stdout

def test_license_and_missing_inputs(invoke):
    p=invoke('--license'); assert p.returncode==0 and 'GNU General Public License' in p.stdout and 'free software' in p.stdout
    p=invoke(); assert p.returncode==1 and 'No files specified. Try "executable --help".' in p.stderr

def test_unknown_options(invoke):
    for arg in ('--wat','-Z','-'):
        p=invoke(arg); assert p.returncode==1 and f'Unknown option: {arg}' in p.stderr

def test_print_language_mappings_and_force(invoke,tmp_path):
    names=['x.c','x.py','x.pyx','x.pxd','x.pxi','x.scons','x.wsgi','x.js','x.rb','x.go','x.rs','x.PY']
    for n in names: (tmp_path/n).write_text('')
    p=invoke('--print-language',*names); assert p.returncode==0
    m=dict(line.split(': ',1) for line in p.stdout.splitlines())
    for n,l in [('x.c','C'),('x.py','Python'),('x.js','JavaScript'),('x.rb','Ruby'),('x.go','Go'),('x.rs','Rust'),('x.PY','NONE')]: assert m[n]==l
    assert invoke('--language-force=InvalidLang','x.c').returncode==1
    p=invoke('--language-force=Python','--print-language','x.c'); assert 'x.c: Python' in p.stdout

def test_core_native_stdout_and_default_file(invoke,tmp_path):
    f=tmp_path/'sample.c'; f.write_text('struct MyStruct {\n    int field;\n};\nvoid func() {}\n')
    p=invoke('-o','-',f); assert p.returncode==0 and p.stderr==''
    rows=records(p.stdout); by={r[0]:r for r in rows}
    assert {'MyStruct','field','func'} <= by.keys()
    assert by['func'][2]=='/^void func() {}$/;"' and by['func'][3]=='f'
    assert 'typeref:typename:void' in by['func']
    assert invoke(f,cwd=tmp_path).returncode==0
    assert (tmp_path/'tags').exists()

def test_numeric_patterns_and_fields(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('int alpha;\n')
    p=invoke('--excmd=number','--fields=+nl','-o','-',f)
    assert p.returncode==0 and '\t1;"\t' in p.stdout and 'line:1' in p.stdout and 'language:C' in p.stdout
    assert invoke('--excmd=bogus',f).returncode==1
    assert invoke('--fields=+{notAField}',f).returncode==1

def test_sort_modes(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('int Zoo;\nint Apple;\nint zebra;\nint apple;\n')
    names=lambda p:[r[0] for r in records(p.stdout)]
    assert names(invoke('-o','-',f))==['Apple','Zoo','apple','zebra']
    assert names(invoke('-u','-o','-',f))==['Zoo','Apple','zebra','apple']
    assert names(invoke('--sort=foldcase','-o','-',f))==['Apple','zebra','Zoo']
    assert invoke('--sort=badval',f).returncode==1

def test_json_and_xref(invoke,tmp_path):
    f=tmp_path/'x.py'; f.write_text('class C:\n    def meth(self):\n        pass\ndef top():\n    pass\n')
    p=invoke('--output-format=json',f); assert p.returncode==0
    objs=[json.loads(x) for x in p.stdout.splitlines()]; tags=[o for o in objs if o.get('_type')=='tag']
    assert {'C','meth','top'} <= {o['name'] for o in tags}
    assert all({'name','path','kind'} <= o.keys() for o in tags)
    p=invoke('-x',f); assert p.returncode==0 and 'meth' in p.stdout and 'member' in p.stdout and not (tmp_path/'tags').exists()
    p=invoke('-x','--_xformat=%N|%K|%n','-o','-',f); assert 'meth|member|2' in p.stdout

def test_extras_and_file_scope(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('static int hidden;\nint visible;\n')
    p=invoke('--extras=-F','-o','-',f); assert p.returncode==0
    names={r[0] for r in records(p.stdout)}; assert 'hidden' not in names and 'visible' in names

def test_diagnostics(invoke,tmp_path):
    f=tmp_path/'x.c'; f.write_text('int x;\n')
    assert 'Invalid value for "sort" option' in invoke('--sort=badvalue',f).stderr
    assert 'Unsupported value for "format" option' in invoke('--format=3',f).stderr
    assert 'append mode is not compatible' in invoke('--append=yes','-o','-',f).stderr
    assert 'Unknown language "InvalidLang"' in invoke('--language-force=InvalidLang',f).stderr
