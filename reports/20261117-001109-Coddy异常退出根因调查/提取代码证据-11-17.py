import json,pathlib,subprocess,tarfile
h=pathlib.Path('/root/lby-docker/req2test/user/benchmark')
ids={'067d32a367e1f45f','4e6505b87460587e','a9b81946ed00195a','275ee7bf98602829','53e3121a97c34639'}
d=json.loads(subprocess.check_output(['zstd','-dc',str(h/'kits/coddy-agent/1.2/mutation/manifest.json.zst')]))
ms=[m for m in d['mutants'] if m['id'] in ids]
out={'mutants':ms,'source':{}}
with tarfile.open(h/'engine/inputs/coddy-agent/1.2-c1a6c0994b53/seed/workspace.tar') as t:
 for m in t:
  for x in ms:
   if m.name.endswith(x['file']):
    lines=t.extractfile(m).read().decode().splitlines();a=x['start_line'];out['source'][x['file']]='\n'.join(f'{i+1}: {l}' for i,l in enumerate(lines) if a-10<=i+1<=a+35)
   if m.name.endswith('external/httpserver/server.go'):
    lines=t.extractfile(m).read().decode().splitlines()
    out['source'][m.name]='\n'.join(f'{i+1}: {l}' for i,l in enumerate(lines) if any(z in l for z in ['func (s *Server) Drain','cancelCodexAuthLogins','cancelNeuralDeepAuthLogins','StopAll','removeUsageObserver','removeTurnObserver']))
p=h/'runs/req2test-subset160-infra-recovery-20261116-v1/coddy-agent/th/predictions.norm.jsonl'
out['candidate']=next(json.loads(l) for l in p.read_text().splitlines() if json.loads(l)['instance_id'].endswith('subagents_http.feature:32'))
print(json.dumps(out,ensure_ascii=False,indent=2))
