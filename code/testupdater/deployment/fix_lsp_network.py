from pathlib import Path
import json,subprocess
r=Path('/root/Baxxhy/work2/reproductions/testupdater');p=r/'runtime/utils/multilspy/language_servers/eclipse_jdtls'
f=p/'initialize_params.json';d=json.loads(f.read_text());d['initializationOptions']['settings']['java']['configuration']['maven']['userSettings']='/root/Baxxhy/work2/reproductions/mumutestup/deployment/maven-settings-luna.xml';f.write_text(json.dumps(d,indent=2))
f=p/'eclipse_jdtls.py';s=f.read_text();s=s.replace('                "-Dfile.encoding=utf8",','                "-Dfile.encoding=utf8",\n                "-Dhttp.proxyHost=127.0.0.1",\n                "-Dhttp.proxyPort=7890",\n                "-Dhttps.proxyHost=127.0.0.1",\n                "-Dhttps.proxyPort=7890",\n                "-Dhttp.nonProxyHosts=localhost|127.0.0.1",');f.write_text(s)
# Stop only this task's warmup and its own child JVM; no global Java kill.
import psutil
for proc in psutil.process_iter(['pid','cmdline']):
 if any(arg == str(r/'deployment/warm_lsp.py') for arg in proc.info['cmdline'] or []):
  children=proc.children(recursive=True)
  for child in children:child.terminate()
  proc.terminate()
repo=r/'repos/shred/acme4j';sample=json.loads((r/'datasets/updates4j/verified_shred_acme4j.json').read_text())[0]
subprocess.run(['git','-C',str(repo),'checkout','--detach',sample['commit_tgt']],check=True)
print('LSP network configured and smoke repo set to dataset commit')
