import csv,json,hashlib
from pathlib import Path
from collections import Counter,defaultdict
from datetime import datetime
from zoneinfo import ZoneInfo
r=Path(__file__).resolve().parents[2]
d=Path(__file__).resolve().parent
old=list(csv.DictReader((r/'reports/pass-nonkill-20261116/FAILURE_MECHANISM_DATABASE.csv').open()))
annotations=json.loads((r/'reports/business-behavior-gap-20261116/annotations.json').read_text())
metrics=[json.loads(x) for x in (r/'results/test-generation-20261114/reports/req2test-per-task.jsonl').read_text().splitlines()]
tasks={x['instance_id']:x for x in map(json.loads,(r/'data/test-generation-20261114/req2test-tasks.jsonl').read_text().splitlines())}
artifacts={x['instance_id']:x for x in json.loads((r/'results/test-generation-20261114/task-artifacts.json').read_text()) if x['benchmark']=='req2test'}
oldmap={x['instance_id']:x for x in old}
notes={
'algorand-sdk/features/unit/abijson.feature:74':('未发现明确缺口','','真实Interface序列化，完整JsonNode相等比较并反序列化回原对象。'),
'e-petitions/features/admin/admin_access.feature:12':('明确检查缺口','结果检查不完整','要求markup有效，但仅检查html和body元素存在。HTML解析器可修复无效标记，这两个元素存在不能检查标记有效性。登录跳转和HTTPS检查均存在。'),
'python-docx/features/blk-iter-inner-content.feature:7':('明确检查缺口','对象顺序检查不完整','要求所有段落和表格按文档顺序返回。测试比较六个类型和三个段落文本，没有比较三张表格的内容或身份。同为Table的对象调换仍满足这些断言。'),
'algorand-sdk/features/unit/atomic_transaction_composer.feature:175':('明确检查缺口','异常约束未检查','需求指定zero group size error。生成捕获任意Exception只检查非空，expectedError仅用于没有抛异常时的报错文字。参考将IllegalArgumentException映射为指定错误，IOException检查其消息。生成可接受其他错误。'),
'coddy-agent/features/config_tools.feature:58':('背景步骤未落实','前置能力未设置','背景要求会话可热重载，hotReload为空。参考sessionCanReload设置env.ReloadConfig。当前场景实际检查暂存命令列表，这一背景缺失对该检查的影响未验证。'),
'sylius/features/admin/promotion/managing_coupons/generating_coupon.feature:26':('未发现明确缺口','','真实管理员API生成优惠券，检查成功并重新查询该promotion的优惠券数量。'),
'prestashop/tests/Integration/Behaviour/Features/Scenario/Meta/meta_management.feature:10':('未发现明确缺口','','检查默认语言，执行AddMetaCommand，重新加载Meta并逐项检查page、title、description、url_rewrite。'),
'python-docx/features/sty-latent-props.feature:21':('未发现明确缺口','','真实latent_styles属性设置，再读取属性按示例精确比较。'),
'python-docx/features/doc-access-collections.feature:17':('未发现明确缺口','','从文档fixture读取sections并检查Sections类型，与唯一Then匹配。'),
'python-docx/features/doc-access-collections.feature:22':('未发现明确缺口','','建立真实Document并检查styles为Styles类型，与唯一Then匹配。'),
'python-docx/features/doc-settings.feature:8':('未发现明确缺口','','按有无settings部件分支准备文档，读取settings并检查Settings类型。'),
'algorand-sdk/features/unit/tealsign.feature:15':('未发现明确缺口','','真实解码输入、构造账户、tealSignFromProgram，检查签名字节的Base64等于给定值。'),
'algorand-sdk/features/unit/offline.feature:10':('未发现明确缺口','','真实助记词构造Account并toMnemonic，精确检查往返字符串。'),
'python-docx/features/sty-latent-props.feature:7':('未发现明确缺口','','从默认模板读取latent_styles，按每个属性和示例值精确比较。'),
}
for k in ['algorand-sdk/features/unit/v2indexerclient_paths.feature:150','algorand-sdk/features/unit/v2indexerclient_paths.feature:195','algorand-sdk/features/unit/v2indexerclient_paths.feature:62','algorand-sdk/features/unit/v2indexerclient_paths.feature:304','algorand-sdk/features/unit/v2algodclient_paths.feature:16']:
 notes[k]=('背景步骤未落实','请求观察被URL构造替代','Background明确写mock server recording request paths。生成Given只创建client，随后检查getRequestUrl，未建立记录请求的服务器。URL构造已真实执行，是否必须发送HTTP才能满足该任务仍需结合官方getRequestUrl接口定义区分，单列背景差异。')
notes['e-petitions/features/charlie_creates_a_petition.feature:56']=('明确检查缺口','结果检查不完整','实际提交XSS输入并检查不存在onmouseover属性，覆盖指定攻击载荷；markup有效性步骤只检查解析后的html元素和单个事件属性，没有检查解析错误。安全载荷检查有效，通用标记有效性检查较窄。')
rows=[]
for m in metrics:
 if not m['passed']:continue
 k=m['instance_id'];a=artifacts[k];q=r/'results/test-generation-20261114/req2test/tasks'/a['artifact_id']/'generated';files=[str(p.relative_to(r)) for p in sorted(q.rglob('*')) if p.is_file()]
 if k in oldmap:
  o=oldmap[k];z=annotations['old'].get(o['artifact_id'])
  if o['requirement_gap_confirmed']=='True':status='明确检查缺口';mechanism=z['class'];note=z['note']
  elif o['cause_group']=='reference_scope_difference':status='参考准备或检查范围不同';mechanism='';note=o['analysis']
  else:status='仍需核实';mechanism='';note=o['analysis']
 else:status,mechanism,note=notes[k]
 task=tasks[k]['task'];req=(task['requirement'].get('background') or '')+'\n'+task['criterion']['gherkin']
 rows.append(dict(instance_id=k,project=k.split('/')[0],group='KillComplete' if m['kill_complete'] else 'Pass-but-Non-Kill',classification=status,mechanism=mechanism,analysis=note,n_scored=m['n_scored'],n_killed=m['n_killed'],requirement=req,generated_files=';'.join(files),execution_evidence='results/test-generation-20261114/reports/req2test-per-task.jsonl',review_date='2026-11-16'))
assert len(rows)==44 and len({x['instance_id'] for x in rows})==44

def writecsv(name,items):
 with (d/name).open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(items[0]));w.writeheader();w.writerows(items)
writecsv('44条通过任务逐项复核-11-16.csv',rows)
project=[]
for p in sorted({x['project'] for x in rows}):
 s=[x for x in rows if x['project']==p];gap=sum(x['classification']=='明确检查缺口' for x in s);bg=sum(x['classification']=='背景步骤未落实' for x in s)
 project.append(dict(project=p,passed_tasks=len(s),confirmed_check_gaps=gap,gap_percent=round(100*gap/len(s),2),background_only=bg,nonkill=sum(x['group']=='Pass-but-Non-Kill' for x in s),killcomplete=sum(x['group']=='KillComplete' for x in s)))
writecsv('各项目问题比例-11-16.csv',project)
# Baseline population ledger preserves every ID, with failed executions separated.
review={x['instance_id']:x for x in rows}
ledger=[]
for m in metrics:
 x=review.get(m['instance_id']);ledger.append(dict(instance_id=m['instance_id'],project=m['project'],outcome=m['outcome'],exclusion=m.get('exclusion'),semantic_review='完成' if x else '执行未通过，未作通过后行为质量判定',classification=x['classification'] if x else '',n_scored=m.get('n_scored'),n_killed=m.get('n_killed')))
writecsv('160条任务状态总表-11-16.csv',ledger)
# Audit all 142 Sylius mutants using existing records only.
e=r/'reports/pass-nonkill-20261116/evidence/7627df83491b90a0f0fa'
cand=json.loads((e/'execution.json').read_text());gold=json.loads((r/'reports/business-behavior-gap-20261116/gold-execution/7627df83491b90a0f0fa.json').read_text())['record']
mutants=json.loads((e/'surviving-mutants.json').read_text());outcomes={x['mutant_id']:x['outcome'] for x in json.loads((e/'mutation-results.json').read_text())};kills={x['mutant_id']:x['gold_outcome'] for x in json.loads((e/'reference-kills.json').read_text())}
mutantrows=[]
for x in mutants:
 hit=x['start_line'] in cand['coverage_lines'].get(x['file'],[]);g=x['start_line'] in gold['coverage_lines'].get(x['file'],[])
 assert outcomes[x['id']]=='passed' and kills[x['id']]=='killed'
 mutantrows.append(dict(mutant_id=x['id'],file=x['file'],line=x['start_line'],original=x['original'],mutated=x['mutated'],candidate_mutant_outcome=outcomes[x['id']],reference_mutant_outcome=kills[x['id']],candidate_baseline_line_covered=hit,reference_baseline_line_covered=g,location_group='管理员订单查询扩展' if '/QueryExtension/Admin/Order/' in x['file'] else '其他位置',reference_file_call_steps=';'.join(map(str,sorted({z['step'] for z in gold['direct_calls'] if z.get('callee_file')==x['file'] and z['step'] is not None})))))
assert len(mutantrows)==142 and len({x['mutant_id'] for x in mutantrows})==142
writecsv('Sylius142个存活变异逐项统计-11-16.csv',mutantrows)
summary={'time':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'fixed_population':160,'scored_population':159,'passed_population':44,'reviewed_passed_population':len(rows),'class_counts':dict(Counter(x['classification'] for x in rows)),'nonkill_counts':dict(Counter(x['classification'] for x in rows if x['group']=='Pass-but-Non-Kill')),'control_counts':dict(Counter(x['classification'] for x in rows if x['group']=='KillComplete')),'sylius_uncovered':sum(not x['candidate_baseline_line_covered'] for x in mutantrows),'sylius_covered':sum(x['candidate_baseline_line_covered'] for x in mutantrows),'sylius_admin_order_locations':sum(x['location_group']=='管理员订单查询扩展' for x in mutantrows),'new_model_calls':0,'new_evaluations':0}
(d/'统计汇总-11-16.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False,indent=2));print(project)
