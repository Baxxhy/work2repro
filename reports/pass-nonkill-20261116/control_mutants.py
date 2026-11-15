from pathlib import Path
import json,subprocess
r=Path(__file__).resolve().parent
m=json.loads((r/'manifest.json').read_text())
for project in sorted({x['project'] for x in m['controls']}):
 kit=next((Path('/root/lby-docker/req2test/user/benchmark/kits')/project).iterdir())
 manifest=json.loads(subprocess.check_output(['zstd','-dc',str(kit/'mutation/manifest.json.zst')]))
 lookup={x['id']:x for x in manifest['mutants']}
 for x in m['controls']:
  if x['project']!=project:continue
  d=r/'evidence'/x['artifact']['artifact_id']
  ids={v['mutant_id'] for v in json.loads((d/'mutation-results.json').read_text())}
  assert ids<=lookup.keys()
  (d/'control-mutants.json').write_text(json.dumps([lookup[mid] for mid in sorted(ids)],indent=2))
  print(x['instance_id'],len(ids))
