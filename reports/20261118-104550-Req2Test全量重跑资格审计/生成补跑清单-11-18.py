import collections
import csv
import json
from pathlib import Path

root = Path(__file__).resolve().parent
baseline = root.parent / '20261118-010456-Req2Test全量尾项恢复与统计修正'
prior = root.parent / '20261118-103039-Req2Test生成中断误计审计'
load = lambda name: json.loads(name.read_text())
evidence = load(root/'全量执行证据信号-11-18.json')
extra = {row['id']:row for row in load(root/'未交付疑点复核-11-18.json')}
for row in evidence['tasks']:
    check = extra.get(row['id'])
    if check and check['events'].get('turn.completed') and not row['job']:
        assert row['outcome'] == 'no_files_returned' and row['trace_exists']
        row['terminal'] = check['events']
known_429 = {row['id'] for row in load(prior/'限流中断任务-11-18.json')}
with (baseline/'逐任务状态与排除原因-11-18.csv').open() as source:
    status = {row['instance_id']:row for row in csv.DictReader(source)}
assert len(status) == len(evidence['tasks']) == 2051
assert set(status) == {row['id'] for row in evidence['tasks']}

def classify(row, official):
    if row['id'] in known_429:
        assert row['stop'] == 'exit 1' and row['gateway_http'] == [429]
        assert row['terminal'].get('turn.failed') and not row['terminal'].get('turn.completed')
        return 'generation_rerun', '生成请求被限流且未完成'
    if not row['terminal'].get('turn.completed') and row['generation_issue'] and row['outcome']=='no_files_returned':
        return 'generation_rerun', {'thread_start':'运行器线程启动失败','view_read':'官方视图压缩包读取失败',
                                    'launch_transport':'生成运行器或传输失败'}[row['generation_issue']]
    if official == 'population_excluded':
        return 'protocol_excluded', '作者预设人口排除'
    if official == 'infrastructure_excluded':
        return 'evaluation_blocked', '官方评测异常，已有隔离复跑证据'
    if official == 'outside_ladder_excluded':
        return 'review_exit', '步骤通过但进程非零退出，需区分测试清理与评测器故障'
    if row['generation']=='failed' and not row['stop'] and not row['trace_exists']:
        return 'review_missing_evidence', '历史退出缺少运行日志或轨迹'
    if (row['terminal'].get('turn.failed') or row['stop']=='timed out') and not row['terminal'].get('turn.completed'):
        if row['trace_http'] or row['gateway_http'] or row['stop']=='timed out':
            return 'review_generation', '生成结束信号异常，需核查是否由平台中断'
    if set(row['exec_signals']) & {'host_resource','docker_transport','missing_dependency'}:
        return 'review_evaluation', '日志出现环境错误提示，需绑定到实际失败点'
    if row['outcome'] in {'container_error','parse_or_compile_error','solution_error','no_scenario_ran'} and not row['exec_signals']:
        return 'review_evaluation', '执行失败但现有摘要不足以定位责任'
    if row['outcome']=='no_files_returned' and not row['terminal'].get('turn.completed'):
        return 'review_generation', '未交付且缺少可核验的正常终止事件'
    return 'retain', '保留现有结果'

fields = ['instance_id','project','disposition','outcome','decision','reason','job','stop','calls','exec_signals']
inventory=[]
for row in evidence['tasks']:
    original = status[row['id']]
    decision,reason = classify(row,original['disposition'])
    inventory.append(dict(instance_id=row['id'],project=row['project'],disposition=original['disposition'],
        outcome=row['outcome'],decision=decision,reason=reason,job=row['job'],stop=row['stop'],
        calls=row['calls'],exec_signals='|'.join(row['exec_signals'])))
for filename, rows in (
    ('全部任务补跑资格-11-18.csv',inventory),
    ('补跑与进一步核实清单-11-18.csv',[r for r in inventory if r['decision'] not in {'retain','protocol_excluded'}])):
    with (root/filename).open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fields,lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
print('decisions',collections.Counter(r['decision'] for r in inventory))
for d in sorted({r['decision'] for r in inventory}-{'retain','protocol_excluded'}):
    rows=[r for r in inventory if r['decision']==d]
    print(d,collections.Counter(r['project'] for r in rows),collections.Counter(r['reason'] for r in rows))
print('mutation',collections.Counter(r['outcome'] for r in evidence['mutation_exception_rows']))
