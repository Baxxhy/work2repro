import pathlib,json,os,signal,shutil,time,subprocess
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
backup=root/'concurrency-change-20261117-100109';assert not backup.exists();backup.mkdir()
controller=int(subprocess.check_output(['systemctl','show',root.name,'-p','MainPID','--value'],text=True));assert controller>0
os.kill(controller,signal.SIGSTOP)
for file in ['state.json','progress.json','frozen/config.json','resume-frozen-sha256.json']:
 shutil.copy2(root/file,backup/pathlib.Path(file).name)
s=json.loads((root/'state.json').read_text());job,=[j for j in s['jobs'].values() if j['state']=='running'];assert job['key']=='coddy-agent'
folder=pathlib.Path('/root/lby-docker/req2test/user/benchmark/runs')/job['official_run_id']/'coddy-agent/th/mutation'
pairs=[]
for file in folder.glob('*.jsonl'):
 shutil.copy2(file,backup/('mutation-'+file.name))
 for l in file.read_text().splitlines():
  r=json.loads(l);pairs.append((r['instance_id'],r['mutant_id']))
# Locate only the coordinator belonging to this job, leaving its workers to the official cancellation handler.
def descendants(pid):
 p=pathlib.Path('/proc')/str(pid)
 try:kids=(p/'task'/str(pid)/'children').read_text().split()
 except FileNotFoundError:return []
 out=[]
 for k in kids:
  k=int(k);out.append(k);out.extend(descendants(k))
 return out
matches=[]
for pid in descendants(job['pid']):
 args=(pathlib.Path('/proc')/str(pid)/'cmdline').read_bytes()
 if args.split(b'\0')[0].endswith(b'/python') and b'diagnostic_eval.py\x00evaluate' in args:matches.append(pid)
assert len(matches)==1,matches
record={'controller_pid':controller,'job':job['id'],'coordinator_pid':matches[0],'preserved_unique_pairs':len(set(pairs)),'backup':str(backup),'signal_time':time.time(),'new_workers':2}
(backup/'switch.json').write_text(json.dumps(record,indent=2));os.kill(matches[0],signal.SIGTERM)
print(json.dumps(record))
