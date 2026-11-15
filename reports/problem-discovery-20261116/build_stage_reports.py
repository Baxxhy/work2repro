"""Render a conservative interim report from metrics and reviewed cases."""
import pathlib,json,csv,collections,hashlib
root=pathlib.Path(__file__).resolve().parent
prior=root.parent/'failure-mechanisms-20261115/cases'
metrics=list(csv.DictReader((root/'incremental_metrics.csv').open()))
selection=json.loads((root/'semantic_selection.json').read_text())['cases']
progress=json.loads((root/'incremental_progress.json').read_text())
reviewed={}
findings={
 '33':('已证实','替代业务对象上的断言','需求要求从真实购物车创建订单。生成代码用本地 items 数组和匿名类构造订单，优惠券、地址及多项准备步骤为空函数，最后仅对匿名对象 getItems() 的数量断言。唯一生成文件中不存在生产订单创建调用。执行通过，API F1 和 Coverage J 均为 0，200 个已计分变异体全部存活。可证实该测试验证了自建对象，具体每个变异体的因果影响仍需差分确认。','需求中的 cart、voucher、create an order 指向业务操作。正确业务调用的具体接线是否可由可见视图唯一确定仍需核对。'),
 '35':('有线索','准备路径与行为义务的对应关系','测试使用 Document 创建真实表格，先通过 height_rule setter 准备状态，再读取 getter 并与枚举或 None 比较。103 个变异体中杀死 101 个，2 个存活。真实调用和具体结果断言均存在。存活原因需要对照变异体差分，不能归因为缺少断言。','可见需求明确 getter 返回值，准备路径是否必须独立于 setter 尚无法判断。'),
 '37':('有线索','已覆盖显式断言后的剩余漏检','测试真实调用 lookupAssetTransactions(...).execute()，检查响应成功、currentRound、交易数量及指定 sender，覆盖了场景中显式列出的结果检查。27 个变异体杀死 21 个、6 个存活。它构成对“存活必然表示漏掉显式断言”的反例，具体缺失义务仍待变异体差分确认。','round、length、index 和 sender 在 Examples 中明确给出。其余隐含义务能否推导尚无法判断。'),
 '40':('已证实','成功对照','真实 Document 对象上的 latent_styles 经 setattr 写入指定属性，再用 getattr 读取，并按类型转换后的期望值断言。113 个已计分变异体全部杀死。该对照支持真实对象、写入和读取关系可由生成测试实现。','Given/When/Then 明确写入和读取关系。默认值准备的完整性仍受单个场景范围限制。')}
case_sections=[]
for number,(level,label,analysis,visible) in findings.items():
 d=prior/number;c=json.loads((d/'case.json').read_text());task=json.loads((d/'task.json').read_text());prediction=json.loads((d/'prediction.jsonl').read_text());evidence=root/'semantic_batches/batch-001'/number;evidence.mkdir(parents=True,exist_ok=True)
 for file in prediction['files']:
  dest=evidence/'generated'/file['path'];dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(file['content'])
 requirement=task['task']['criterion']['gherkin'].replace('\\n','\n');(evidence/'requirement.txt').write_text(requirement)
 m=c['metrics'];mutations=[json.loads(l) for l in (d/'mutation-records.jsonl').read_text().splitlines() if l.strip()];survivors=[x['mutant_id'] for x in mutations if x['outcome']=='passed']
 record=dict(instance_id=c['instance_id'],evidence_level=level,label=label,analysis=analysis,visible_information=visible,metrics=m,surviving_mutants=survivors,other_test_check='Checked all generated files in this prediction. ' + str(len(prediction['files']))+' file(s).',source_case=str(d),pending='Mutant source-level causal explanation and cross-project confirmation')
 (evidence/'analysis.json').write_text(json.dumps(record,ensure_ascii=False,indent=2));reviewed[c['instance_id']]=record
 code=[]
 for file in prediction['files']:
  lines=file['content'].splitlines();code.append(f"文件 `{file['path']}`，完整生成文件已保存至 `{evidence.relative_to(root)}/generated/`。\n\n"+'\n'.join(f'{i+1:03d} {line}' for i,line in enumerate(lines) if any(k in line for k in ['new class','items[]','Assert::','lookupAssetTransactions','assertThat','height_rule','assert actual','setattr','getattr'])))
 case_sections.append(f"## 案例 {number} · {label}\n\n任务 `{c['instance_id']}`。证据等级为{level}。\n\n```gherkin\n{requirement}\n```\n\n"+'\n\n'.join(code)+f"\n\n{analysis}\n\n{visible}\n\n已检查该预测的全部 {len(prediction['files'])} 个生成文件。原执行记录位于 `{d}/exec.jsonl`，变异执行记录位于 `{d}/mutation-records.jsonl`。存活变异体示例为 {', '.join(survivors[:6]) or '无'}。源码级因果解释待复核。\n")
fields=['benchmark','instance_id','stratum','source','annotation_status','phenomenon','evidence_level','finding','requirement','code_and_logs','other_tests_checked','cross_project_confirmed']
with (root/'FAILURE_CASE_DATABASE.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for c in selection:
  r=reviewed.get(c['instance_id']);row={k:c.get(k,'') for k in fields};row.update(annotation_status='reviewed_initial' if r else 'pending',phenomenon=r['label'] if r else '',evidence_level=r['evidence_level'] if r else '无法判断',finding=r['analysis'] if r else '',requirement=str(pathlib.Path(r['source_case'])/'task.json') if r else '',code_and_logs=r['source_case'] if r else c['evidence_directory'],other_tests_checked=r['other_test_check'] if r else '',cross_project_confirmed=False);w.writerow(row)
(root/'REPRESENTATIVE_CASES.md').write_text('# 阶段性案例证据\n\n本批复核 4 个已有案例，复用原始执行证据。56 个固定案例的语义复核仍待完成。\n\n'+'\n'.join(case_sections))
counts=collections.Counter((r['benchmark'],r['candidate']) for r in metrics)
table='\n'.join(f'| {b} | {c} | {n} |' for (b,c),n in sorted(counts.items()))
report=f'''# 增量式研究问题发现阶段报告

当前完成 TSB 165/165 条、Req2Test 780/2051 条，后者完成比例 {780/2051:.2%}。计分分母分别为 165 和 774，Req2Test 完成任务中有 6 条官方人口排除项。当前完成项目有选择性，结论适用于当前快照。

## 自动统计

| Benchmark | 可观测筛选类别 | 任务数 |
|---|---|---:|
{table}

这些类别来自官方指标。语义标签需要需求、全部生成测试和执行证据支持。TSB 部分测试有效的套件按照有效测试调查，完整套件通过与单个测试通过分别解释。

## 语义证据

固定 60 个开发分析任务，包含此前 40 个案例及新增 20 个分层任务。分层规则和来源保存在 semantic_selection.json，样本比例不用于总体发生率。当前复核 4 个 Req2Test 案例。1 个 CoreShop 案例证实使用替代业务对象断言，2 个存在真实调用和具体断言但仍有存活变异体，1 个 python-docx 成功对照杀死全部 113 个变异体。替代业务对象现象的确认数量为 1，涉及 1 个项目，普遍性尚待验证。

## 复用与增量

原始 TASK_INVENTORY.csv 保留，原报告备份位于 preserved-before-incremental。快照按内容哈希保存。incremental_analysis.py 以 benchmark 和 instance_id 唯一计数，比较新增 ID、变化行和首次出现的筛选类别。重复同一输入已验证新增 0、变化 0。refresh.py 只读取已完成评测，生成和评测调用数均为 0。

运行 `python3 diagnostics/problem-discovery-20261116/refresh.py` 可更新统计。语义记录追加到 semantic_batches，已有记录按任务复用。报告中的阶段性数字对应本次快照，后续以 incremental_progress.json 的更新时间和数字为准。

## 未完成与判断边界

56 个案例仍待语义复核，尚无跨项目复现的已确认行为机制。变异体源码级因果检查、TSB 行为案例、多个问题共现关系和语义标签与分数关联尚待完成。当前不具备分类饱和证据，研究问题保留待验证状态。依赖、语法、fixture 等执行问题单列为工程因素。
'''
(root/'PROBLEM_DISCOVERY_REPORT.md').write_text(report)
(root/'CROSS_BENCHMARK_ANALYSIS.md').write_text('''# 跨 Benchmark 阶段性分析

TSB 的分析单位首先是应用规格及整个生成套件，其有效率是测试级比例。Req2Test 的分析单位是具体 BDD 场景，可比较场景执行通过和 KillComplete。两者的通过率、变异分母以及语义标注粒度需要分别报告。

当前 TSB 165 条和 Req2Test 780 条已评测任务进入自动统计。Req2Test 计分 774 条。当前人工复核的替代业务对象案例来自 CoreShop，尚无 TSB 对应已确认案例。两个基准中存活变异体的共同出现只能说明待调查对象存在，底层原因是否共同仍待确认。

反例包括 Algorand 的真实调用及对需求显式结果的逐项断言、python-docx 的高变异检出测试和 KillComplete 对照。相同表面结果可以对应不同机制。TSB 完整规格的义务遗漏和 Req2Test 场景准备歧义暂时分别保留。
''')
(root/'RESEARCH_PROBLEM_CANDIDATES.md').write_text('''# 待验证研究问题

目前支持保留两个调查问题。重要性、发生频率和跨项目稳定性均待进一步证据。

## 真实业务调用与替代对象断言

痛点是测试可能对自己构造的结果进行正确断言，却未约束产品行为。CoreShop create_order_with_discount.feature:23 提供一例直接代码证据，执行通过、API F1 为 0、200 个变异体全部存活。当前确认 1 条、1 个项目。60 条开发样本尚有 56 条待语义复核，总体发生频率未知。

需要检查其他项目是否重复出现替代对象或空业务步骤，并确认框架是否注入额外调用。对已确认案例将真实业务操作与可见需求对齐，比较同项目真实调用的成功对照。已有覆盖与变异方法可以度量执行和检出情况，其对隐藏实现场景中的业务接线问题解决程度尚需文献和实验复核。

## 显式断言齐备后的行为漏检

Algorand v2indexerclient_responses.feature:15 检查了场景明确列出的 round、length、sender，并真实执行 SDK 请求，但仍有 6/27 个变异体存活。python-docx tbl-row-props.feature:29 有真实属性准备和读取，仍有 2/103 个存活。当前是 2 个项目中的机制线索，尚不能归为共同原因。

需要逐个对齐存活变异体、输入准备、调用和观察点，核实预期是否可从可见需求推导。频率与跨项目稳定性尚无法量化。原始对照、成功对照和反例应共同决定是否继续研究。不能从剩余漏检直接推出断言不足或需求理解失败。
''')
print('Wrote six interim deliverables; 4 initial reviews, 56 pending, no invented prevalence.')
