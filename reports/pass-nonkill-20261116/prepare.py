import pathlib,json,hashlib,collections
r=pathlib.Path(__file__).resolve().parent;b=r.parents[1]/'publication/work2repro/results/test-generation-20261114';rows=[json.loads(l) for l in (b/'reports/req2test-per-task.jsonl').read_text().splitlines()];ex=json.loads((b/'reports/req2test-denominators-and-exclusions.json').read_text())['official_population']['excluded'];scored=[x for x in rows if x['instance_id'] not in ex];passed=[x for x in scored if x['passed']];non=[x for x in passed if not x['kill_complete']];controls=[x for x in passed if x['kill_complete']];assert (len(rows),len(scored),len(passed),len(non),len(controls))==(160,159,44,24,20)
selected=[];counts=collections.Counter()
for x in sorted(controls,key=lambda x:hashlib.sha256(x['instance_id'].encode()).hexdigest()):
 if not counts[x['project']]:selected.append(x);counts[x['project']]+=1
for x in sorted(controls,key=lambda x:hashlib.sha256(x['instance_id'].encode()).hexdigest()):
 if len(selected)>=10:break
 if x not in selected:selected.append(x)
a={x['instance_id']:x for x in json.loads((b/'task-artifacts.json').read_text())}
m=dict(nonkill=[dict(x,artifact=a[x['instance_id']]) for x in non],controls=[dict(x,artifact=a[x['instance_id']]) for x in selected],denominators=dict(manifest=160,scored=159,pass_count=44,killcomplete=20,nonkill=24),exclusions=ex,control_rule='one per available project ordered by SHA256(instance_id), then deterministic top-up to ten; report matching limitations',source_sha256=hashlib.sha256((b/'reports/req2test-per-task.jsonl').read_bytes()).hexdigest())
p=r/'manifest.json'
if p.exists():assert json.loads(p.read_text())==m
else:p.write_text(json.dumps(m,indent=2))
print('fixed',len(non),len(selected),'controls',collections.Counter(x['project'] for x in selected))
