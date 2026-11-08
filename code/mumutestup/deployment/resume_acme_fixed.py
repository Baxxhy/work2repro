from pathlib import Path
import json,time,subprocess,os
root=Path("/root/Baxxhy/work2/reproductions/mumutestup")
current=root/"runs/updates4j-fixed-v3-20261107"
output=root/"runs/updates4j-acme-fixed-20261107"
output.mkdir(exist_ok=True)
while True:
 state=json.loads((current/"status.json").read_text())
 if state["state"]!="running":break
 time.sleep(30)
script=(root/"deployment/start_updates4j_fixed_v3.sh").read_text().replace("updates4j-fixed-v3-20261107",output.name).replace("--workers 7", "--workers 1 --project shred/acme4j")
launcher=output/"start.sh";launcher.write_text(script)
env=os.environ.copy();env["PYTHONPATH"]=str(root/"deployment/updates4j_environment")
p=subprocess.Popen(["bash",str(launcher)],env=env,stdout=(output/"console.log").open("a"),stderr=subprocess.STDOUT,start_new_session=True)
(output/"launcher.json").write_text(json.dumps({"pid":p.pid,"source":"updates4j-fixed-v3-20261107","scope":"shred/acme4j 18 samples"}))
print(p.pid,flush=True)
