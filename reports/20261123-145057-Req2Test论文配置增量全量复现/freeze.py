import collections,csv,hashlib,json,re,subprocess,sys
from pathlib import Path
h=Path('/root/lby-docker/req2test/user')
base=Path('/root/Baxxhy/work2/reproductions/req2test')
old='req2test-paired80-20261123-b'
p=base/old
o=h/'runs'/old
def rows(f):return [json.loads(l) for l in f.open() if l.strip()]
def sha(f):return hashlib.sha256(f.read_bytes()).hexdigest()
def index(rs):
 d={r['instance_id']:r for r in rs}
 assert len(d)==len(rs)
 return d
u=index(rows(h/'benchmark/data/dataset-v1.1/eval.jsonl'))
m=index([r for f in (h/'tasks').glob('*.eval.jsonl') for r in rows(f)])
s=json.loads((p/'state.json').read_text())
j={x['key']:x for x in s['jobs'].values() if x['phase']=='gen_req'}
assert len(u)==2051 and u.keys()==m.keys() and len(j)==len(s['tasks'])==80
assert all(r['view']=='th' and r['benchmark_version']=='1.1' for r in m.values())
binary=Path('/root/lby-docker/req2test/paper-cli-01534/package/vendor/x86_64-unknown-linux-musl/bin/codex')
assert subprocess.check_output([binary,'--version'],text=True).strip()=='codex-cli 0.153.4'
adapter=(o/'agent.py').read_text()
assert str(binary.parent) in adapter and 'runner.packs.setup_attempt=without_pack' in adapter
assert 'CALLS = 200' in (h/'repo/req2test/inference/run_agent.py').read_text()
oldrows=index([r for f in (o/'input').glob('regenerated-*.jsonl') for r in rows(f)])
first=index([r for f in (h/'benchmark/runs').glob(old+'-regenerated-*/*/th/instances.jsonl') for r in rows(f)])
reuse=[]
for k,t in sorted(s['tasks'].items()):
 i=t['id']; job=Path(j[k]['path']); argv=json.loads((job/'spec.json').read_text())['argv']; req=json.loads((job/'first-provider-request.json').read_text())
 f=Path(t['prediction']); trace=f.parent/'workspaces/0000.log'; row,=rows(f)
 assert f.is_relative_to(o/'generation') and row==oldrows[i] and row['instance_id']==i and row['view']=='th' and row['model_name_or_path']=='codex-gpt-6-luna-high'
 assert req['model']=='gpt-6-luna' and req['reasoning']['effort']=='high' and 'PAIRED_ARM=b' in argv and str(o/'agent.py') in argv and argv[argv.index('--timeout')+1]=='3600'
 assert rows(Path(argv[argv.index('--tasks')+1]))==[m[i]] and i in first and t['gen_attempts']==1
 calls=int(re.search(r'run_agent: exit 0 after (\d+) LLM call',trace.read_text()).group(1));assert 0<calls<=200
 reuse.append(dict(instance_id=i,project=t['project'],prediction=str(f),prediction_sha256=sha(f),trace_sha256=sha(trace),calls=calls,first_outcome=first[i]['outcome']))
b={r['instance_id'] for r in reuse}; rest=sorted(set(u)-b); assert len(b)==80 and len(rest)==1971 and not b.intersection(rest) and set(rest)|b==set(u)
print(json.dumps(dict(reuse=reuse,pending=[dict(instance_id=i,project=u[i]['project']) for i in rest],binary_sha256=sha(binary),adapter_sha256=sha(o/'agent.py'),dataset_sha256=sha(h/'benchmark/data/dataset-v1.1/eval.jsonl'),overlap=0)))
