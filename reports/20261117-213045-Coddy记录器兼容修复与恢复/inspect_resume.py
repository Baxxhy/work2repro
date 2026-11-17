from pathlib import Path
import json,subprocess,time,hashlib
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');run=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th')
def rows(folder):
 out={}
 for f in folder.glob('*.jsonl'):
  for line in f.read_text().splitlines():
   x=json.loads(line);out[(x['instance_id'],x['mutant_id'])]=x
 return out
old=rows(root/'recorder-compat-20261117-v1/mutation-checkpoint');current=rows(run/'mutation');assert all(current.get(k)==v for k,v in old.items())
ids={'659aecc1f78ad83f','c87eec6495a2213d','124abcc9bfcbee6e'};iid='coddy-agent/features/subagents_http.feature:42';s=json.loads((root/'state.json').read_text());jobs=[j for j in s['jobs'].values() if j['state']=='running'];targets=[v for (i,m),v in current.items() if i==iid and m in ids]
jobs=[{**{k:j.get(k) for k in ['id','pid','workers','state','path']},'log':(Path(j['path'])/'job.log').read_text()[-5000:]} for j in jobs]
print(json.dumps(dict(time=time.time(),service=subprocess.check_output(['systemctl','show',root.name,'-p','ActiveState','-p','MainPID','-p','InvocationID'],text=True),progress=json.loads((root/'progress.json').read_text()),jobs=jobs,preserved=len(old),current_pairs=len(current),new_pairs=len(current)-len(old),fixed_target_rows=targets,official_repo_status=subprocess.check_output(['git','-c','safe.directory=/root/lby-docker/req2test/user/repo','-C','/root/lby-docker/req2test/user/repo','status','--short'],text=True)),ensure_ascii=False,indent=2))
