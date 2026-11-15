"""Render offline evidence and deterministic statistics from immutable subset."""
import csv, hashlib, json, re, statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = json.loads((ROOT / 'manifest.json').read_text())
SOURCE = ROOT.parents[1] / 'publication/work2repro/results/test-generation-20261114'

def load(path):
    return json.loads(path.read_text())

def write_csv(name, rows):
    with (ROOT / name).open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def link(path, label=None):
    return f'[{label or path.name}]({path.relative_to(ROOT).as_posix()})'

def excerpt(path, term, following=20):
    lines = path.read_text().splitlines()
    start = next((i for i,line in enumerate(lines) if term in line), 0)
    return '\n'.join(f'{i+1:4} {line}' for i,line in enumerate(lines[start:start+following], start))

def features(case, group):
    directory = ROOT / 'evidence' / case['artifact']['artifact_id']
    task = load(directory / 'task.json')
    requirement = task['requirement']
    text = (requirement['feature'].get('background') or '') + '\n' + requirement['scenario']['gherkin']
    paths = [p for p in (directory / 'generated').rglob('*') if p.is_file()]
    code = '\n'.join(p.read_text() for p in paths)
    return dict(instance_id=case['instance_id'], project=case['project'], group=group,
                language=task['environment']['language'], framework=task['environment']['framework'],
                scenario_kind=requirement['scenario']['kind'],
                gherkin_steps=len(re.findall(r'^\s*(?:Given|When|Then|And|But)\s', text, re.M)),
                example_data_rows=max(0,len(re.findall(r'^\s*\|', requirement['scenario']['gherkin'],re.M))-1) if requirement['scenario']['kind']=='outline' else 0,
                code_lines=len(code.splitlines()), code_files=len(paths),
                assertion_site_proxy=len(re.findall(r'\bassert\b|\bassertThat\s*\(|\bAssert::|\bexpect\s*\(|return fmt\.Errorf',code)),
                n_scored=case['n_scored'], n_killed=case['n_killed'], n_dropped=case['n_dropped'],
                mutation_recall=case['recall'], api_f1=case['api_f1'], coverage_j=case['coverage_j'])

CONTROL_NOTES = {
'0af839eba15d14e2da1b':'与Footer.iter_inner_content最接近。读取已有fixture并验证块类型次序及段落文本，93/93。对象由Document变为Footer，gold pool也不同，无法将成绩差异完全归因于加载fixture。',
'1181f3b3a11032dde790':'六行查询参数示例，真实构造SearchForAssets并对观测路径做精确相等比较。与response场景同项目但输出类型不同，21个pool较小。',
'3ed4dd6333d45d5c438e':'通过admin API生成coupon并查询collection数量，实际跨过管理员观测边界。与下单currency场景同项目，但promotion业务和107个变异集合不同。',
'5b6d2a356463dcb5ec19':'AddMeta命令后重新读取Meta，逐项比较page/title/description/url_rewrite。可与bulk-delete的命令及结果检查对照，业务类型不同。',
'e06a3c2e2fe0c51cee1a':'同一feature的XSS场景，真实走创建页面并断言不存在onmouseover属性，98/98。HTML检查仍不是完整标准校验，KillComplete不能证明所有需求维度充分。',
'ffee1edff496f2038c9e':'registry.Execute执行config_set与config_changes，再检查返回列表包含命令。与ask-mode相比，检查值来自真实工具调用。业务路径与205个变异池不同。',
'2247fcf10bc1e9313ee6':'属性读写同类对照，六个示例，直接Document()取得latent_styles后setattr/getattr精确比较，113/113。这是“程序化构造必然较差”的反例。',
'3b028264ab4a34f36c37':'真实空composer.buildGroup必须抛异常并保留BUILDING状态，76/76。不过catch仅验证异常非空，没有比较需求给出的错误文本，是KillComplete仍可能有oracle缺口的反例。',
'3c372d074b10efc34dca':'两行pending参数示例，调用实际SDK后用verifyPathUrls检查观察到的请求路径，19/19。与响应内容检查的任务复杂度和pool不同。',
'4bb1ed2b5f9a7c045cef':'三行exclude组合，真实SDK调用后读取lastRequest，精确比较URI路径及编码查询，19/19。直接检查最终外部输出，当前仅构成同项目类型较远对照。',
}

rows, mutants, feature_rows = [], [], []
parts = ['# 24 条 Pass-but-Non-Kill 任务专项分析\n',
'分析快照为2026-11-16。固定使用已发布160条子集，逐任务结果SHA256为 `'+MANIFEST['source_sha256']+'`。本目录中的分析与证据副本独立保存。\n',
'## 分母与结果核对\n',
'160条交付记录，官方排除1条，实际计分159条。执行通过44条，占159条的27.67%。KillComplete为20/159，即12.58%。通过且非KillComplete为24/159，即15.09%，占通过任务24/44，即54.55%。44=20+24，24条全部有非空scored变异集合。\n',
'官方排除项为 `'+str(MANIFEST['exclusions'])+'`，排除来自发布报告的官方人口定义。\n',
'官方G_i取参考测试杀死的变异体，扣除reference_excluded及reviewed nondeterministic项。n_scored=|G_i|−n_dropped，recall=n_killed/n_scored。KillComplete要求原实现passed、n_scored>0且n_killed=n_scored；strict还要求无drop。Python/Algorand/CoreShop/Sylius/coddy的timeout按规则drop，Kapua/PrestaShop/e-petitions的timeout可计kill，基础设施结果drop。coddy按官方规则接受带crash标记的failed。'+link(ROOT/'source-context/official-score.py','锁定版本计分源码')+'\n',
'24条共833个存活(instance_id,mutant_id)对，每对都在参考pool中gold_outcome=killed，在生成测试mutation记录中outcome=passed。全部生成文件与发布SHA256一致。coddy subagents_http另有5个dropped，已经独立列出。按存活记录作语义分析不改变官方分数。\n',
'## 判断边界\n',
'5条存在明确需求验证缺口，并能与代表性漏检路径联系起来。另1条确认断言关系缺失，但其11个存活的具体原因尚未确定。16条确认参考测试采用额外准备/调用/检查路径，其中各存活的动态传播完整性不同。剩余2条为INSUFFICIENT_EVIDENCE。按“存活主要解释”汇总为5条需求缺口、16条参考范围/路径差异、3条未确定。需求缺口观察量为6/24，代表性漏检可解释量为5/24。两种口径明确分开。\n',
'参考范围差异表示已观察到额外执行依赖；它不保证该任务所有存活均已解释。每条案例给出具体限制。官方pool保留kill标签，当前提取包没有逐变异参考堆栈，因此只将代码可解释的路径差异写为解释，未执行反事实复验。\n',
'当前24条是按结果选择的集合。任何比例仅描述该集合，无法外推到160条、2051条或其他模型。非执行通过任务不参与此轮语义归因。\n',
'## 逐任务证据\n']

for index,case in enumerate(MANIFEST['nonkill'],1):
    key=case['artifact']['artifact_id'];directory=ROOT/'evidence'/key
    task=load(directory/'task.json');annotation=load(directory/'analysis.json');execution=load(directory/'execution.json')
    survivors=load(directory/'surviving-mutants.json');mutation_rows={x['mutant_id']:x for x in load(directory/'mutation-results.json')}
    gold={x['mutant_id']:x for x in load(directory/'reference-kills.json')}
    assert len(survivors)==case['n_scored']-case['n_killed']
    reference_name,anchor=annotation['reference_anchor'].split('|',1)
    refs=[p for p in (directory/'reference').rglob(reference_name) if anchor in p.read_text()]
    generated=[p for p in (directory/'generated').rglob('*') if p.is_file()]
    reference_location=';'.join(str(p.relative_to(ROOT))+':'+str(next(i+1 for i,l in enumerate(p.read_text().splitlines()) if anchor in l)) for p in refs)
    assert refs, (key,reference_name,anchor)
    group='requirement_gap' if annotation['adjudication']=='CONFIRMED_REQUIREMENT_GAP' else 'reference_scope_difference' if annotation['adjudication']=='CONFIRMED_SCOPE_DIFFERENCE' else 'unresolved'
    rows.append(dict(instance_id=case['instance_id'],project=case['project'],artifact_id=key,
                     category=annotation['category'],evidence_status=annotation['adjudication'],cause_group=group,
                     requirement_gap_confirmed=annotation['requirement_gap_confirmed'],passed=case['passed'],
                     kill_complete=case['kill_complete'],n_scored=case['n_scored'],n_killed=case['n_killed'],
                     n_survived=len(survivors),n_dropped=case['n_dropped'],recall=case['recall'],
                     generated_files=';'.join(str(p.relative_to(ROOT)) for p in generated),reference_location=reference_location,
                     execution_record=str((directory/'execution.json').relative_to(ROOT)),
                     analysis=annotation['analysis'],all_survivors_explained=False))
    feature_rows.append(features(case,'pass_nonkill'))
    parts += [f'### {index:02d} {case["instance_id"]}\n',
              f'分类 `{annotation["category"]}`，证据状态 `{annotation["adjudication"]}`。实际执行 `{execution["outcome"]}`，杀死 {case["n_killed"]}/{case["n_scored"]}，存活 {len(survivors)}，drop {case["n_dropped"]}。\n',
              '#### 需求原文\n', '```gherkin\n'+(task['requirement']['feature'].get('background') or '')+'\n'+task['requirement']['scenario']['gherkin']+'\n```\n',
              '#### 输入、调用、观察及未验证行为\n',annotation['analysis']+'\n',
              '本条全部交付文件均在下方列出，未发现另有生成文件补足上述已确认缺口。保留步骤由官方执行入口装配，reference中的其他场景函数不作为本任务已执行证据。\n',
              '#### 生成代码与执行证据\n']
    for p in generated:
        parts += [link(p)+'\n','<details><summary>带行号的原始生成代码</summary>\n\n```text\n'+''.join(f'{i+1:4} {line}\n' for i,line in enumerate(p.read_text().splitlines()))+'```\n\n</details>\n']
    step_results=execution.get('per_step') or []
    parts += ['官方执行记录 '+link(directory/'execution.json')+'，退出码 `'+str(execution.get('exit_codes'))+'`。\n',
              '```json\n'+json.dumps(step_results,ensure_ascii=False,indent=2)+'\n```\n',
              '#### 对应参考测试\n']
    for p in refs:
        parts += [link(p)+'\n','```text\n'+excerpt(p,anchor,24)+'\n```\n']
    parts += ['对应参考kill记录 '+link(directory/'reference-kills.json')+'，候选变异结果 '+link(directory/'mutation-results.json')+'。以下列出全部存活修改，gold列为官方pool标签。\n',
              '|变异ID|源码位置|原文|修改后|gold|candidate|\n|---|---|---|---|---|---|\n']
    for mutant in survivors:
        mid=mutant['id'];assert gold[mid]['gold_outcome']=='killed';assert mutation_rows[mid]['outcome']=='passed'
        original=str(mutant.get('original',''));replacement=str(mutant.get('mutated',''))
        vals=[mid,mutant['file']+':'+str(mutant.get('start_line')),original,replacement,'killed','passed']
        parts.append('|'+ '|'.join(v.replace('|','\\|').replace('\n','<br>') for v in vals)+'|\n')
        mutants.append(dict(instance_id=case['instance_id'],project=case['project'],mutant_id=mid,
                            file=mutant['file'],line=mutant.get('start_line'),operator=mutant.get('operator'),
                            original=original,mutated=replacement,gold_outcome='killed',candidate_outcome='passed',
                            semantic_attribution='see task annotation; pair-specific cause not automatically assigned'))
    parts.append('\n')
(ROOT/'PASS_NONKILL_CASE_ANALYSIS.md').write_text('\n'.join(parts))
write_csv('FAILURE_MECHANISM_DATABASE.csv',rows)
write_csv('surviving_mutant_pairs.csv',mutants)

controls=['# KillComplete 对照分析\n',
'固定选择10条，来自20条KillComplete候选。先按instance_id SHA256排序，在每个有可用成功任务的项目选1条，再依同一排序补足10条。覆盖6个项目。CoreShop和Kapua在这20条中没有KillComplete可配对。选择已冻结于manifest.json。优先保留同项目对照，需求类型相近度在逐项描述中明确。算法补足导致Algorand有4条，未达到每条失败均有相同需求类型对照的理想匹配。\n',
'代码行数包含注释和装配代码。assertion_site_proxy只是跨语言词法计数，Go的错误返回也可能是准备错误，不等同语义断言数。需求步骤数来自Gherkin关键字，outline的数据行数独立记录。未构造主观“复杂度分数”，未作显著性检验。\n']
for index,case in enumerate(MANIFEST['controls'],1):
    key=case['artifact']['artifact_id'];d=ROOT/'evidence'/key;task=load(d/'task.json');f=features(case,'killcomplete_control');feature_rows.append(f)
    controls += [f'## {index:02d} {case["instance_id"]}\n',CONTROL_NOTES[key]+'\n',
                 f'实测passed，KillComplete=true，{case["n_killed"]}/{case["n_scored"]}，drop={case["n_dropped"]}。语言 {f["language"]}，框架 {f["framework"]}，Gherkin步骤 {f["gherkin_steps"]}，示例数据行 {f["example_data_rows"]}，代码 {f["code_lines"]} 行。\n',
                 '```gherkin\n'+task['requirement']['scenario']['gherkin']+'\n```\n',
                 '原始执行 '+link(d/'execution.json')+'，逐变异结果 '+link(d/'mutation-results.json')+'。\n']
    operator_counts = Counter(item['operator'] for item in load(d/'control-mutants.json'))
    controls.append('变异修改类型 '+str(dict(sorted(operator_counts.items())))+'。对应原始修改 '+link(d/'control-mutants.json')+'。\n')
    for p in (d/'generated').rglob('*'):
        if p.is_file():controls.append(link(p)+'\n')
    (d/'control-analysis.json').write_text(json.dumps(dict(note=CONTROL_NOTES[key],features=f),ensure_ascii=False,indent=2)+'\n')
write_csv('control_features.csv',feature_rows)
controls += ['## 描述性比较\n','|分组|任务数|代码行数中位数|步骤数中位数|scored变异数中位数|\n|---|---|---|---|---|\n']
for group in ['pass_nonkill','killcomplete_control']:
    selected=[x for x in feature_rows if x['group']==group]
    controls.append(f'|{group}|{len(selected)}|{statistics.median(x["code_lines"] for x in selected)}|{statistics.median(x["gherkin_steps"] for x in selected)}|{statistics.median(x["n_scored"] for x in selected)}|\n')
controls += ['\n成功对照同时包含读取fixture和直接构造对象。明确边界输出、真实调用和充分准备值得继续检查，但这些观察没有控制任务、pool规模、项目及需求类型。尤其空composer错误文本和XSS标记校验反例说明KillComplete不能替代需求审查。\n',
'对照侧的787个变异记录已提取对应修改，按任务/操作符分布保存在mutation_operator_counts.csv。成功侧统计全部被杀死项，非Kill侧统计存活项，条件不同，不能直接解释为操作符导致成绩差异。\n']
(ROOT/'KILL_COMPLETE_CONTROL_ANALYSIS.md').write_text('\n'.join(controls))

project_rows=[]
for project in sorted({x['project'] for x in rows}):
    selected=[x for x in rows if x['project']==project]
    project_rows.append(dict(project=project,n_nonkill=len(selected),confirmed_gap_observed=sum(x['requirement_gap_confirmed'] for x in selected),
                             gap_linked_to_representative_survival=sum(x['cause_group']=='requirement_gap' for x in selected),
                             reference_scope_difference=sum(x['cause_group']=='reference_scope_difference' for x in selected),
                             unresolved_survival=sum(x['cause_group']=='unresolved' for x in selected)))
write_csv('project_mechanism_counts.csv',project_rows)
counts=Counter(x['cause_group'] for x in rows)
summary=dict(fixed_population=MANIFEST['denominators'],nonkill_tasks=24,controls=10,surviving_pairs=len(mutants),
             cause_groups=dict(counts),requirement_gaps_observed=sum(x['requirement_gap_confirmed'] for x in rows),
             projects=project_rows,new_generation_calls=0,new_evaluation_tasks=0,
             mutation_pair_causality='no new intervention; group-level explanations only where supported',
             control_selection=MANIFEST['control_rule'])
(ROOT/'analysis_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
