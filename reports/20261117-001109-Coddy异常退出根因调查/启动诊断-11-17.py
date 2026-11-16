import subprocess,json,pathlib
name='req2test-coddy-exit-diagnosis-20261117-v1'
work=pathlib.Path('/root/lby-docker/req2test/user/runs')/name
pid=subprocess.check_output(['systemctl','show','user@1001.service','-p','MainPID','--value'],text=True).strip()
command=['systemd-run','--unit='+name,'--service-type=exec','--property=WorkingDirectory='+str(work),'--property=StandardOutput=append:'+str(work/'official-evaluate.log'),'--property=StandardError=append:'+str(work/'official-evaluate.log'),'nsenter','-t',pid,'-m','--','runuser','-u','r2tbench','--','bash','-c','source /root/lby-docker/req2test/user/env.sh; exec python /root/lby-docker/req2test/user/runs/req2test-coddy-exit-diagnosis-20261117-v1/observe.py evaluate --predictions '+str(work/'predictions.jsonl')+' --instances '+str(work/'instances.txt')+' --split eval --workers 1 --run-id '+name]
(work/'service-command.json').write_text(json.dumps(command,indent=2))
r=subprocess.run(command,text=True,capture_output=True);print(r.stdout,r.stderr);print('exit',r.returncode)
