import subprocess,json,time
from pathlib import Path
r=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
jid='203bcbde69d949f4a4c2576334bbb812'
assert (r/'jobs'/jid/'exit.json').exists()
subprocess.run(['systemctl','stop',r.name],check=True)
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
x=subprocess.run(['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test env down --project coddy-agent --nonce e3c2b1b63'],capture_output=True,text=True,timeout=600)
assert x.returncode==0 or 'no live environment' in x.stderr,x.stderr
s=json.loads((r/'state.json').read_text());s['jobs'][jid]['planned_concurrency_change']=True;s['jobs'][jid]['stop_reason']='Complete helper and subprocess timeout audit before mutation';s['projects']['coddy-agent']='pending'
(r/'state.json').write_text(json.dumps(s,indent=2))
x=subprocess.run(json.loads((r/'service-command.json').read_text()),capture_output=True,text=True);print(x.stdout,x.stderr);assert x.returncode==0
