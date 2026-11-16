import pathlib,json,subprocess,time,hashlib
name='req2test-eval2051-resume-20261117-v1';root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test')/name
assert (root/'preparation-summary.json').exists()
s=json.loads((root/'state.json').read_text());s['reused_generations']=2020
s['generation_cap']=8;s['evaluation_cpu_budget']=8;s['network_error_times']=[];s['events_429']=0;s['request_retries']=0;s['build_cap']=1
prior=json.loads((root/'parent-progress.json').read_text());s['prior_known_token_usage']=prior.get('known_total_token_usage',{})
(root/'state.json').write_text(json.dumps(s,indent=2))
p=root/'control/controller.py';code=p.read_text().replace('total_usage=usage.copy()',"total_usage=usage.copy()\n    total_usage.update(S.get('prior_known_token_usage',{}))")
p.write_text(code)
p=root/'control/final_report.py';p.write_text(p.read_text().replace('prior-generation-reuse.json','current-generation-reuse.json'))
subprocess.run(['/usr/bin/python3','-m','py_compile',str(root/'control/controller.py'),str(root/'control/final_report.py')],check=True)
freeze={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for folder in ['control','frozen'] for p in (root/folder).glob('*.py' if folder=='control' else '*.json')}
(root/'resume-frozen-sha256.json').write_text(json.dumps(freeze,indent=2))
cmd=['systemd-run','--unit='+name,'--service-type=exec','--property=WorkingDirectory='+str(root),'--property=Restart=on-failure','--property=RestartSec=30','--property=StartLimitIntervalSec=3600','--property=StartLimitBurst=3','--property=Environment=HTTP_PROXY=http://127.0.0.1:7890 HTTPS_PROXY=http://127.0.0.1:7890 NO_PROXY=127.0.0.1,localhost','--property=StandardOutput=append:'+str(root/'controller.log'),'--property=StandardError=append:'+str(root/'controller.log'),'/usr/bin/python3','-u',str(root/'control/controller.py'),str(root)]
(root/'service-command.json').write_text(json.dumps(cmd,indent=2));result=subprocess.run(cmd,text=True,capture_output=True);print(result.stdout,result.stderr);raise SystemExit(result.returncode)
