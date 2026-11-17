from pathlib import Path
import json,subprocess,shutil,time,sys,py_compile,hashlib
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
assert subprocess.check_output(['systemctl','show',root.name,'-p','ActiveState','--value'],text=True).strip()=='inactive'
backup=root/'tail-recovery-20261118-v1';backup.mkdir(exist_ok=False)
for rel in ['state.json','progress.json','frozen/config.json','control/controller.py','completion.json','final-task-audit.json','failures-and-unfinished.json']:
 if (root/rel).exists():shutil.copy2(root/rel,backup/Path(rel).name)
shutil.copy2('/tmp/work2-project-status.py',root/'control/project_status.py')
sys.path.insert(0,str(root/'control'));from project_status import apply_project_status
cfgp=root/'frozen/config.json';cfg=json.loads(cfgp.read_text());s=json.loads((root/'state.json').read_text());assert not any(j['state']=='running' for j in s['jobs'].values())
home=Path(cfg['req_home']);canonical=home/'benchmark/runs'/cfg['req_run_id'];audit={};snapshot={}
for project,run_id in s['project_run_ids'].items():
 source=home/'benchmark/runs'/run_id/project;target=canonical/project
 report=json.loads((home/'benchmark/runs'/run_id/'summary.json').read_text());disclosure=report.get('disclosures',{}).get(project+'/th',{})
 rows=[json.loads(l) for l in (source/'th/exec.jsonl').read_text().splitlines() if l.strip()]
 s['projects'][project]=apply_project_status(s['tasks'],project,rows,disclosure)
 audit[project]=dict(total=len(rows),infrastructure=disclosure.get('infrastructure_excluded',[]),outside=disclosure.get('outside_ladder_excluded',{}))
 snap=backup/'projects'/project;snap.mkdir(parents=True)
 for rel in ['th/exec.jsonl','th/mutation.done.json']:
  f=source/rel
  if f.exists():shutil.copy2(f,snap/Path(rel).name)
 if (source/'th/mutation').exists():shutil.copytree(source/'th/mutation',snap/'mutation')
 if not target.exists():source.rename(target);source.symlink_to(target,target_is_directory=True)
 for f in (target/'th').glob('*.jsonl'):snapshot[str(f)]=hashlib.sha256(f.read_bytes()).hexdigest()
for project in ['coddy-agent','prestashop']:
 s['projects'][project]='pending'
 for t in s['tasks'].values():
  if t.get('project')==project and t['evaluation']=='infra_blocked':t['evaluation']='pending'
wrapper='/root/lby-docker/req2test/recovery-control-20261113-v1/full-tail-recovery-20261118-v1'
cfg.update(diagnostic_eval_wrapper=wrapper+'/diagnostic_eval.py',recovery_profile='full-tail-recovery-20261118-v1',timeout_profile='extended-20261117-v1-tail-recovery1',coddy_eval_workers=2,eval_worker_max=2,evaluation_max_cpu_budget=16)
cfgp.write_text(json.dumps(cfg,indent=2))
p=root/'control/controller.py';text=p.read_text();assert 'from project_status import' not in text;text='from project_status import apply_project_status\n'+text
text=text.replace("PYTHONPATH='/root/lby-docker/req2test/recovery-control-20261113-v1/recorder-compat-20261117-v1:'","PYTHONPATH='"+wrapper+":'")
a=text.index("        if rc==0 and not infrastructure:\n");b=text.index("        return\n    if phase=='final_req_report':",a)
text=text[:a]+'''        if rc==0:
            merge_project_output(project,run_id)
            folder=RH/'benchmark/runs'/CFG['req_run_id']/project/'th'
            rows=[json.loads(line) for line in (folder/'exec.jsonl').read_text().splitlines() if line.strip()]
            disclosure=json.loads(report.read_text()).get('disclosures',{}).get(project+'/th',{})
            S['projects'][project]=apply_project_status(S['tasks'],project,rows,disclosure)
            event('project_official_results_accounted',project=project,state=S['projects'][project],infrastructure=infrastructure)
        elif tries<2:S['projects'][project]='pending'
        else:
            S['projects'][project]='infra_blocked'
            for task in S['tasks'].values():
                if task['benchmark']=='req2test' and task['project']==project and task['evaluation']!='finished':task['evaluation']='infra_blocked'
'''+text[b:]
p.write_text(text);py_compile.compile(str(p),doraise=True)
s['evaluation_cpu_budget']=16;s['final_report_done']=False;s.pop('final_report_blocked',None);s['final_audit_attempts']=0;s['last_adapt']=time.time();s['final_report_attempts']=0
(root/'state.json').write_text(json.dumps(s,indent=2))
if (root/'completion.json').exists():(root/'completion.json').rename(backup/'completion-before-resume.json')
(backup/'source-artifact-sha256.json').write_text(json.dumps(snapshot,indent=2));(backup/'population-audit.json').write_text(json.dumps(audit,indent=2))
record=dict(time=time.time(),kind='full_eval_tail_recovery',manifest_total=len(s['tasks']),finished=sum(t['evaluation']=='finished' for t in s['tasks'].values()),pending=sum(t['evaluation']=='pending' for t in s['tasks'].values()),project_workers=2,projects=['coddy-agent','prestashop'],generation_calls=0,completed_mutations_preserved=True)
(backup/'deployment.json').write_text(json.dumps(record,indent=2))
with (root/'events.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
r=subprocess.run(json.loads((root/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0;print(json.dumps(record))
