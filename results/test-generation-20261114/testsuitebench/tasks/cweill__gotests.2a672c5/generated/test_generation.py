import os, subprocess, tempfile
from pathlib import Path
EXE=Path('/workspace/executable')
def invoke(args, cwd):
    return subprocess.run([str(EXE),*args],cwd=cwd,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15)
def put(root, name, text):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);return p

def test_canonical_generation_and_signature_types(tmp_path):
    f=put(tmp_path,'math.go','package math\n\nfunc Add(a, b int) int { return a+b }\nfunc Ping() {}\n')
    p=invoke(['-all',str(f)],tmp_path)
    assert p.returncode==0 and not p.stderr
    assert p.stdout.startswith('Generated TestAdd\nGenerated TestPing\npackage math\n\nimport "testing"\n')
    assert 'func TestAdd(t *testing.T)' in p.stdout and 'a int\n\t\tb int' in p.stdout
    assert 'Add(tt.args.a, tt.args.b)' in p.stdout and 'got != tt.want' in p.stdout
    assert 'func TestPing(t *testing.T)' in p.stdout and '// TODO: Add test cases.' in p.stdout
    assert 'func init()' not in p.stdout

def test_selectors_combine_in_order(tmp_path):
    f=put(tmp_path,'p.go','package p\nfunc Foo() {}\nfunc food() {}\nfunc Bar() {}\n')
    cases=[(['-all','-only','Foo|Bar','-excl','Bar'],['TestFoo'],['TestBar','Test_food']),
           (['-all','-exported'],['TestFoo','TestBar'],['Test_food']),
           (['-excl','Foo'],['Test_food','TestBar'],['TestFoo'])]
    for args,yes,no in cases:
        p=invoke(args+[str(f)],tmp_path)
        for s in yes: assert s in p.stdout
        for s in no: assert s not in p.stdout

def test_method_receiver_and_results(tmp_path):
    f=put(tmp_path,'m.go','package p\ntype Thing struct { Value int }\nfunc (x *Thing) Add(a int) (int, error) { return x.Value+a, nil }\n')
    p=invoke(['-all',str(f)],tmp_path)
    assert 'func TestThing_Add' in p.stdout and 'type fields struct' in p.stdout
    assert '&Thing{' in p.stdout and 'wantErr bool' in p.stdout
    assert 'if (err != nil) != tt.wantErr' in p.stdout and 'if tt.wantErr {' in p.stdout

def test_named_nosubtests_parallel_and_inputs(tmp_path):
    f=put(tmp_path,'f.go','package p\nfunc Add(a, b int) int { return a+b }\n')
    p=invoke(['-all','-named','-nosubtests','-parallel','-i',str(f)],tmp_path)
    assert 'tests := map[string]struct {' in p.stdout and 'for name, tt := range tests' in p.stdout
    assert 't.Run(' not in p.stdout and 't.Parallel()' in p.stdout
    assert '"%q. Add(%v, %v) = %v, want %v", name, tt.args.a, tt.args.b' in p.stdout

def test_nosubtests_naked_and_writer(tmp_path):
    f=put(tmp_path,'w.go','package p\nimport "io"\nfunc Emit(x int, w io.Writer) int { return x }\n')
    p=invoke(['-all','-i','-nosubtests',str(f)],tmp_path)
    assert 'bytes.Buffer' in p.stdout and 'wantW string' in p.stdout
    assert 'tt.args.w' in p.stdout and 'Emit(%v, %v)' in p.stdout

def test_generic_and_cmp_modes(tmp_path):
    f=put(tmp_path,'g.go','package p\nfunc Identity[T any](x T) T { return x }\nfunc Values() []int { return nil }\n')
    p=invoke(['-all','-use_go_cmp',str(f)],tmp_path)
    assert 'Identity[int](tt.args.x)' in p.stdout and 'cmp.Equal' in p.stdout
    assert 'github.com/google/go-cmp/cmp' in p.stdout

def test_header_comments_crlf_and_write(tmp_path):
    f=tmp_path/'p.go';f.write_bytes('// π package\r\npackage _p\r\nfunc Go() {}\r\n'.encode())
    p=invoke(['-all','-w',str(f)],tmp_path)
    out=(tmp_path/'p_test.go').read_text()
    assert p.stdout=='Generated TestGo\n' and not p.stderr
    assert out.startswith('// π package\n\npackage _p\n')

def test_directory_discovery_and_recursive_paths(tmp_path):
    put(tmp_path,'root.go','package p\nfunc Root() {}\n')
    put(tmp_path,'sub/child.go','package p\nfunc Child() {}\n')
    put(tmp_path,'sub/child_test.go','package p\nfunc Existing() {}\n')
    p=invoke(['-all',str(tmp_path)],tmp_path)
    assert 'TestRoot' in p.stdout and 'TestChild' not in p.stdout
    q=invoke(['-all',str(tmp_path/'...')],tmp_path)
    assert 'TestRoot' in q.stdout and 'TestChild' in q.stdout

def test_missing_paths_and_empty_source(tmp_path):
    p=invoke(['-all',str(tmp_path/'missing'/'')],tmp_path)
    assert p.returncode==0 and 'input.Files: os.Stat: stat ' in p.stdout and 'no such file or directory\n\n' in p.stdout
    f=put(tmp_path,'empty.go','')
    q=invoke(['-all',str(f)],tmp_path)
    assert q.stdout=='Parser.Parse source file: file is empty\n'
