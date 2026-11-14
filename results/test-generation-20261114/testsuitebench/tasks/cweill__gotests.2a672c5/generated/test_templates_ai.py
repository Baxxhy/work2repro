import json, os, subprocess
from pathlib import Path
EXE=Path('/workspace/executable')
def run(args,cwd,env=None):
 e=os.environ.copy();e.update(env or {})
 return subprocess.run([str(EXE),*args],cwd=cwd,env=e,text=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=12)
def source(d,name='f.go',body='func Value() int { return 1 }'):
 p=d/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('package p\n'+body+'\n');return p

def test_template_params_and_bad_json(tmp_path):
 p=source(tmp_path)
 r=run(['-all','-template_params','{bad}',str(p)],tmp_path)
 assert r.returncode==0 and r.stdout.startswith('Failed to unmarshal template_params JSON:') and not r.stderr
 params=tmp_path/'params.json';params.write_text('{bad}')
 q=run(['-all','-template_params_file',str(params),str(p)],tmp_path)
 assert q.returncode==0 and q.stdout.startswith('Failed to umarshal '+str(params)+' er ')

def test_template_directory_load_errors(tmp_path):
 p=source(tmp_path)
 absent=run(['-all','-template_dir',str(tmp_path/'absent'),str(p)],tmp_path)
 assert absent.stdout==f'output.Process: loading custom templates: ioutil.ReadDir: open {tmp_path}/absent: no such file or directory\n'
 empty=tmp_path/'empty';empty.mkdir()
 r=run(['-all','-template_dir',str(empty),str(p)],tmp_path)
 assert r.stdout=='output.Process: loading custom templates: tmpls.ParseFiles: template: no files named in call to ParseFiles\n'

def test_custom_function_template_executes(tmp_path):
 p=source(tmp_path)
 td=tmp_path/'tmpl';td.mkdir()
 (td/'function.tmpl').write_text('{{define "function"}}func {{.TestName}}(t *testing.T) {}{{end}}')
 r=run(['-all','-template_dir',str(td),str(p)],tmp_path)
 assert r.returncode==0 and 'Generated TestValue' in r.stdout and 'func TestValue(t *testing.T)' in r.stdout

def test_testify_template_and_env_precedence(tmp_path):
 p=source(tmp_path,'f.go','func Value() int { return 1 }')
 r=run(['-all','-template','testify',str(p)],tmp_path)
 assert 'github.com/stretchr/testify/assert' in r.stdout and 'assert.Equal(t, tt.want, Value())' in r.stdout

def test_ai_validation_warning_and_order(tmp_path):
 p=run(['-ai','-ai-model=','-all'],tmp_path)
 assert p.returncode==1 and 'WARNING: Function source code will be sent to AI provider at http://localhost:11434' in p.stderr
 assert 'Error: -ai-model cannot be empty when using -ai flag' in p.stderr
 q=run(['-ai','-ai-min-cases=0','-ai-max-cases=101'],tmp_path)
 assert q.returncode==1 and 'must be at least 1, got 0' in q.stderr and 'must be at most 100' not in q.stderr

def test_ai_unreachable_is_graceful(tmp_path):
 p=source(tmp_path)
 r=run(['-ai','-all','-ai-endpoint','http://127.0.0.1:1',str(p)],tmp_path)
 assert r.returncode==0 and 'output.Process: AI provider ollama is not available' in r.stdout
 assert 'http://127.0.0.1:1' in r.stdout and 'WARNING:' in r.stderr

def test_existing_test_is_preserved_or_reported(tmp_path):
 p=source(tmp_path,'top.go','func Top() {}')
 (tmp_path/'top_test.go').write_text('package p\nfunc ExistingHelper() {}\n')
 r=run(['-all',str(p)],tmp_path)
 assert r.returncode==0 and 'output.Process: imports.Process:' in r.stdout
 assert 'Generated TestTop' not in r.stdout

def test_relative_execution_from_other_working_directory(tmp_path):
 root=tmp_path/'inputs';root.mkdir();source(root)
 other=tmp_path/'other';other.mkdir()
 rel=os.path.relpath(root/'f.go',other)
 r=run(['-all',rel],other)
 assert 'Generated TestValue' in r.stdout and 'package p' in r.stdout
