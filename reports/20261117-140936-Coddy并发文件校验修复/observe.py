import json,time
from pathlib import Path
root=Path('/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1')
job=root/'jobs/466f2571c2594946baed7802d4be04a6'
mutation=Path('/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1-coddy-agent/coddy-agent/th/mutation')
checkpoint=job/'resource-start-checkpoint'
baseline={f.name:len(f.read_text().splitlines()) for f in checkpoint.glob('*.jsonl')}
out=Path('/tmp/r2t-fixed-observation.jsonl')
for _ in range(60):
 log=(job/'job.log').read_text()
 counts={f.name:len(f.read_text().splitlines()) for f in mutation.glob('*.jsonl')}
 growing={k:v-baseline.get(k,0) for k,v in counts.items() if v>baseline.get(k,0)}
 progress=json.loads((root/'progress.json').read_text())
 row=dict(time=time.time(),qualified='is up and qualified (20 workers)' in log,mutation_started='8559 to run' in log,growing_shards=growing,total_rows=sum(counts.values()),resources=progress.get('resources'),exited=(job/'exit.json').exists(),tail=log[-800:])
 with out.open('a') as f:f.write(json.dumps(row)+'\n')
 print(json.dumps({k:v for k,v in row.items() if k!='tail'}),flush=True)
 if row['exited'] or len(growing)==20 and min(growing.values())>=3:break
 time.sleep(30)
