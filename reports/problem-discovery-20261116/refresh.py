"""Fetch a read-only snapshot and refresh all incremental tables. No LLM calls."""
import hashlib,json,pathlib,subprocess,sys
root=pathlib.Path(__file__).resolve().parent
result=subprocess.run(['ssh','-o','ClearAllForwardings=yes','-o','BatchMode=yes','-o','ConnectTimeout=15','4x3090','/root/lby-docker/req2test/user/venv/bin/python -'],input=(root/'collect_remote.py').read_text(),text=True,capture_output=True,timeout=180)
if result.returncode:
 sys.stderr.write(result.stderr);raise SystemExit(result.returncode)
data=json.loads(result.stdout);raw=json.dumps(data,sort_keys=True).encode();name=hashlib.sha256(raw).hexdigest()[:16]+'.json'
folder=root/'snapshots';folder.mkdir(exist_ok=True)
if not (folder/name).exists():(folder/name).write_bytes(raw)
(root/'latest-snapshot.txt').write_text(name+'\n')
subprocess.run([sys.executable,str(root/'incremental_analysis.py')],check=True)
