from pathlib import Path
import json,os,signal,subprocess,shutil,time,re
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
backup=root/'concurrency32-20261117-late'; backup.mkdir(exist_ok=False)
controller=int(subprocess.check_output(['systemctl','show',root.name,'-p','MainPID','--value'],text=True)); assert controller>0
os.kill(controller,signal.SIGSTOP)
try:
 s=json.loads((root/'state.json').read_text()); jobs=[j for j in s['jobs'].values() if j['state']=='running']; assert len(jobs)==1
 j=jobs[0]; assert j['key']=='coddy-agent' and j['workers']==28
 def children(pid):
  out=[]
  try: ids=(Path('/proc')/str(pid)/'task'/str(pid)/'children').read_text().split()
  except FileNotFoundError:return out
  for k in ids: out.append(int(k)); out+=children(int(k))
  return out
 matches=[]
 for pid in children(j['pid']):
  try: args=(Path('/proc')/str(pid)/'cmdline').read_bytes()
  except FileNotFoundError:continue
  if args.split(b'\0')[0].endswith(b'/python') and b'diagnostic_eval.py\x00evaluate' in args: matches.append(pid)
 assert matches and all(pid in children(matches[0]) for pid in matches[1:])
 for f in ['state.json','progress.json','frozen/config.json','control/controller.py']:shutil.copy2(root/f,backup/Path(f).name)
 source=Path('/root/lby-docker/req2test/user/benchmark/runs')/j['official_run_id']/'coddy-agent/th/mutation'
 (backup/'mutation').mkdir()
 pairs={}
 for f in source.glob('*.jsonl'):
  shutil.copy2(f,backup/'mutation'/f.name)
  for line in f.read_text().splitlines():
   r=json.loads(line); key=(r['instance_id'],r['mutant_id']); pairs[key]=r
 log=(Path(j['path'])/'job.log').read_text(); nonce=re.search(r'environment (e[0-9a-f]+)',log).group(1)
 record=dict(time=time.time(),controller_pid=controller,coordinator_pid=matches[0],job=j['id'],nonce=nonce,before_workers=28,after_workers=32,preserved_pairs=len(pairs))
 (backup/'switch.json').write_text(json.dumps(record,indent=2));os.kill(matches[0],signal.SIGTERM);print(json.dumps(record),flush=True)
except BaseException:
 os.kill(controller,signal.SIGCONT);raise
