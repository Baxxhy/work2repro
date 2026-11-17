from pathlib import Path
import json,subprocess,shutil,os,re,time
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');cancel='5ac8d1d7b8d04e4dbf11b8798529ae8c'
assert (root/'jobs'/cancel/'exit.json').exists(),'Waiting for cancelled pool cleanup'
b=root/'concurrency-recovery-20261117-135859';assert not b.exists();b.mkdir()
subprocess.run(['systemctl','stop',root.name],capture_output=True)
for f in ['state.json','frozen/config.json','control/controller.py']:shutil.copy2(root/f,b/Path(f).name)
s=json.loads((root/'state.json').read_text());pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip();retired=[]
for key in ['be77c65a80f846d99c06124e734f9275','c23721042bdd4e2487844e531c656467',cancel]:
 j=s['jobs'][key];log=(Path(j['path'])/'job.log').read_text();nonce=re.search(r'environment (e[0-9a-f]+)',log)[1]
 cmd=['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test env down --project coddy-agent --nonce '+nonce]
 r=subprocess.run(cmd,text=True,capture_output=True,timeout=180);assert r.returncode==0 or 'no live environment' in r.stderr,r.stderr
 retired.append({'job':key,'nonce':nonce,'returncode':r.returncode})
 if key!=cancel:j['unstable_resource_attempt']=True;j['failure_reason']='worker_quarantined_at_workers_above20'
s['jobs'][cancel]['planned_concurrency_change']=True
source=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th')
checkpoint=Path(s['jobs']['be77c65a80f846d99c06124e734f9275']['resource_checkpoint'])
pairs=set()
for f in checkpoint.glob('*.jsonl'):
 for l in f.read_text().splitlines():
  r=json.loads(l);pairs.add((r['instance_id'],r['mutant_id']))
assert len(pairs)==2310
for name in ['mutation','mutation-raw','mutation.done.json']:
 if (source/name).exists():shutil.move(str(source/name),str(b/name))
(source/'mutation').mkdir();os.chown(source/'mutation',1001,1001)
for f in checkpoint.glob('*.jsonl'):
 dst=source/'mutation'/f.name;shutil.copy2(f,dst);os.chown(dst,1001,1001)
c=json.loads((root/'frozen/config.json').read_text());c.update(coddy_eval_workers=20,coddy_memory_reservation_gib=2,evaluation_max_cpu_budget=80);(root/'frozen/config.json').write_text(json.dumps(c,indent=2))
s['projects']['coddy-agent']='pending';s['evaluation_cpu_budget']=80;s['last_adapt']=time.time();s['final_report_done']=False;s.pop('final_report_blocked',None);(root/'state.json').write_text(json.dumps(s,indent=2))
p=root/'control/controller.py';code=p.read_text();old="and not x.get('planned_concurrency_change') for x in S['jobs'].values())";new="and not x.get('planned_concurrency_change') and not x.get('unstable_resource_attempt') for x in S['jobs'].values())";assert old in code;code=code.replace(old,new);p.write_text(code)
subprocess.run(['/usr/bin/python3','-m','py_compile',str(p)],check=True)
record={'restored_pairs':2310,'retired':retired,'failed_profiles':[28,32],'new_worker_cap':20,'new_profile_infrastructure_retry_limit':3,'old_failures_retained':True,'archive':str(b)};(b/'recovery.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
r=subprocess.run(json.loads((root/'service-command.json').read_text()),text=True,capture_output=True);print(r.stdout,r.stderr);assert r.returncode==0
