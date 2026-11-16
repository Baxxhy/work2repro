import http.server,json,subprocess,threading,tempfile,os,pathlib
captured=[]
class Handler(http.server.BaseHTTPRequestHandler):
 def do_POST(self):
  body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
  captured.append({k:body.get(k) for k in ('model','reasoning','max_output_tokens')})
  self.send_response(400); self.send_header('Content-Type','application/json'); self.end_headers()
  self.wfile.write(b'{"error":{"message":"Intentional offline audit stop","type":"invalid_request_error"}}')
 def log_message(self,*args): pass
server=http.server.HTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
cli='/root/lby-docker/req2test/agent/bin/codex'
catalog='/root/lby-docker/req2test/user/repo/req2test/data/codex_models.json'
with tempfile.TemporaryDirectory(prefix='payload-',dir='/root/lby-docker/req2test/protocol-probe-20261116') as directory:
 settings=['model_reasoning_effort=medium','model_provider=offline_audit',f'model_providers.offline_audit={{name="Offline audit",base_url="http://127.0.0.1:{server.server_port}",wire_api="responses",requires_openai_auth=false,request_max_retries=0,stream_max_retries=0}}',f'model_catalog_json="{catalog}"','web_search="disabled"','features.multi_agent=false','features.apps=false','features.memories=false','features.hooks=false']
 command=[cli,'exec','--ephemeral','--ignore-user-config','--ignore-rules','--model','gpt-6-luna']+[arg for setting in settings for arg in ('-c',setting)]+['--dangerously-bypass-approvals-and-sandbox','--skip-git-repo-check','--json','-']
 environment={'PATH':'/usr/bin:/bin','HOME':directory,'NO_PROXY':'127.0.0.1,localhost'}
 version=subprocess.run([cli,'--version'],env=environment,capture_output=True,text=True)
 try:
  result=subprocess.run(command,input='Reply OK.',text=True,capture_output=True,cwd=directory,env=environment,timeout=60)
  output={'version':version.stdout.strip(),'request':captured,'exit':result.returncode,'stdout':result.stdout[-2000:],'stderr':result.stderr[-2000:],'real_provider_calls':0}
 except subprocess.TimeoutExpired as error:
  output={'version':version.stdout.strip(),'request':captured,'timeout':True,'stdout':str(error.stdout)[-2500:],'stderr':str(error.stderr)[-2500:],'real_provider_calls':0}
 print(json.dumps(output))
server.shutdown()
