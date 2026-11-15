import hashlib,json,re
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parent
snapshot=json.loads((ROOT/'completed-snapshot.json').read_text())
previous=json.loads((ROOT.parent/'pass-nonkill-20261116/manifest.json').read_text())
old={x['instance_id'] for x in previous['nonkill']+previous['controls']}
old.update(x['instance_id'] for x in json.loads((ROOT.parent/'problem-discovery-20261116/semantic_selection.json').read_text())['cases'])
rows=[x for x in snapshot['rows'] if x['passed'] and x['mutation_status']=='scored' and x['instance_id'] not in old and x['instance_id'] not in snapshot['exclusions']]
rank=lambda x:hashlib.sha256(x['instance_id'].encode()).hexdigest()
projects=sorted({x['project'] for x in rows if not x['kill_complete']})
nonkill=[]
for project in projects:
 candidates=sorted([x for x in rows if x['project']==project and not x['kill_complete']],key=rank)
 assert len(candidates)>=5,(project,len(candidates))
 nonkill.extend(candidates[:5])
assert len(nonkill)==20
controls=[];pairs=[]
def tokens(iid):
 return set(re.findall(r'[a-z]+',snapshot['requirements'][iid]['title'].lower()))
for round_index in range(4):
 for project in projects:
  if len(controls)==15:break
  target=[x for x in nonkill if x['project']==project][round_index]
  candidates=[x for x in rows if x['project']==project and x['kill_complete'] and x not in controls]
  if not candidates:continue
  def match(x):
   a=tokens(target['instance_id']);b=tokens(x['instance_id'])
   same_feature=x['instance_id'].rsplit(':',1)[0]==target['instance_id'].rsplit(':',1)[0]
   same_kind=snapshot['requirements'][x['instance_id']]['requirement_type']==snapshot['requirements'][target['instance_id']]['requirement_type']
   return (-int(same_feature),-int(same_kind),-len(a&b)/max(1,len(a|b)),rank(x))
  chosen=min(candidates,key=match);controls.append(chosen)
  score=match(chosen)
  pairs.append(dict(target=target['instance_id'],control=chosen['instance_id'],same_feature=bool(-score[0]),same_kind=bool(-score[1]),title_jaccard=-score[2]))
assert len(controls)==15
for case in nonkill+controls:
 key=rank(case)[:20]
 case['artifact']=dict(artifact_id=key,original_record=case['_prediction'])
manifest=dict(nonkill=nonkill,controls=controls,matching=pairs,source_snapshot_sha256=hashlib.sha256((ROOT/'completed-snapshot.json').read_bytes()).hexdigest(),
 rule='Exclude previous 24+10 and prior 60 selection; select five SHA256-ranked nonkill per eligible completed project; controls round-robin same project, prefer same feature, same scenario kind, title token Jaccard; SHA256 breaks ties',
 available_completed=len(snapshot['rows']),full_population=2051,excluded_prior_ids=sorted(old))
p=ROOT/'manifest.json'
if p.exists():assert json.loads(p.read_text())==manifest
else:p.write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
print('selection',Counter(x['project'] for x in nonkill),Counter(x['project'] for x in controls))
for x in nonkill:print(x['instance_id'],x['n_killed'],x['n_scored'])
