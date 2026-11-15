"""Render frozen, manually adjudicated evidence. Reads existing results only."""
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.parent / 'pass-nonkill-20261116'
A = json.loads((ROOT / 'annotations.json').read_text())
MANIFEST = json.loads((ROOT / 'manifest.json').read_text())

def read(path):
    return json.loads(path.read_text())

def key(instance):
    return hashlib.sha256(instance.encode()).hexdigest()[:20]

def link(path, label=None):
    return f'[{label or path.name}]({path.resolve()})'

def dump_csv(path, rows):
    with path.open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

def requirement(task):
    r = task['requirement']
    return '\n'.join(x for x in [r['feature'].get('narrative'), r['feature'].get('background'), r['scenario']['gherkin']] if x)

def source_links(directory):
    return '、'.join(link(p) for p in sorted(directory.rglob('*')) if p.is_file())

def numbered_code(directory, pattern=None):
    chunks = []
    for path in sorted(directory.rglob('*')):
        if not path.is_file():
            continue
        lines = path.read_text(errors='replace').splitlines()
        if pattern:
            selected = set()
            for i, line in enumerate(lines):
                if re.search(pattern, line, re.I):
                    selected.update(range(max(0, i-2), min(len(lines), i+4)))
        else:
            selected = range(len(lines))
        chunks += [link(path), '\n```text\n' + '\n'.join(f'{i+1:4} {lines[i]}' for i in sorted(selected)) + '\n```']
    return '\n\n'.join(chunks)

pairs = list(csv.DictReader((OLD / 'surviving_mutant_pairs.csv').open()))
occurrences = Counter((r['project'], r['mutant_id']) for r in pairs)
counts = Counter(r['instance_id'] for r in pairs)
rows = []
cache = {}
for r in pairs:
    k = key(r['instance_id'])
    if k not in cache:
        d = OLD / 'evidence' / k
        cache[k] = (read(d/'task.json'), read(d/'execution.json'), read(ROOT/'gold-execution'/f'{k}.json')['record'])
    task, candidate, gold = cache[k]
    line = int(r['line'])
    c_covered = line in candidate.get('coverage_lines', {}).get(r['file'], [])
    g_covered = line in gold.get('coverage_lines', {}).get(r['file'], [])
    matching_calls = [c for c in gold.get('direct_calls', []) if c.get('callee_file') == r['file']]
    relevance = 'INSUFFICIENT_EVIDENCE'
    explanation = '逐对需求相关性尚未确认；源码修改和执行标签完整，不按任务标签批量归因'
    witness = A['old'].get(k, {}).get('witness')
    if witness and r['mutant_id'] == witness:
        relevance = 'EXPLICIT_REQUIREMENT_SUPPORTED'
        explanation = A['old'][k]['note']
    rows.append({**r,
        'scoped_mutant_id': r['project'] + '/' + r['mutant_id'],
        'task_occurrences_of_mutant': occurrences[(r['project'], r['mutant_id'])],
        'task_survivor_count': counts[r['instance_id']],
        'requirement_original': requirement(task),
        'task_gap_class': A['old'].get(k, {}).get('class', 'not_reclassified_this_round'),
        'requirement_relevance': relevance,
        'semantic_evidence': explanation,
        'gold_baseline_mutation_start_line_covered': g_covered,
        'candidate_baseline_mutation_start_line_covered': c_covered,
        'gold_baseline_calls_in_mutated_file': json.dumps(matching_calls, ensure_ascii=False),
        'gold_per_mutant_failing_path': 'UNAVAILABLE_IN_EXTRACTED_ARTIFACTS',
        'gold_baseline_trace': str(ROOT/'gold-execution'/f'{k}.json'),
        'candidate_execution': str(OLD/'evidence'/k/'execution.json'),
        'candidate_mutation_execution': str(OLD/'evidence'/k/'mutation-results.json'),
        'reference_kill_record': str(OLD/'evidence'/k/'reference-kills.json'),
        'reference_test_directory': str(OLD/'evidence'/k/'reference')})
dump_csv(ROOT/'MUTANT_LEVEL_EVIDENCE.csv', rows)
summary = {
    'frozen_subset_tasks':160, 'official_scored_tasks':159, 'passed':44, 'kill_complete':20,
    'pass_nonkill':24, 'task_mutant_pairs':len(rows),
    'unique_task_mutant_pairs':len({(r['instance_id'],r['mutant_id']) for r in rows}),
    'unique_project_mutants':len(occurrences),
    'unique_raw_mutant_ids':len({r['mutant_id'] for r in rows}),
    'mutants_shared_between_tasks':sum(v>1 for v in occurrences.values()),
    'extra_pair_occurrences':sum(v-1 for v in occurrences.values()),
    'gold_start_line_covered':sum(r['gold_baseline_mutation_start_line_covered'] for r in rows),
    'candidate_start_line_covered':sum(r['candidate_baseline_mutation_start_line_covered'] for r in rows),
    'pair_requirement_relevance':dict(Counter(r['requirement_relevance'] for r in rows)),
    'new_nonkill_class_counts':dict(Counter(x['class'] for x in A['new'].values())),
    'new_nonkill_status_counts':dict(Counter(x['status'] for x in A['new'].values())),
    'completed_snapshot_tasks':MANIFEST['available_completed'], 'planned_full_tasks':2051,
    'new_controls':len(MANIFEST['controls']), 'new_nonkill':len(MANIFEST['nonkill']),
    'control_same_feature':sum(x['same_feature'] for x in MANIFEST['matching']),
    'control_same_scenario_kind':sum(x['same_kind'] for x in MANIFEST['matching']),
    'new_model_or_evaluation_calls':0,
}
(ROOT/'audit-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')

main = ['# 需求指定业务行为的执行与观察缺口\n',
'''## 阶段性判断

当前证据支持“存在重复出现的执行、准备或观察缺口”。“经常发生”的总体频率仍无法确定。旧6例来自按结果筛选的24例，新增20例按项目定额筛选，模型和生成配置也仅覆盖本次Codex GPT-6 Luna medium复现。

旧6例跨6个项目，复核后为A操作未执行2例、B目标状态未观察1例、C结果关系或异常约束未断言2例、A_setup必要准备状态未建立1例。coddy同时具有A/B/C，以A作互斥主分类。Sylius和python-docx的真实目标操作已有动态执行证据，上一轮分类在本报告修正。

新增20条通过但非KillComplete案例中，5条观察到明确缺口，分布于CoreShop与e-petitions。包括3条背景准备缺失、1条管理员状态/页面未观察、1条列表关系断言缺失。另2条证据不足，13条未确认明确需求缺口。5/20只描述本次筛选集合，其中3条CoreShop背景缺失与主要操作漏检的因果关系尚未证明。

15条新增KillComplete对照中，1条仍有列表对象—值关系断言缺失。缺口可以伴随KillComplete出现；低分也可能来自参考额外准备、调用或检查。现有结果不足以据此识别模型能力的单一根因。

## 固定数据与计分

旧子集160条，官方排除1条census_pass，实际计分159条。执行通过44条，其中20条KillComplete、24条通过且存在存活变异体。官方G_i为参考测试杀死集合，扣除reference_excluded与reviewed nondeterministic；n_scored=|G_i|−n_dropped，recall=n_killed/n_scored。KillComplete还要求原实现通过、n_scored>0且全部scored变异被杀死。项目timeout/drop规则沿用锁定源码。coddy旧任务的5个drop和Kapua重复观测告警均保留。

新增样本来自780条已完成任务的固定快照，占2051条计划集合38.03%。780是完成记录数，不能直接用作官方质量计分分母。新35条均为原实现通过且mutation_status=scored，15条控制为KillComplete。完成快照之后的运行进度不影响本轮分析。
''',
link(OLD/'source-context/official-score.py','官方计分源码')+'；'+link(ROOT/'manifest.json','新增固定任务清单')+'；'+link(ROOT/'audit-summary.json','核对结果'),
'''## 证据等级与类别

A指需求指定的目标操作被空步骤、自建对象或自定义行为替代。A_setup单列必要前置状态缺失，以免把已执行的目标操作误写为未执行。B指真实操作执行后未观察需求指定角色、对象或外部边界。C指观察存在，但断言未核验具体值、类型或对象关系。D用于检查了无直接关系的其他行为，本轮没有需要单独确认的D案例。E为证据不足。N表示当前审查没有确认该缺口，不能解释为已证明需求完全满足。

“确认缺口”由需求与代码义务对照决定。“代表性存活可解释”需要相应变异和执行标签支持。“实际变异传播路径已观测”需要变异运行轨迹或失败位置。本轮取得官方参考基线gold_run的direct_calls及coverage_lines，逐变异pool主要提供killed标签，无法补全每个变异的失败堆栈。以下明确区分这些层级。

## 旧6例重新核验
''']
for k, note in A['old'].items():
    d = OLD/'evidence'/k
    task, candidate, gold = cache[k]
    metrics = read(d/'metrics.json')
    main += [f"### {task['instance_id']}\n",
             f"主分类与兼类 `{note['class']}`，证据状态 `{note['status']}`。原实现 `{candidate.get('outcome')}`，杀死 {metrics.get('n_killed')}/{metrics.get('n_scored')}，存活 {counts[task['instance_id']]}。",
             '```gherkin\n'+requirement(task)+'\n```', note['note'],
             '#### 实际调用、状态读取与断言位置\n', numbered_code(d/'generated', note['anchor']),
             '#### 开发者路径及执行证据\n',
             '参考源码入口见 '+source_links(d/'reference')+'。', numbered_code(d/'reference', note['anchor']),
             f"候选基线direct_calls有{len(candidate.get('direct_calls',[]))}条，官方参考基线有{len(gold.get('direct_calls',[]))}条。调用条数只用于溯源，不作为行为质量指标。",
             link(d/'execution.json','候选逐步执行与调用')+'；'+link(ROOT/'gold-execution'/f'{k}.json','参考实际基线调用')+'；'+link(d/'reference-kills.json','逐变异参考kill标签')+'；'+link(d/'surviving-mutants.json','具体修改位置')+'；'+link(d/'mutation-results.json','候选变异执行结果'),
             '全部交付生成文件已经纳入检查，未发现其他生成文件补足上述明确缺口。参考源码内其他场景函数的存在不代表本场景实际执行。']
main += ['## 833对记录审计\n',
 f"833条均为唯一(task,mutant)对，对应{len(occurrences)}个唯一(project,mutant)，原始mutant_id也有{summary['unique_raw_mutant_ids']}个。{summary['mutants_shared_between_tasks']}个变异体在多个任务中出现，造成{summary['extra_pair_occurrences']}条跨任务重复计入。每个任务的存活数量如下。\n",
 '|项目|任务|存活对数|\n|---|---|---|']
for iid,n in sorted(counts.items()):
    main.append(f'|{iid.split("/")[0]}|{iid}|{n}|')
main += [f"\n全部833对均为gold killed、candidate passed。参考基线覆盖全部833个变异起始行；候选基线覆盖{summary['candidate_start_line_covered']}个，另{833-summary['candidate_start_line_covered']}个未覆盖。该统计按任务—变异对计算，同一源行和变异体可重复出现。行未覆盖与需求范围差异、fixture差异和真实漏执行均可能有关。",
'''逐变异表保存原始修改、位置、每任务存活数、跨任务出现次数、生成与参考结果、参考基线实际同文件调用和证据路径。3个已逐对对照的旧代表变异标记EXPLICIT_REQUIREMENT_SUPPORTED，其余830对需求相关性保留INSUFFICIENT_EVIDENCE。旧任务级判断不会被自动传播到所有变异。这些记录缺少足以完成逐对语义归因的证据，不能把833对作为833个已确认需求缺陷。

## 研究结论的适用范围

操作未真正执行在CoreShop订单与coddy工具调用中有直接证据，覆盖PHP/Behat与Go/Godog。必要准备缺失在python-docx/behave与CoreShop/Behat出现。观察边界缺失涉及Sylius管理员订单读回与e-petitions管理员页面条件，两者保留各自业务含义。结果断言约束缺失涉及Kapua/Java异常约束与e-petitions/Ruby对象—值关系。跨项目的共同点是明确需求义务在测试链中失去对应约束；这些具体机制尚不能合并为同一因果解释。

本轮沿用原始评测和生成产物，全部新增工作为读取、静态对照及统计。没有针对缺口重新执行反事实实验。两条e-petitions新代表变异有源码与已有kill/pass支持，但其实际DOM和逐变异参考失败位置未保存，传播细节仍属有证据的推断。
''']
(ROOT/'BUSINESS_BEHAVIOR_GAP_ANALYSIS.md').write_text(re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)', r'\1\n', '\n\n'.join(main))+'\n')

cross = ['# 新增跨项目验证\n',
'''## 固定选择规则

从已完成780条快照中，按项目分别筛选原实现通过、有非空计分变异且非KillComplete的任务。排除上一轮24例、10条控制以及此前60例语义清单中的ID。四个有合格新增候选的项目各取SHA256稳定排序前5条，共20条。该规则保留了参考范围差异、缺口和未定案例。

控制按项目轮转，从未分析的KillComplete任务中优先同feature，再同scenario kind，再标题token Jaccard，最后SHA256打破平局，共15条。每条控制独立使用一次。自动匹配只能提供候选，下面另记语义匹配强弱。因已完成数据分布限制，尚未补充新的Sylius、coddy、Kapua或PrestaShop项目样本。
''', link(ROOT/'select.py','可复核选择脚本')+'；'+link(ROOT/'manifest.json','固定清单和全部配对'),
'## 新增20例汇总\n\n|项目|确认缺口|证据不足|未确认缺口|总计|\n|---|---|---|---|---|']
for project in sorted({r['project'] for r in MANIFEST['nonkill']}):
    notes = [A['new'][key(r['instance_id'])] for r in MANIFEST['nonkill'] if r['project']==project]
    c=Counter(n['status'] for n in notes)
    cross.append(f"|{project}|{c['CONFIRMED_GAP']}|{c['INSUFFICIENT_EVIDENCE']}|{c['NO_CONFIRMED_GAP']}|{len(notes)}|")
cross += ['\n该比例仅描述按项目定额选取的20例。主分类A_setup 3、B 1、C 1、E 2、N 13。与旧6例合计观察到缺口的11例跨6项目，其中多个例子可能共享背景模板；任务独立性不足以支持因果或总体频率估计。', '## 新增逐任务分析\n']
case_rows=[]
for group in ['nonkill','controls']:
    if group=='controls':
        cross += ['## 15条KillComplete对照\n',f"自动配对中同feature为{summary['control_same_feature']}/15，同scenario kind为{summary['control_same_scenario_kind']}/15。后者只表示场景语法形式相同。全部同项目，但不能据此视为需求难度匹配。"]
    for row in MANIFEST[group]:
        k=key(row['instance_id']);d=ROOT/'evidence'/k;task=read(d/'task.json');e=read(d/'execution.json')
        note=A['new'][k] if group=='nonkill' else {'class':'C' if k=='51402702ed0f9175add9' else 'N','status':'CONTROL_GAP' if k=='51402702ed0f9175add9' else 'CONTROL','note':A['controls'][k]}
        case_rows.append({'instance_id':row['instance_id'],'project':row['project'],'group':group,'class':note['class'],'status':note['status'],'n_killed':row['n_killed'],'n_scored':row['n_scored'],'n_survived':row['n_scored']-row['n_killed'],'analysis':note['note'],'evidence_directory':str(d)})
        cross += [f"### {row['instance_id']}\n",f"`{note['class']}` / `{note['status']}`。原实现 `{e.get('outcome')}`，杀死{row['n_killed']}/{row['n_scored']}，存活{row['n_scored']-row['n_killed']}，drop {row['n_dropped']}。",'```gherkin\n'+requirement(task)+'\n```',note['note']]
        if group=='controls':
            match=next(x for x in MANIFEST['matching'] if x['control']==row['instance_id'])
            cross.append(f"配对任务 `{match['target']}`。同feature={match['same_feature']}，同scenario kind={match['same_kind']}，标题Jaccard={match['title_jaccard']:.3f}。匹配限制见上面的语义说明。")
        cross += ['生成代码见 '+source_links(d/'generated')+'。',
            link(d/'execution.json','实际逐步执行和调用')+'；'+link(ROOT/'gold-execution'/f'{k}.json','参考基线调用')+'；'+link(d/'mutation-results.json','候选全部变异结果')+'；'+link(d/'surviving-mutants.json','存活修改')+'；'+link(d/'reference-kills.json','参考杀死标签'),
            '参考测试见 '+source_links(d/'reference')+'。']
        if note['status'] in ('CONFIRMED_GAP','CONTROL_GAP'):
            cross += ['#### 对应生成代码位置\n',numbered_code(d/'generated')]
        witness=note.get('witness')
        if witness:
            m=next(m for m in read(d/'surviving-mutants.json') if m['id']==witness)
            cross += [f"代表变异 `{witness}`，`{m['file']}` 第{m['start_line']}行。",'```diff\n- '+m['original']+'\n+ '+m['mutated']+'\n```']
            relevant = ROOT/'source-context/e-petitions'
            cross.append('相关生产源码 '+source_links(relevant)+'。')
        cross.append('本任务全部交付文件均纳入对照。未保存的逐变异堆栈或页面状态保持未知。')
cross += ['## 跨项目判断与反例\n',
'''主要操作完全被替代在旧CoreShop和coddy中重复；本轮20例没有新增这种A主操作案例。A_setup在CoreShop三个新场景重复，与旧python-docx具有准备义务相似性，但商店背景和页眉实际定义对目标结果的重要性不同。

新e-petitions管理员场景支持B观察缺口，与Sylius共同涉及需求指定角色可见状态。两者一个漏核验登录/页面，另一个读取了操作中的共享对象，不能声称完全相同机制。e-petitions列表关系缺失在新搜索场景、旧创建场景及一条KillComplete控制重复，当前属于单项目内稳定现象。Kapua异常类型/文本属于另一种C约束，尚无同类型跨项目复现。

Algorand真实HTTP URI核验、python-docx真实footer内容准备、CoreShop汇率持久化及实体锁跨对象检查提供正向反例。15条控制中1条关系缺口和20条nonkill中13条未确认缺口说明，KillComplete和该现象之间没有一一对应关系。本轮样本不适合估计因果效应，也不构成对所有需求义务的穷尽审计。
''']
(ROOT/'CROSS_PROJECT_VALIDATION.md').write_text(re.sub(r'(?m)(\|[^\n]*\|)\n\n(?=\|)', r'\1\n', '\n\n'.join(cross))+'\n')
dump_csv(ROOT/'case-classifications.csv',case_rows)
print(json.dumps(summary,ensure_ascii=False,indent=2))
