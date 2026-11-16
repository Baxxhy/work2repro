import json,pathlib,collections,sys,hashlib
payload=json.load(open('/tmp/r2t-log-audit-161933/input.json'))
for group in payload['evaluations']:
 p=pathlib.Path(group['destination']);pairs=collections.defaultdict(list)
 for f in sorted((p/'mutation').glob('*.jsonl')):
  for line in f.open():
   r=json.loads(line);pairs[(r['instance_id'],r['mutant_id'])].append(r['outcome'])
 done=json.load(open(p/'mutation.done.json'))
 print(json.dumps({'project':group['project'],'unique_pairs':len(pairs),'records':sum(map(len,pairs.values())),'conflicting_pairs':[list(k) for k,v in pairs.items() if len(set(v))>1],'outcomes':dict(collections.Counter(v[-1] for v in pairs.values())),'done_pairs':done['pairs'],'exec_sha256_matches_done':hashlib.sha256((p/'exec.jsonl').read_bytes()).hexdigest()==done['exec_sha256']}),flush=True)
