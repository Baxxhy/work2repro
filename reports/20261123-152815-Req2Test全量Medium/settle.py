"""Wait for the frozen queue, verify full provenance, then use official aggregation."""
import hashlib,json,subprocess,time
from pathlib import Path
d=Path(__file__).resolve().parent
name='req2test-medium-full-20261123'
p=Path('/root/Baxxhy/work2/reproductions/req2test')/name
h=Path('/root/lby-docker/req2test/user')
import csv
with (d/'全量任务-11-23.csv').open() as f: lock=dict(reuse=[],pending=list(csv.DictReader(f)))
def index(rows):
 out={r['instance_id']:r for r in rows}
 assert len(out)==len(rows)
 return out
def rows(path):return [json.loads(l) for l in path.open() if l.strip()]
original=index(lock['reuse']); new=index(lock['pending'])
while not (p/'completion.json').is_file():time.sleep(45)
s=json.loads((p/'state.json').read_text());data={};lineage={}
for group,g in s['groups'].items():
 assert g['state']=='finished',group
 role,project=group.split('-',1); assert role in ('original','regenerated')
 ids=set(g['ids']);assert ids<=set(original if role=='original' else new)
 inp=h/'runs'/name/'input'/(group+'.jsonl')
 predictions=index(rows(inp));assert set(predictions)==ids
 scores=index(rows(h/'benchmark/runs'/g['run']/project/'th/instances.jsonl'));assert set(scores)==ids
 assert not ids.intersection(data)
 for i in ids:
  source=Path(original[i]['prediction'] if role=='original' else s['tasks']['req:'+i]['prediction'])
  if role=='original':assert hashlib.sha256(source.read_bytes()).hexdigest()==original[i]['prediction_sha256']
  assert rows(source)==[predictions[i]] and predictions[i]['model_name_or_path']=='codex-gpt-6-luna-medium'
  assert scores[i]['project']==project and scores[i]['view']=='th'
  lineage[i]=dict(source=str(source),official_run=g['run'],cohort=role)
 data.update(scores)
missing=sorted((set(original)|set(new))-set(data))
(p/'settlement-coverage.json').write_text(json.dumps(dict(rows=len(data),missing=missing)))
assert not missing and len(data)==2051
script="""import sys,json
from req2test.aggregate import aggregate
from req2test.report import population_exclusions
rs=json.load(sys.stdin)
ex=population_exclusions('1.1')['excluded']
ag=aggregate(rs,excluded=ex)
cells=ag['cells']
assert len(cells)==8 and all(c['complete'] for c in cells.values())
den=sum(c['n']-c['excluded'] for c in cells.values())
passed=sum(c['passes'] for c in cells.values())
print(json.dumps(dict(total=len(rs),population_exclusions=ex,eligible_before_infrastructure=sum(c['n'] for c in cells.values()),pass_denominator=den,passed=passed,pooled=passed/den,official_macro=ag['mean']['th']['pass_at_1'],projects=cells),indent=2))
"""
r=subprocess.run(['runuser','-u','r2tbench','--','env','HOME='+str(h),'REQ2TEST_HOME='+str(h/'benchmark'),str(h/'venv/bin/python'),'-c',script],cwd=h/'repo',input=json.dumps(list(data.values())),text=True,stdout=subprocess.PIPE,check=True)
(p/'final-instances.jsonl').write_text(''.join(json.dumps(data[i])+'\n' for i in sorted(data)))
(p/'final-lineage.json').write_text(json.dumps(lineage))
(p/'final-pass-at-1.json').write_text(r.stdout)
