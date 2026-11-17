import pathlib,json,subprocess,signal,os,shutil,time
root=pathlib.Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
backup=root/'concurrency-change-20261117-105721';assert not backup.exists();backup.mkdir()
controller=int(subprocess.check_output(['systemctl','show',root.name,'-p','MainPID','--value'],text=True));assert controller>0
os.kill(controller,signal.SIGSTOP)
try:
 s=json.loads((root/'state.json').read_text());j,=[x for x in s['jobs'].values() if x['state']=='running'];assert j['key']=='coddy-agent' and j['workers']==3
 def children(pid):
  out=[]
  for k in (pathlib.Path('/proc')/str(pid)/'task'/str(pid)/'children').read_text().split():
   k=int(k);out.append(k);out+=children(k)
  return out
 matches=[]
 for pid in children(j['pid']):
  args=(pathlib.Path('/proc')/str(pid)/'cmdline').read_bytes()
  if args.split(b'\0')[0].endswith(b'/python') and b'diagnostic_eval.py\x00evaluate' in args:matches.append(pid)
 assert matches
 assert all(pid in children(matches[0]) for pid in matches[1:])
 matches=matches[:1]
 for f in ['state.json','progress.json','frozen/config.json','control/controller.py']:shutil.copy2(root/f,backup/pathlib.Path(f).name)
 folder=pathlib.Path('/root/lby-docker/req2test/user/benchmark/runs')/j['official_run_id']/'coddy-agent/th/mutation';pairs=set()
 for f in folder.glob('*.jsonl'):
  shutil.copy2(f,backup/('mutation-'+f.name))
  for line in f.read_text().splitlines():
   r=json.loads(line);pairs.add((r['instance_id'],r['mutant_id']))
 r={'controller_pid':controller,'coordinator_pid':matches[0],'job':j['id'],'before_workers':3,'after_workers':20,'preserved_unique_pairs':len(pairs),'time':time.time()};(backup/'switch.json').write_text(json.dumps(r,indent=2));os.kill(matches[0],signal.SIGTERM);print(json.dumps(r))
except BaseException:
 os.kill(controller,signal.SIGCONT);raise
