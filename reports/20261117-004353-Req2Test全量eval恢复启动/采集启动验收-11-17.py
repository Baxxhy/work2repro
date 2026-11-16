import pathlib,json,subprocess,collections,hashlib
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
s=json.loads((root/'state.json').read_text());cfg=json.loads((root/'frozen/config.json').read_text())
summary=json.loads((root/'preparation-summary.json').read_text())
assert len(s['tasks'])==2051 and summary['subset_reused']==160
assert sum(len(x['subset_ids']) for x in summary['projects'])==160
assert len({i for x in summary['projects'] for i in x['subset_ids']})==160
jobs=[]
for j in s['jobs'].values():
 record={k:j.get(k) for k in ['id','key','phase','pid','state','path','api_requests','returncode','workers','official_run_id']}
 if j['phase']=='gen_req':
  req=pathlib.Path(j['path'])/'first-provider-request.json'
  if req.exists():
   d=json.loads(req.read_text());assert d['model']=='gpt-6-luna' and d['reasoning']['effort']=='medium';record['verified_model']=d['model'];record['verified_reasoning']=d['reasoning']['effort']
  record['error_statuses']=[e.get('status') for e in j.get('api_errors',[])]
 jobs.append(record)
assert any(j.get('api_requests',0) for j in jobs if j['phase']=='gen_req')
service=subprocess.check_output(['systemctl','show',cfg['run_id'],'-p','ActiveState','-p','SubState','-p','MainPID','-p','InvocationID'],text=True)
assert 'ActiveState=active' in service
out={'service':service,'progress':json.loads((root/'progress.json').read_text()),'jobs':jobs,'recent_events':(root/'events.jsonl').read_text().splitlines()[-12:],'source_commit':subprocess.check_output(['git','-c','safe.directory=/root/lby-docker/req2test/user/repo','rev-parse','HEAD'],cwd=pathlib.Path(cfg['req_home'])/'repo',text=True).strip(),'official_repo_diff':subprocess.check_output(['git','-c','safe.directory=/root/lby-docker/req2test/user/repo','status','--porcelain'],cwd=pathlib.Path(cfg['req_home'])/'repo',text=True),'frozen_hashes':json.loads((root/'resume-frozen-sha256.json').read_text())}
print(json.dumps(out,ensure_ascii=False,indent=2))
