# 测试生成基线复现

TestSuiteBench 与 Req2Test-Bench 的 Codex CLI 基线：根据软件规格或需求生成可执行测试，并使用锁定版本的官方评测流程评分。

**Agent：Codex CLI 0.160.0；模型：GPT-6 Luna；思考等级：medium。** 固定子集这一轮于北京时间 2026-11-14 02:43:47 完成。

## 最新Req2Test全量结果（2026-11-18）

**eval清单2,051条、8个项目均有官方记录，全部ID已核对。** 已完成59,558条变异记录；4条异常按作者规则单列。协议人口排除14条，其他排除及各指标分母见报告，不将2,051直接当成所有指标的分母。

|Pass@1|KillComplete@1|API F1|Coverage J|Mutation R|
|---:|---:|---:|---:|---:|
|29.73%|13.33%|19.73%|26.14%|27.31%|

采用作者leaderboard模式，对8个项目等权平均。模型仍为Codex CLI + GPT-6 Luna、medium。全量结果独立发布，下面的固定160条成绩和原始产物保留。

- [全量报告、尾项原因与处理记录](reports/20261118-010456-Req2Test全量尾项恢复与统计修正/Req2Test全量评测与尾项处理-11-18.md)
- [官方原始全量报告](reports/20261118-010456-Req2Test全量尾项恢复与统计修正/Req2Test官方全量报告-11-18.md)
- [2,051条逐任务指标](reports/20261118-010456-Req2Test全量尾项恢复与统计修正/Req2Test全量逐任务指标-11-18.jsonl)
- [各项目结果和计分分母](reports/20261118-010456-Req2Test全量尾项恢复与统计修正/各项目指标与分母-11-18.csv)

## 固定子集基线（2026-11-14，保留原结果）

| Benchmark | 范围 | 最终指标 |
|---|---|---|
| TestSuiteBench | **165/165 全量** | Validity **74.67%**；Mutation Score **16.11%** |
| Req2Test-Bench | **160/160 固定子集，实际计分 159 条** | Pass@1 **27.57%**；KillComplete@1 **12.53%**；API F1 **19.37%**；Coverage J **23.76%**；Mutation R **24.80%** |

Req2Test 每个项目随机选取 20 条，共 8 个项目，种子为 20261112。官方排除 1 条 Sylius census_pass 实例；指标按项目等权平均。它不是 eval 的 2051 条全集，不能直接作为完整榜单成绩。

## 从这里查看

- [导师汇报：数据集特点、复现结果、真实代码与原因分析](reports/20261116-104005-需求驱动测试通俗汇报/导师一页汇报-11-16.md)
- [325条任务分类及已确认问题比例](reports/20261117-162415-全任务失败分类与比例统计/全任务失败分类与比例报告-11-17.md)

- [完整复现报告与说明](reports/test-generation-20261114/README.md)
- [官方原始报告、逐任务指标和各项目结果](results/test-generation-20261114/reports/)
- [325 条任务的生成产物与原始位置索引](results/test-generation-20261114/task-artifacts.json)
- [输入数据与软件规格](data/test-generation-20261114/)
- [生成测试与轨迹节选](results/test-generation-20261114/)
- [实际运行代码与环境补丁](code/test-generation-20261114/)
- [版本、预算、任务选择和环境记录](environment/test-generation-20261114/)

## 早期研究动机报告（后续修订见导师汇报）

[从真实商城案例读起](research/problem-discovery-final/科研动机报告-11-16.md) · [文献、证据册与验证计划](research/problem-discovery-final/本轮调研说明-11-16.md)

## 实证问题分析

2026-11-16 的阶段性研究包含已有结果审计、24 条 Pass-but-Non-Kill 分析，以及业务行为执行与观察缺口复核。

- [第二轮业务行为缺口分析](reports/business-behavior-gap-20261116/BUSINESS_BEHAVIOR_GAP_ANALYSIS.md)
- [833 对变异记录的逐对证据表](reports/business-behavior-gap-20261116/MUTANT_LEVEL_EVIDENCE.csv)
- [新增 20 条案例与 15 条 KillComplete 对照](reports/business-behavior-gap-20261116/CROSS_PROJECT_VALIDATION.md)
- [6 个 TestSuiteBench 任务的交叉核验](reports/business-behavior-gap-20261116/TSB_CROSS_VALIDATION.md)
- [研究动机候选及证据限制](reports/business-behavior-gap-20261116/RESEARCH_MOTIVATION_CANDIDATES.md)
- [上一轮 24 条专项分析](reports/pass-nonkill-20261116/README.md)
- [早期问题发现及增量统计](reports/problem-discovery-20261116/PROBLEM_DISCOVERY_REPORT.md)

第二轮新增样本来自 780/2051 条已完成任务的固定快照。20 条新增非 KillComplete 案例中确认 5 条缺口，另外 2 条证据不足。833 对记录对应 783 个唯一变异体，其中 830 对的逐对需求归属仍证据不足。定向样本中的比例仅描述本次选中集合。

目录保留需求、生成代码、候选执行记录、参考基线调用、变异修改、分类缓存和统计脚本。源码与执行文件沿用原始内容，Markdown 中的本地证据链接转换为仓库相对链接。服务器原始路径和历史核验记录保留用于溯源，发布副本使用独立的 [SHA-256 清单](reports/research-publication-manifest.json) 核验。

```bash
python3 scripts/verify_research_publication.py
```

提取脚本使用原实验服务器路径。历史报告中的服务器命令需要对应环境，发布副本的离线校验使用上面的命令。本轮发布未新增模型生成或评测调用。

## 文件内容与验证

本仓库发布 165 份 TestSuiteBench 规格、160 条 Req2Test 官方输入、生成测试文件、原格式预测、可见轨迹节选及完整性记录。生成文件附 SHA-256；长轨迹字符串的截断已明确标记。完整原始日志、详细执行矩阵、参考实现、变异体、Docker 镜像和大型缓存保留在实验服务器。

Req2Test 只对确认的 8 条基础设施异常进行恢复；其余 152 条预测和正式评分逐条验证不变。生成失败和测试失败照实保留，没有按评分重生成选优。修复、并发变化与结果限制见复现报告。

本地离线核验：

```bash
python3 scripts/verify_test_generation.py
cd code/test-generation-20261114/controller
python3 -m unittest -v test_generation_outcome.py test_seed_evaluation.py
```

GitHub Actions 执行相同的文件、指标和离线回归检查，不重新调用模型或运行完整 benchmark。

## 原始研究

| Benchmark | 论文 | 作者仓库 |
|---|---|---|
| TestSuiteBench | [arXiv:2610.13065](https://arxiv.org/abs/2610.13065) | [eth-sri/testsuitebench](https://github.com/eth-sri/testsuitebench) |
| Req2Test-Bench | [arXiv:2610.36584](https://arxiv.org/abs/2610.36584) | [code-philia/Req2Test-Bench](https://github.com/code-philia/Req2Test-Bench) |

第三方数据、规格和源码补丁的归属及许可遵循对应上游。账号凭据未包含在发布文件中。当前目录仅展示本轮测试生成复现，历史提交保留此前归档。

### 2026-11-16 逐案例数量与比例复核

[44条通过任务的逐项分析、项目分布与研究动机](reports/20261116-091532-全案例比例复核/案例数量与研究动机复核-11-16.md)
