import hashlib
import json
import os
from pathlib import Path
import pwd
import sys

payload = json.load(open(sys.argv[1]))
run_id = 'req2test-subset160-infra-recovery-20261116-v1'
home = Path('/root/lby-docker/req2test/user')
work = home / 'runs' / run_id
root = home / 'benchmark/runs' / run_id
assert not root.exists(), 'Recovery directory already exists; inspect before resuming'
assert not work.exists(), 'Recovery inputs already exist; inspect before resuming'
work.mkdir(); root.mkdir()
uid = pwd.getpwnam('r2tbench').pw_uid
predictions = []
for task in payload['tasks']:
    rows = [json.loads(line) for line in Path(task['original_record']).read_text().splitlines() if line.strip()]
    row, = [row for row in rows if row['instance_id'] == task['instance_id']]
    actual = {f['path']: hashlib.sha256(f['content'].encode()).hexdigest() for f in row['files']}
    assert actual == {f['path']: f['sha256'] for f in task['generated_files']}
    predictions.append(row)
(work / 'predictions.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in predictions))
(work / 'instances.txt').write_text(''.join(row['instance_id']+'\n' for row in predictions))
retry_id = 'coddy-agent/features/subagents_http.feature:32'
retry_mutants = {'067d32a367e1f45f','4e6505b87460587e','a9b81946ed00195a','275ee7bf98602829','53e3121a97c34639'}
provenance = []
for group in payload['evaluations']:
    source = Path(group['destination'])
    destination = root / group['project'] / 'th'
    (destination / 'exec/raw').mkdir(parents=True)
    (destination / 'mutation').mkdir()
    content = (source/'exec.jsonl').read_text()
    (destination/'exec/raw/w_reused.jsonl').write_text(content)
    (destination/'mutation.baseline.jsonl').write_text((source/'mutation.baseline.jsonl').read_text())
    reused = 0
    omitted = []
    for number, path in enumerate(sorted((source/'mutation').glob('*.jsonl'))):
        keep = []
        for line in path.read_text().splitlines():
            row = json.loads(line)
            if row['instance_id'] == retry_id and row['mutant_id'] in retry_mutants:
                assert row['outcome'] == 'passed_but_nonzero_exit'
                omitted.append(row)
            else:
                keep.append(row)
        (destination/'mutation'/f'reused-{number}.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in keep))
        reused += len(keep)
    provenance.append({'project':group['project'],'source':str(source),'exec_sha256':hashlib.sha256(content.encode()).hexdigest(),'reused_mutant_pairs':reused,'rerun_pairs':omitted})
assert sum(len(x['rerun_pairs']) for x in provenance)==5
assert sum(x['reused_mutant_pairs'] for x in provenance)==4751
(work/'recovery-provenance.json').write_text(json.dumps(provenance,indent=2))
for base in [work,root]:
    os.chown(base,uid,uid)
    for path in base.rglob('*'): os.chown(path,uid,uid)
print(json.dumps({'run_id':run_id,'work':str(work),'official_output':str(root),'reuse_exec':160,'reuse_mutant_pairs':4751,'rerun_mutant_pairs':5}))
