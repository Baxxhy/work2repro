"""Compare recorded A/B and developer-control evaluator identities; no auth material."""
from pathlib import Path
import json,sys,hashlib
w=Path(sys.argv[1])
base=Path.home()/'benchmark/runs'
prefix='req2test-paired80-20261123-'
projects=['algorand-sdk','coddy-agent','coreshop','e-petitions','kapua','prestashop','python-docx','sylius']
def inspect(run,project):
    folder=base/run/project/'th'
    envptr=json.loads((folder/'env.json').read_text())
    env=json.loads(Path(envptr['record']).read_text())
    handle=env['handle'];q=env['qualification']['checks']
    execrows=folder/'exec.jsonl'
    commits=set()
    if execrows.exists():
        for l in execrows.open():
            r=json.loads(l)
            if r.get('harness_commit'):commits.add(r['harness_commit'])
    profiles=['profile','release_items']
    digests={k:hashlib.file_digest(open(handle[k],'rb'),'sha256').hexdigest() if hasattr(hashlib,'file_digest') else hashlib.sha256(Path(handle[k]).read_bytes()).hexdigest() for k in profiles}
    return dict(run=run,env_id=envptr['nonce'],workers=handle['k'],image_id=handle['image_id'],kit=handle['kit_version'],profile=handle['profile'],release=handle['release_items'],current_config_sha=digests,engine_commits=sorted(commits),qualification={k:v for k,v in q.items() if k in ('reset-probe','probe','harden')},control_worker_status={k:y['outcome'] for k,y in (q.get('gold_control') or {}).get('workers',{}).items()})
for_project={}
for p in projects:
    control=('req2test-paired80-gold-1123-'+p) if p in ('coreshop','sylius') else ('r2t-di-1123-'+w.name[:15]+'-gold-'+p)
    runs={'A':prefix+'a-regenerated-'+p,'B':prefix+'b-regenerated-'+p,'gold':control}
    items={key:inspect(run,p) for key,run in runs.items()}
    equal={k:len({json.dumps(y[k],sort_keys=True) for y in items.values()})==1 for k in ('kit','image_id','profile','release','current_config_sha','engine_commits')}
    for_project[p]=dict(matches=equal,records=items)
print(json.dumps(for_project,indent=2,ensure_ascii=False))
