import pathlib,json,subprocess,hashlib,time
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1');backup=root/'concurrency-change-20261117-101627'
assert (root/'jobs/fbb0aaeae93541c0b52891b632a27e65/exit.json').exists(), 'Wait for official cancellation cleanup'
subprocess.run(['systemctl','stop',root.name],check=True)
s=json.loads((root/'state.json').read_text())
for key in ['50fefa76ab4549f5a0c0737f5dfcfb90','fbb0aaeae93541c0b52891b632a27e65']:
 s['jobs'][key]['planned_concurrency_change']=True
(root/'state.json').write_text(json.dumps(s,indent=2))
f=root/'frozen/config.json';c=json.loads(f.read_text());assert c['coddy_eval_workers']==2;c['coddy_eval_workers']=3;f.write_text(json.dumps(c,indent=2))
f=root/'control/controller.py';before=f.read_text();old="tries=sum(x['phase']==phase and x['key']==key for x in S['jobs'].values())";new="tries=sum(x['phase']==phase and x['key']==key and not x.get('planned_concurrency_change') for x in S['jobs'].values())";assert old in before;f.write_text(before.replace(old,new))
# Check the exact production expression against planned switches and genuine failures.
phase='eval_req_project';key='coddy-agent'
S={'jobs':{'a':{'phase':phase,'key':key,'planned_concurrency_change':True},'b':{'phase':phase,'key':key,'planned_concurrency_change':True},'c':{'phase':phase,'key':key}}}
ns={'phase':phase,'key':key,'S':S};exec(new,ns);assert ns['tries']==1
for x in S['jobs'].values():x.pop('planned_concurrency_change',None)
exec(new,ns);assert ns['tries']==3
subprocess.run(['/usr/bin/python3','-m','py_compile',str(f)],check=True)
r={'time':time.time(),'workers_before':2,'workers_after':3,'planned_switch_jobs_marked':2,'real_failure_budget_unchanged':3,'retry_expression_tests_passed':2,'controller_before_sha256':hashlib.sha256(before.encode()).hexdigest(),'controller_after_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'retry_old_expression':old,'retry_new_expression':new}
(backup/'config-change.json').write_text(json.dumps(r,indent=2))
cmd=json.loads((root/'service-command.json').read_text());p=subprocess.run(cmd,text=True,capture_output=True);print(p.stdout,p.stderr);assert p.returncode==0
