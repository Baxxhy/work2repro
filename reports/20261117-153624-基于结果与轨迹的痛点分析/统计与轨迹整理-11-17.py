from pathlib import Path
import collections,json,hashlib,re
ROOT=Path(__file__).resolve().parents[2]
PUB=ROOT/'publication/work2repro'
OUT=Path(__file__).resolve().parent
base=PUB/'results/test-generation-20261114'
report={}
for bench in ['testsuitebench','req2test']:
 fs=list((base/bench/'tasks').glob('*/trajectory-excerpt.json'))
 report[bench]={'published_trace_files':len(fs),'complete_trace_flags':dict(collections.Counter(str(json.loads(f.read_text()).get('complete_trace')) for f in fs))}
f=base/'reports/req2test-per-task.jsonl'
rows=[json.loads(l) for l in f.read_text().splitlines() if l.strip()]
report['fixed_req_subset']={'rows':len(rows),'unique_ids':len({r['instance_id'] for r in rows}),'passed':sum(bool(r['passed']) for r in rows),'kill_complete':sum(bool(r['kill_complete']) for r in rows),'outcomes':dict(collections.Counter(r['outcome'] for r in rows)),'exclusions':dict(collections.Counter(str(r.get('exclusion')) for r in rows))}
raw=json.loads(Path('/tmp/problem-full-trace-extract.json').read_text())
# Publish compact event evidence, avoiding full context/output and host paths.
clean={}
for k,d in raw.items():
 events=[]
 for e in d.get('events',[]):
  x={a:e[a] for a in ['event_index','type','exit_code'] if a in e}
  text=e.get('text',e.get('command',''))
  text=re.sub(r'/root/[^\s)\]"\']+', '[实验工作目录]',text)
  x['text']=text
  events.append(x)
 clean[k]={'source_sha256':d.get('source_sha256'),'raw_event_count':d.get('raw_event_count'),'events':events}
(OUT/'结果与轨迹盘点-11-17.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
(OUT/'五个案例轨迹证据-11-17.json').write_text(json.dumps(clean,ensure_ascii=False,indent=2))
print(json.dumps(report,ensure_ascii=False,indent=2))
