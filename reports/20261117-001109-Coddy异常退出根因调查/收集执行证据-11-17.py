import pathlib,json,subprocess
home=pathlib.Path('/root/lby-docker/req2test/user')
work=home/'runs/req2test-coddy-exit-diagnosis-20261117-v1'
rows=[]
for d in sorted((work/'native-evidence').iterdir()):
 c=json.loads((d/'capture.json').read_text());m=(c.get('mutation') or {}).get('descriptor')
 if not m:continue
 rows.append({'mutant':m,'returncode':c['returncode'],'context':c['context'],'stdout':(d/'stdout.txt').read_text(),'native':(d/'native.jsonl').read_text()})
out={'captures':rows,'service':subprocess.check_output(['systemctl','show','req2test-coddy-exit-diagnosis-20261117-v1','-p','ActiveState','-p','ExecMainStatus'],text=True),'log':(work/'official-evaluate.log').read_text(),'source':{}}
repo=home/'repo'
for file,a,b in [('benchmark/r2t/bench/harness.py',610,643),('benchmark/r2t/go/runtime.py',418,477),('benchmark/r2t/go/registry.py',344,377),('req2test/mutate.py',799,828),('benchmark/r2t/data/mutation.py',260,301)]:
 lines=(repo/file).read_text().splitlines();out['source'][file]='\n'.join(f'{i+1}: {l}' for i,l in enumerate(lines) if a<=i+1<=b)
p=home/'benchmark/runs/req2test-coddy-exit-diagnosis-20261117-v1/coddy-agent/th/mutation/w0.jsonl'
out['final_rows']=p.read_text() if p.exists() else ''
print(json.dumps(out,ensure_ascii=False))
