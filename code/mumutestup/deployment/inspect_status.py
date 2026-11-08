"""Read-only status of this deployment; does not launch, terminate or delete anything."""
from pathlib import Path
import json, os, urllib.request, subprocess, datetime
r=Path('/root/Baxxhy/work2/reproductions/mumutestup')
result={'timestamp':datetime.datetime.now(datetime.timezone.utc).isoformat()}
for key,pid in {'qwen':2576668,'qwen_probe':2578899,'setup':2577914,'repos':2577968,'embedding':2578025}.items():
    p=Path('/proc')/str(pid)
    result.setdefault('processes',{})[key]={'pid':pid,'alive':p.exists()}
    if p.exists():
        try: result['processes'][key]['comm']=(p/'comm').read_text().strip()
        except OSError: pass
for key,rel in [('repositories','repository-preparation.json'),('qwen_verification','deployment/qwen-concurrency-verification.json')]:
    p=r/rel
    if p.exists():
        d=json.loads(p.read_text())
        if key=='repositories':result[key]={'ready':len([x for x in d['projects'] if 'error' not in x]),'expected':d['expected_projects'],'errors':[x for x in d['projects'] if 'error' in x]}
        else: result[key]={k:d.get(k) for k in ['all_passed','client_concurrency','aggregate_completion_tokens_per_second']}
for rel in ['logs/qwen35-server.log','logs/clone-apache_druid.log','logs/finish-setup.log']:
    p=r/rel
    if p.exists():
        with p.open('rb') as f:f.seek(max(0,p.stat().st_size-5000));s=f.read().decode(errors='replace')
        result.setdefault('log_tails',{})[rel]=s.replace('\r','\n').splitlines()[-3:]
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
for name,url in [('qwen','http://127.0.0.1:8000/health'),('embedding','http://127.0.0.1:8001/health')]:
    try:
        with opener.open(url,timeout=3) as response: result.setdefault('health',{})[name]=response.status
    except Exception as e:result.setdefault('health',{})[name]=str(e)
result['experiment_started']=(r/'runs/smoke-ormlite-20261030/status.json').exists() or (r/'runs/qwen27b-full/status.json').exists()
print(json.dumps(result,ensure_ascii=False,indent=2))
