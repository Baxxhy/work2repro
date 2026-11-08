import concurrent.futures, hashlib, json, os, pathlib, subprocess, time
R=pathlib.Path(os.environ['MUMU_ROOT'])
paths=sorted((R/'upstream/dataset').glob('*/*/data.json'))
assert paths, 'Official dataset missing'
def prepare(p):
    project='/'.join(p.parts[-3:-1]); dest=R/'repos'/project;dest.parent.mkdir(parents=True,exist_ok=True)
    rows=json.loads(p.read_text()); log=R/'logs'/('clone-'+project.replace('/','_')+'.log')
    with log.open('a') as out:
        if not (dest/'.git').exists():
            subprocess.run(['git','clone','https://github.com/'+project+'.git',str(dest)],stdout=out,stderr=out,check=True)
        commits=sorted({row[k] for row in rows for k in ('aCommit','bCommit')})
        for commit in commits:
            result=subprocess.run(['git','cat-file','-e',commit+'^{commit}'],cwd=dest,stdout=out,stderr=out)
            if result.returncode:
                subprocess.run(['git','fetch','origin',commit],cwd=dest,stdout=out,stderr=out,check=True)
    return {'project':project,'samples':len(rows),'commits':len(commits),'dataset_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
results=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
    for f in concurrent.futures.as_completed([pool.submit(prepare,p) for p in paths]):
        try: result=f.result()
        except Exception as e: result={'error':str(e)}
        results.append(result); print(json.dumps(result),flush=True)
        (R/'repository-preparation.json').write_text(json.dumps({'timestamp':time.time(),'projects':results,'expected_projects':len(paths)},indent=2))
if any('error' in r for r in results): raise SystemExit(1)
print('ALL_REPOSITORIES_READY',flush=True)
