import csv
import json
from collections import Counter
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

here = Path(__file__).resolve().parent
root = here.parents[1]
src = root/'diagnostics/20261126-140902-全量生成本机Pass复评'
board = json.loads((root/'reproductions/req2test/repo/results/leaderboard.json').read_text())
arm = next(r['arm'] for r in board['rows'] if 'Luna' in r['model'])
high = {x['project']:x for x in board['cells'] if x['arm']==arm and x['view']=='th'}
protocol = json.loads((src/'预测快照/final-pass-at-1.json').read_text())['population_exclusions']
total = Counter()
services = 0
with (here/'逐任务分类.csv').open('w') as out:
    writer = csv.writer(out,lineterminator='\n')
    writer.writerow(['任务','项目','计分','本机结果','自动装配错误日志'])
    table = []
    for p,h in high.items():
        logs = {x['item_id']:x for x in map(json.loads,(here/'执行记录'/f'{p}.jsonl').open())}
        rows = list(map(json.loads,(src/'本机评分'/p/'instances.jsonl').open()))
        assert len(rows)==len(logs)==len({r['instance_id'] for r in rows})
        counts = Counter()
        for r in rows:
            i = r['instance_id']
            log = logs[i]
            outcome = r['engine_outcome']
            assert log['outcome']==outcome
            valid = i not in protocol and not r['exclusion']
            msg = 'cannot autowire service' in log.get('stdout_tail','').lower() and outcome=='container_error'
            writer.writerow([i,p,int(valid),outcome,int(msg)])
            if valid:
                counts[outcome]+=1
                services+=int(msg)
        total.update(counts)
        n = sum(counts.values())
        table.append(f"| {p} | {counts['passed']}/{n} | {counts['passed']/n:.2%} | {h['pass']}/{h['pass_den']} | {h['values']['pass_at_1']:.2%} |")
print(total,services)
end=datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%F %T')
report=f"""# Req2Test 全量通过率核查

北京时间 2026-11-27 02:07:38 开始，{end} 完成。八项目共 2,051 条预测，逐条关联本机原始执行记录，14 条协议排除，1 条基础设施排除。2,036 条计分，573 条通过，项目宏平均 32.34%。两台机器的逐条通过标记一致。

| 项目 | 本机通过/有效 | 本机 Medium | 作者通过/有效 | 作者 High |
|---|---:|---:|---:|---:|
"""+'\n'.join(table)+"""

作者 High 的项目宏平均为 66.2%。作者论文行与本轮使用的计分人口存在小幅差异，见逐项目分母。生成均禁用运行包，CLI 版本与公开预算一致。模型推理档位、模型服务和外层运行流程未做控制变量实验。相同预测跨机复现仅验证评分一致性。

## 计分任务的原始结果分类

"""+'\n'.join(f"- {k} 共 {v} 条，占计分任务 {v/2036:.2%}。" for k,v in total.most_common())+f"""

Kapua 的一个凭据场景中，生成的 AccountCredentialSteps.java 错用 KapuaServiceLoader.getService 的参数并产生泛型不匹配，Maven 编译失败。CoreShop 购物车税项场景中，生成的 CartItemTaxesContext 构造器请求未注册的 ContainerInterface，Symfony 创建服务失败。有效任务中共有 {services} 条 container_error 的 stdout_tail 明确包含 Cannot autowire service。其余错误需要逐日志解释。failed 是执行器的通用失败分类，不据此断定断言错误。

[逐任务分类](逐任务分类.csv) · [统计脚本](核查.py) · [锁定版本排行榜](https://github.com/code-philia/Req2Test-Bench/blob/c0d7138f408bb7935d2c82e0fed82884f519b199/results/leaderboard.json)

原始执行日志留在本机本目录的“执行记录”下。作者未提供本次核查可用的逐任务配对结果，无法把官方与本轮的差距唯一归因于某一处配置。
"""
(here/'全量通过率核查-11-27.md').write_text(report)
