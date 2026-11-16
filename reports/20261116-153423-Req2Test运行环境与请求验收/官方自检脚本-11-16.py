import subprocess,os,signal,json
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
cmd=['nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec req2test runtime preflight --project python-docx --workspace-root /root/lby-docker/req2test/user/runs/protocol-probe-20261116']
results=[]
for project in ['algorand-sdk','kapua','coddy-agent','coreshop','sylius','prestashop','e-petitions']:
 command=cmd[:-1]+[cmd[-1].replace('--project python-docx','--project '+project)]
 p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 try:
  out,err=p.communicate(timeout=60);r={'exit':p.returncode,'stdout':out,'stderr':err}
 except subprocess.TimeoutExpired:
  os.killpg(p.pid,signal.SIGKILL);out,err=p.communicate();r={'timeout_seconds':60,'stdout':out,'stderr':err}
 results.append(dict(project=project,**r))
print(json.dumps(results))
