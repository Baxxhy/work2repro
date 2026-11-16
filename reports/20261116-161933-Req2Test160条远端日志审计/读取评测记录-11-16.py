import json,pathlib,hashlib,sys
payload=json.load(open(sys.argv[1])); tasks={t['instance_id']:t for t in payload['tasks']}
for project in payload['evaluations']:
 root=pathlib.Path(project['destination']);result={'project':project['project'],'root':str(root),'rows':[]}
 try:
  for name in ['exec.jsonl','predictions.norm.jsonl','mutation.baseline.jsonl']:
   path=root/name
   rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
   selected=[]
   for row in rows:
    key=row.get('instance_id',row.get('item_id'))
    if key not in tasks:continue
    if name=='predictions.norm.jsonl':
     files=[{'path':f['file_path'],'sha256':hashlib.sha256(f['code'].encode()).hexdigest()} for f in row.get('produced_files',[])]
     selected.append({'instance_id':key,'files':files,'matches_published':sorted(files,key=lambda f:f['path'])==sorted(tasks[key]['generated_files'],key=lambda f:f['path'])})
    else:
     selected.append({k:row.get(k) for k in ['instance_id','item_id','outcome','exit_codes','execution_seconds','timeout_cleanup','metadata','record_count','written_files']})
   result[name]={'total_rows':len(rows),'selected':selected}
  path=root/'mutation.done.json';result['mutation.done.json']=json.loads(path.read_text())
 except Exception as e:result['error']=type(e).__name__+': '+str(e)
 print(json.dumps(result),flush=True)
