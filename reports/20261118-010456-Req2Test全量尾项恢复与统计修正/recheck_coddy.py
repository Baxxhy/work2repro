from pathlib import Path
import json,subprocess,time
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
s=json.loads((root/'state.json').read_text());assert not any(j['state']=='running' and j.get('key')=='coddy-agent' for j in s['jobs'].values())
job=root/'tail-recovery-20261118-v1/coddy-evidence-v2';job.mkdir(exist_ok=False)
spec=json.loads((root/'jobs/40e77ea539114517bff7a1fa56d173f1/spec.json').read_text());(job/'spec.json').write_text(json.dumps(spec,indent=2))
unit='req2test-tail-coddy-native-20261118-v2'
cmd=['systemd-run','--unit',unit,'--collect','--property=StandardOutput=append:'+str(job/'job.log'),'--property=StandardError=append:'+str(job/'job.log'),'--working-directory',str(root),'/usr/bin/python3',str(root/'control/job.py'),str(job/'spec.json')]
r=subprocess.run(cmd,capture_output=True,text=True);print(r.stdout,r.stderr);assert r.returncode==0
record=dict(time=time.time(),unit=unit,path=str(job),scope='only two prior infrastructure rows; completed executions and mutations reused',diagnostic_fix='capture metadata stored outside required empty evidence directory')
(job/'launch.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
