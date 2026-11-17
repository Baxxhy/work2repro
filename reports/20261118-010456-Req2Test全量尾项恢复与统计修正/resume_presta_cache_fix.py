from pathlib import Path
import json,subprocess,shutil,time
p=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');assert subprocess.check_output(['systemctl','show',p.name,'-p','ActiveState','--value'],text=True).strip()=='inactive'
b=p/'tail-recovery-20261118-v1/presta-cache-fix-v2';b.mkdir()
for rel in ['state.json','progress.json','frozen/config.json','completion.json']:shutil.copy2(p/rel,b/Path(rel).name)
s=json.loads((p/'state.json').read_text());assert not any(j['state']=='running' for j in s['jobs'].values());s['projects']['prestashop']='pending'
for t in s['tasks'].values():
 if t.get('project')=='prestashop' and t['evaluation']=='infra_blocked':t['evaluation']='pending'
s['final_report_done']=False;s.pop('final_report_blocked',None);s['final_audit_attempts']=0;(p/'state.json').write_text(json.dumps(s,indent=2))
c=json.loads((p/'frozen/config.json').read_text());c['timeout_profile']='extended-20261117-v1-tail-recovery2';c['recovery_profile']='full-tail-recovery-20261118-v2';(p/'frozen/config.json').write_text(json.dumps(c,indent=2));(p/'completion.json').rename(b/'completion-before-resume.json')
r=subprocess.run(json.loads((p/'service-command.json').read_text()),capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0
print(json.dumps(dict(time=time.time(),scope='two PrestaShop infrastructure rows only',official_mutation_complete_reused=True,model_calls=0)))
