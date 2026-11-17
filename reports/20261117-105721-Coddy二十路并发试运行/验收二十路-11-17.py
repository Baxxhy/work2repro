import pathlib,json,subprocess,collections,time,re
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');backup=root/'concurrency-change-20261117-105721'
folder=pathlib.Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th')
def read_rows(f):
 rows=[]
 if f.exists():
  for l in f.read_text().splitlines():
   try:rows.append(json.loads(l))
   except ValueError:pass
 return rows
before={}
for f in backup.glob('mutation-*.jsonl'):
 for r in read_rows(f):before[(r['instance_id'],r['mutant_id'])]=r
current={};files={}
for f in (folder/'mutation').glob('*.jsonl'):
 rows=read_rows(f);files[f.name]=len(rows)
 for r in rows:current[(r['instance_id'],r['mutant_id'])]=r
assert before.keys()<=current.keys()
assert all(current[k]==v for k,v in before.items())
s=json.loads((root/'state.json').read_text());active=[j for j in s['jobs'].values() if j['state']=='running'];j,=active;assert j['workers']==20
nonce=re.search(r'environment (e[0-9a-f]+)',(pathlib.Path(j['path'])/'job.log').read_text())[1]
q=pathlib.Path('/root/lby-docker/req2test/user/benchmark/envs/coddy-agent')/nonce/'qualification'
gold=[{'file':f.name,**{k:r.get(k) for k in ['outcome','exit_codes','execution_seconds']}} for f in q.glob('gold-control.w*.jsonl') for r in read_rows(f)]
raw=[]
for f in folder.glob('mutation-raw/**/cand-w*.jsonl'):
 rs=read_rows(f);raw.append({'file':str(f),'rows':len(rs),'latest_seconds':[r.get('seconds') for r in rs[-3:]],'latest_outcomes':[r.get('outcome') for r in rs[-3:]]})
print(json.dumps({'service':subprocess.check_output(['systemctl','show',root.name,'-p','ActiveState','-p','MainPID','-p','InvocationID'],text=True),'config_change':json.loads((backup/'configuration-change.json').read_text()),'switch':json.loads((backup/'switch.json').read_text()),'gold':gold,'preserved_pairs':len(before),'current_pairs':len(current),'new_pairs':len(current)-len(before),'files':files,'raw_workers':raw,'job':{k:j.get(k) for k in ['id','pid','workers','path','start']},'job_log':(pathlib.Path(j['path'])/'job.log').read_text(),'progress':json.loads((root/'progress.json').read_text()),'resource_watch_tail':(root/'coddy-resource-watch.jsonl').read_text().splitlines()[-12:],'revised_policy':json.loads((backup/'revised-resource-policy.json').read_text()),'current_config':json.loads((root/'frozen/config.json').read_text())},indent=2))
