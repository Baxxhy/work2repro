"""Census official outcomes separately from confirmed requirement mechanisms."""
from pathlib import Path
import json,csv,collections,re,hashlib,ast
OUT=Path(__file__).resolve().parent
ROOT=next((p for p in OUT.parents if (p/'results/test-generation-20261114').exists()),None)
if ROOT is None:
    WORK=next(p for p in OUT.parents if (p/'publication/work2repro').exists())
    ROOT=WORK/'publication/work2repro'
BASE=ROOT/'results/test-generation-20261114'
def readcsv(p):return list(csv.DictReader(p.open()))
def writecsv(name,rows):
    if not rows:return
    keys=list(dict.fromkeys(k for row in rows for k in row))
    with (OUT/name).open('w') as f:
        w=csv.DictWriter(f,keys);w.writeheader();w.writerows(rows)
def pct(n,d):return round(n/d*100,2) if d else None
def clean(text):
    text=re.sub(r'/root/[^\s\]"\')]+','[实验目录]',str(text))
    return text
raw=json.loads((OUT/'TSB分类输入快照-11-17.json').read_text())
reqexec=json.loads((OUT/'Req2Test分类输入快照-11-17.json').read_text())
rex={r['item_id']:r for r in reqexec}
rr=[json.loads(l) for l in (BASE/'reports/req2test-per-task.jsonl').read_text().splitlines() if l.strip()]
ss=readcsv(BASE/'reports/tsb-per-task.csv')
art=json.loads((BASE/'task-artifacts.json').read_text())
byid={r['instance_id']:r for r in art}
previous=readcsv(ROOT/'reports/20261116-091532-全案例比例复核/44条通过任务逐项复核-11-16.csv')
reviews={r['instance_id']:r for r in previous}
assert len(reviews)==44 and set(reviews)=={r['instance_id'] for r in rr if r['passed']}
EXCLUDED='sylius/features/admin/promotion/managing_catalog_promotions/creating_catalog_promotion.feature:97'
# Explicit observed blocker. These categories describe evidence, not inferred model cognition.
phase={'parse_or_compile_error':'编译或API类型错误','container_error':'服务注册或依赖注入错误','no_files_returned':'未交付测试','undefined_steps':'步骤定义或绑定缺失','no_scenario_ran':'测试入口缺少Options','passed':'执行通过'}
def req_reason(r):
    errors=[dict(step=s.get('text'),error=s.get('error')) for s in (r.get('per_step') or []) if s.get('error')]
    text='\n'.join(str(x['error']) for x in errors) or str(r.get('index_errors') or '')+'\n'+(r.get('stdout_tail') or '')
    if r['outcome'] in phase:return phase[r['outcome']],text,errors
    checks=[('步骤参数匹配错误',r'func expected more arguments'),('未配置模型替身',r'no LLM configured'),('页面选择器或控件定位错误',r'Invalid expression|Unable to find|Can’t find mapping'),('未定义辅助API或常量',r'undefined method|uninitialized constant|undefined function'),('测试数据或前置对象异常',r'NullPointerException|NoneType|already contains style|Validation failed|illegal null|does not exist|should not start with a slash|Cannot set both fee|Property Language|Expected a value other than null|requested Storage List'),('运行期类型或兼容性错误',r'Type error:|Fatal error:|Deprecated:'),('结果断言与参考结果不一致',r'Assertion|asserting|expected|Expected|does not contain|lacks |received \d+ permission')]
    for name,pattern in checks:
        if re.search(pattern,text,re.I):return name,text,errors
    if errors:return '执行步骤报错，根因待核',text,errors
    return '日志不足，根因待核',text,errors
# Three hypotheses use positive confirmations only. Unconfirmed never means absent.
confirmed=[]
def add(bench,iid,kind,note,source):
    confirmed.append(dict(benchmark=bench,instance_id=iid,project=iid.split('/')[0] if bench=='req2test' else iid.split('__')[0],problem=kind,evidence='需求与代码已确认',finding=note,source=source))
for iid,r in reviews.items():
    if r['classification']=='明确检查缺口':
        mechanism=r['mechanism']
        if mechanism in ['A','A;B;C','A_setup','B']:
            add('req2test',iid,'P2_业务步骤脱节',r['analysis'],'reports/20261116-091532-全案例比例复核/44条通过任务逐项复核-11-16.csv')
        else:
            add('req2test',iid,'P3_约束判定不足',r['analysis'],'reports/20261116-091532-全案例比例复核/44条通过任务逐项复核-11-16.csv')
        if mechanism=='A;B;C':
            add('req2test',iid,'P3_约束判定不足','会话模式来自请求赋值，工具集来自测试构造常量，判定未绑定真实结果','reports/20261117-154735-测试判别能力与替身边界复核/三个痛点的修订判断-11-17.md')
# Audited TSB positives, kept separate from unreviewed tasks.
add('testsuitebench','ajeetdsouza__zoxide.67ca1bc','P1_细粒度条件遗漏','重复score报错条款没有对应输入，repo_1变异存活','reports/business-behavior-gap-20261116/TSB_CROSS_VALIDATION.md')
add('testsuitebench','nukesor__pueue.8b9d6fe','P1_细粒度条件遗漏','缺少队列任务工作流的若干规格义务，已有静态全套件复核；具体状态变异因果待核','reports/business-behavior-gap-20261116/TSB_CROSS_VALIDATION.md')
for iid,note in [('ismaelgv__rnr.fc0733b','完整帮助被简化成前缀检查，删除命令说明仍存活'),('doxygen__doxygen.966d98e','帮助内容检查遗漏规定条目及拼写，局部帮助变异存活'),('nukesor__pueue.8b9d6fe','帮助检查只检查非空等条件，帮助语义变异存活'),('burntsushi__ripgrep.3b7fd44','JSON仅检查type顺序，原测试函数局部核验接受缺data的输出')]:
    add('testsuitebench',iid,'P3_约束判定不足',note,'reports/business-behavior-gap-20261116/TSB_CROSS_VALIDATION.md' if 'ripgrep' not in iid else 'reports/20261117-154735-测试判别能力与替身边界复核/三个痛点的修订判断-11-17.md')
known=collections.defaultdict(list)
for r in confirmed:known[(r['benchmark'],r['instance_id'])].append(r['problem'])
taskrows=[];failtests=[];source_records=[]
def test_reason(t):
    s=str(t.get('extra',{}).get('message','')) or str(t.get('extra',{}).get('text',''))
    for name,pat in [('测试收集失败',r'collection failure|SyntaxError|IndentationError|ERROR collecting'),('缺少fixture',r"fixture .* not found"),('测试依赖或导入异常',r'^(?:ModuleNotFoundError|ImportError):'),('测试自身变量或类型异常',r'^(?:NameError|UnboundLocalError|TypeError|AttributeError|KeyError):'),('命令或交互等待超时',r'^(?:subprocess.TimeoutExpired|pexpect.exceptions.TIMEOUT)|^Timeout exceeded'),('文件或可执行路径不存在',r'^FileNotFoundError:'),('输出解析失败',r'^(?:xml.etree.ElementTree.ParseError|json.decoder.JSONDecodeError):'),('测试数据或索引处理异常',r'^(?:IndexError|ValueError):'),('系统调用或辅助进程异常',r'^(?:OSError|subprocess.CalledProcessError):'),('断言与参考结果不一致',r'AssertionError|assert |assert\(')]:
        if re.search(pat,s,re.I):return name,s
    return '其他执行异常，待核',s
for r in raw:
    iid=r['instance_id'];s=next(x for x in ss if x['instance_id']==iid)
    trials=r['top_keys']['ground_truth_trials'];group=collections.defaultdict(list)
    for trial,q in enumerate(trials):
        for t in q['test_results']:group[t['name']].append((trial,t))
    valid={name for name,values in group.items() if len(values)==3 and all(t['status']=='passed' for _,t in values)}
    assert len(group)==int(s['n_test_functions'])
    assert abs(len(valid)/len(group)-float(s['validity_rate']))<1e-7
    counts=collections.Counter()
    for name,values in group.items():
        bad=[(trial,t) for trial,t in values if t['status'] not in ['passed','skipped']]
        if not bad:continue
        trial,t=bad[0];cause,text=test_reason(t);counts[cause]+=1
        failtests.append(dict(benchmark='testsuitebench',instance_id=iid,test_name=name,failed_trials=';'.join(str(i+1) for i,_ in bad),diagnostic_category=cause,evidence=clean(text)[:1400],inference='直接执行症状；是否属于需求误判需规格复核'))
    symptoms=';'.join(sorted(counts))
    taskrows.append(dict(benchmark='testsuitebench',instance_id=iid,project=iid.split('__')[0],population_included=True,official_outcome='套件部分或全部测试失败',n_test_items=len(group),n_valid_items=len(valid),validity=float(s['validity_rate']),n_scored=int(s['n_mutants']),n_killed=int(s['n_mutants_killed']),mutation=float(s['mutation_score']),execution_categories=symptoms,confirmed_problems=';'.join(known[('testsuitebench',iid)]),semantic_review='已有正例证据' if known[('testsuitebench',iid)] else '尚无三类问题的逐义务结论',semantic_cause='需另查需求及变异，不将参考实现断言失败等同漏检根因'))
    source_records.append(dict(instance_id=iid,official_report_sha256=r['source_sha256'],gold_repeats=3,categories=dict(counts),error_code=r['top_keys'].get('error_code'),error_details=clean(r['top_keys'].get('error_details'))[:2000]))
reqdiagnostics=[]
for s in rr:
    iid=s['instance_id'];r=rex[iid];cause,text,errors=req_reason(r);review=reviews.get(iid)
    trace=BASE/'req2test/tasks'/hashlib.sha256(iid.encode()).hexdigest()[:20]/'trajectory-excerpt.json'
    taskrows.append(dict(benchmark='req2test',instance_id=iid,project=s['project'],population_included=iid!=EXCLUDED,official_outcome=s['outcome'],n_test_items='',n_valid_items='',validity=s['passed'],n_scored=s['n_scored'],n_killed=s['n_killed'],mutation=s['recall'],execution_categories=cause,confirmed_problems=';'.join(known[('req2test',iid)]),semantic_review=review['classification'] if review else '执行未通过，未完成三类语义义务分析',semantic_cause=review['analysis'] if review else '仅确定阻断症状，未执行部分不得认定为需求漏检'))
    reqdiagnostics.append(dict(instance_id=iid,population_included=iid!=EXCLUDED,official_outcome=s['outcome'],engine_outcome=r['outcome'],blocker=cause,failed_steps=json.dumps(errors,ensure_ascii=False),evidence=clean(text)[:2200],source='Req2Test分类输入快照-11-17.json',cause_level='执行症状及明确报错，模型决策根因待轨迹核对'))
    if not s['passed']:
        failtests.append(dict(benchmark='req2test',instance_id=iid,test_name=errors[0]['step'] if errors else '',failed_trials='1',diagnostic_category=cause,evidence=clean(text)[:1400],inference='执行阻断；排除项保持官方人口规则'))
assert len(taskrows)==325 and len({(r['benchmark'],r['instance_id']) for r in taskrows})==325
writecsv('全部325条逐任务分类-11-17.csv',taskrows)
writecsv('全部执行失败证据-11-17.csv',failtests)
writecsv('Req2Test160条阻断原因-11-17.csv',reqdiagnostics)
writecsv('三类问题已确认清单-11-17.csv',confirmed)
counts=[]
for bench,den in [('testsuitebench',165),('req2test',159)]:
    br=[r for r in taskrows if r['benchmark']==bench and r['population_included']]
    passed=44 if bench=='req2test' else None
    for k in ['P1_细粒度条件遗漏','P2_业务步骤脱节','P3_约束判定不足']:
        sub=[r for r in confirmed if r['benchmark']==bench and r['problem']==k]
        counts.append(dict(benchmark=bench,problem=k,confirmed_tasks=len({r['instance_id'] for r in sub}),denominator=den,confirmed_lower_bound_pct=pct(len(sub),den),passed_denominator=passed,confirmed_among_passed_pct=pct(len(sub),passed) if passed else '',projects=len({r['project'] for r in sub}),interpretation='已确认下界，不是总体发生率；其余任务存在未完成语义复核'))
writecsv('三类问题数量与分母-11-17.csv',counts)
projectstats=[]
for (bench,project) in sorted({(r['benchmark'],r['project']) for r in taskrows}):
    sub=[r for r in taskrows if r['benchmark']==bench and r['project']==project];inc=[r for r in sub if r['population_included']]
    cs=[r for r in confirmed if r['benchmark']==bench and r['project']==project]
    projectstats.append(dict(benchmark=bench,project=project,total=len(sub),scored_population=len(inc),passed=sum(r['official_outcome']=='pass' for r in inc),P1=sum(r['problem'].startswith('P1') for r in cs),P2=sum(r['problem'].startswith('P2') for r in cs),P3=sum(r['problem'].startswith('P3') for r in cs),confirmed_union=len({r['instance_id'] for r in cs}),execution_categories=json.dumps(dict(collections.Counter(r['execution_categories'] for r in inc)),ensure_ascii=False)))
writecsv('各项目分类统计-11-17.csv',projectstats)
reqsc=[r for r in reqdiagnostics if r['population_included']]
summary=dict(tasks=325,req_population=159,req_passed=44,req_execution_failed=115,req_blockers=dict(collections.Counter(r['blocker'] for r in reqsc if r['official_outcome']!='pass')),req_passed_semantic_review=dict(collections.Counter(r['classification'] for r in reviews.values())),tsb_tasks=165,tsb_raw_unique_test_items=sum(int(r['n_test_functions']) for r in ss),tsb_valid_items=sum(r['n_valid_items'] for r in taskrows if r['benchmark']=='testsuitebench'),tsb_failure_categories=dict(collections.Counter(r['diagnostic_category'] for r in failtests if r['benchmark']=='testsuitebench')),tsb_tasks_with_category={c:len({r['instance_id'] for r in failtests if r['benchmark']=='testsuitebench' and r['diagnostic_category']==c}) for c in {r['diagnostic_category'] for r in failtests if r['benchmark']=='testsuitebench'}},confirmed=counts,semantic_unreviewed={'req_nonpassing':115,'tsb_no_complete_obligation_audit':165},official_scores_unchanged=True)
(OUT/'统计汇总-11-17.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
(OUT/'TSB来源校验与分类-11-17.json').write_text(json.dumps(source_records,ensure_ascii=False,indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
