import json,csv,sys
from pathlib import Path
from req2test import report as R
from req2test.inference import run_agent as G
out=Path(sys.argv[1]);out.mkdir(exist_ok=True)
runs=Path('/root/lby-docker/req2test/user/benchmark/runs')
old=runs/'req2test-eval2051-resume-20261117-v1'
def read(p):return json.loads(p.read_text())
def rows(p):return [json.loads(l) for l in p.read_text().splitlines()]
ids={r['id'] for r in read(Path('/tmp/限流中断任务-11-18.json'))+read(Path('/tmp/历史启动异常任务-11-18.json')) if r.get('kind')!='unresolved'}
assert len(ids)==50
orig=[r for f in old.glob('*/th/instances.jsonl') for r in rows(f)]
assert len(orig)==len({r['instance_id'] for r in orig})==2051
def collect(pattern):
 a=[r for f in runs.glob(pattern+'/th/instances.jsonl') for r in rows(f) if r['instance_id'] in ids];assert len(a)==len({r['instance_id'] for r in a});return {r['instance_id']:r for r in a}
new=collect('req2test-diagnose308-20261118-v1-regenerated-*/*');full=collect('final11-medium-profile-20261119-*/*')
assert set(new)==ids and set(full)=={i for i,r in new.items() if r['passed']} and len(full)==11
for project in {r['project'] for r in new.values()}:
 kit=R._default_kit(project)
 path=runs/('req2test-diagnose308-20261118-v1-regenerated-'+project)/project/'th/exec.jsonl'
 failed=[r for r in rows(path) if R.S.instance_id_of(r) in ids-set(full)]
 for scored in R.S.score_instances(kit,failed,[]):
  assert not scored['passed']
  row=new[scored['instance_id']]
  row.update({k:v for k,v in scored.items() if k in row})
new.update(full); final=[new.get(r['instance_id'],r) for r in orig]
s=read(old/'summary.json');ex=s['population']['excluded'];kits={r['project']:None for r in orig};iset=R._i_sets_for({k:R._default_kit(k) for k in kits})
for mode in s['modes']:
 assert R.A.aggregate(orig,mode,i_sets=iset,excluded=ex)['mean']==s['modes'][mode]['mean']
 s['modes'][mode]=R.A.aggregate(final,mode,i_sets=iset,excluded=ex)
s.pop('ci',None);s['run_id']=out.name;s['disclosures']=R.disclosures(R.A.without_excluded(final,ex));R.write(out,s)
(out/'逐任务指标-11-20.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in final))
print(s['modes']['leaderboard']['mean']['th'])
for x in list(csv.reader(open('/tmp/empty-audit-rows.csv')))[1:]:
 if x[2]!='True' or x[4]=='0':continue
 for line in Path(x[6]).read_text().splitlines():
  try:e=json.loads(line)
  except ValueError:continue
  i=e.get('item',{})
  if e.get('type')=='item.completed' and i.get('type')=='file_change':
   project=x[0].split('/')[0];rel=i['changes'][0]['path'].split('/0000/repo/')[-1]
   root=Path(x[6]).parents[2]; manifests=list((root.parent.parent/'manifests/items').glob(root.name+'.jsonl'))
   print(project,rel,'removable',G.removable(project)(rel),'manifest',manifests)
   if manifests:print('accepted',G.answers(rows(manifests[0])[0]['placement'],rel,G.removable(project)))
