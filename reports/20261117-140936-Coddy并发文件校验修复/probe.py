import subprocess,json,time,concurrent.futures,sys
from pathlib import Path
from r2t_inventory_batch import patch_support
source=Path('/root/lby-docker/req2test/user/repo/benchmark/r2t/go/execution_support.sh').read_text()
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
base=['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','docker','--host','unix:///run/user/1001/req2test-docker-10156f49/docker.sock']
names=subprocess.check_output(base+['ps','--filter','name=coddy_agent_e1c14983c_go_','--format','{{.Names}}'],text=True).split()
inspection=json.loads(subprocess.check_output(base+['inspect']+names))
summary=[{'name':x['Name'],'pid_mode':x['HostConfig']['PidMode'],'network_mode':x['HostConfig']['NetworkMode'],'mounts':x['Mounts']} for x in inspection]
def one(name,code):
 start=time.monotonic()
 try:
  r=subprocess.run(base+['exec',name,'bash','-c',code,'probe','inventory','/work'],capture_output=True,timeout=60)
  import hashlib
  return dict(name=name,seconds=time.monotonic()-start,rc=r.returncode,sha256=hashlib.sha256(r.stdout).hexdigest(),stderr=r.stderr.decode()[:300])
 except subprocess.TimeoutExpired:return dict(name=name,seconds=time.monotonic()-start,timeout=True)
results={'isolation':summary}
for label,code in [('batched',patch_support(source)),('original',source)]:
 with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:results[label]=list(pool.map(lambda name:one(name,code),names))
 print(label,[(round(x['seconds'],2),x.get('rc')) for x in results[label]],flush=True)
Path('/tmp/r2t-inventory-probe.json').write_text(json.dumps(results,indent=2))
