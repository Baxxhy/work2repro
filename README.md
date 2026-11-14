# 测试演化复现与分析

## 本次新增：从软件规格生成测试（2026-11-14 完成）

Codex CLI 0.160.0 + GPT-6 Luna，思考等级 medium。

| Benchmark | 范围 | 最终核心指标 |
|---|---|---|
| TestSuiteBench | **165/165 全量** | Validity **74.67%**；Mutation Score **16.11%** |
| Req2Test-Bench | **160/160 固定子集，实际计分 159 条** | Pass@1 **27.57%**；KillComplete@1 **12.53%** |

[本轮完整复现报告与目录导航](reports/test-generation-20261114/README.md) · [官方报告与逐任务指标](results/test-generation-20261114/reports/) · [325 条生成产物索引](results/test-generation-20261114/task-artifacts.json) · [输入与规格](data/test-generation-20261114/) · [运行代码](code/test-generation-20261114/)

本轮追加了 325 条正式任务的生成结果、生成文件、可见轨迹节选、环境和恢复记录。Req2Test 为 8 个项目各 20 条，不是 eval 的 2051 条全量；结果按官方项目等权口径报告。完整原始日志及大型评测数据留在服务器。下面保留此前三方法测试演化实验的原始结果。


MuMuTestUp、TestUpdater、TestSyncer 在 PRBench 和 Updates4J 上的同模型复现。

模型为 GPT-6 Luna，思考等级 medium。仓库保留复现代码、766 条实验输入、2,298 条最终生成记录、逐样本指标、汇总表和调研报告。

## 测试通过率

| 数据集 | MuMuTestUp | TestUpdater | TestSyncer |
|---|---:|---:|---:|
| PRBench，571 条 | 501／571，87.7% | 433／571，75.8% | 211／571，37.0% |
| Updates4J，195 条 | 178／195，91.3% | 151／195，77.4% | 127／195，65.1% |

完整质量评测已覆盖原先通过的 1,601 条测试中的 1,578 条，另外 23 条仍有评测异常。覆盖率和变异分数在 `summary.csv` 中列出有效样本数。共同样本上的比较见调研报告。

## 从这里查看

- [三方法复现与研究问题分析](reports/test-evolution-20261108/测试演化三方法复现与研究问题分析.md)
- [六组指标汇总](results/summary.csv)
- [逐样本结果与指标](results/per-sample.csv)
- [数据集与字段说明](data/README.md)
- [复现代码](code/)

## 数据与结果

| 路径 | 内容 |
|---|---|
| `data/prbench.json` | 571 条输入，包含版本、旧测试、参考测试和被测方法信息 |
| `data/updates4j.json` | 195 条输入，使用本次复现的适配字段 |
| `results/MuMuTestUp/` | 两个数据集的最终生成代码、状态及指标 |
| `results/TestUpdater/` | 两个数据集的最终生成代码、状态及指标 |
| `results/TestSyncer/` | 两个数据集的最终生成代码、状态及指标 |
| `results/per-sample.csv` | 六组共 2,298 条记录的扁平表 |
| `results/summary.json` | 指标聚合规则、有效数量及异常数量 |
| `reports/` | 方法优缺点、共同样本分析、案例及研究方向 |
| `environment/` | 实验环境依赖版本 |

`sample_id` 由数据集、项目及零基索引组成，连接输入、方法输出和逐样本指标。`original_record` 保留原实验机的记录位置，便于追溯。TestSyncer 的 PRBench `apache/druid:32` 已核对为仅生成注释，精简结果中记为 `generation_failure`。

## 代码与运行

`code/` 保留实际运行器、环境修复、数据适配与作者源码文本。模型调用和执行入口位于各方法的 `deployment/`，统一质量评测入口位于 `code/comparison/`。

代码采用实验机 `/root/Baxxhy/work2/reproductions` 布局。重新运行时需配置对应路径、项目 checkout、分项目 JDK、Maven 与模型接口，数据文件保存了需要的仓库和提交。`results/` 可直接下载分析。

各方法的反馈轮次不同。JUnit 5 项目的兼容评测采用 PIT 1.15.2 和相应插件，其他项目保留运行记录中的版本。方法适配、环境处理与结果限制在报告中说明。

本仓库是精简分析版，原始运行日志、完整 XML／HTML 评测报告、环境缓存和历史试跑档案保留在实验服务器。

## 原始研究

| 方法 | 论文／官方来源 | 作者代码 |
|---|---|---|
| MuMuTestUp | [论文](https://arxiv.org/abs/2605.19265) | [GitHub](https://github.com/crazyTang-cloud/MuMuTestUp) |
| TestUpdater | [论文](https://arxiv.org/abs/2509.24419) | [GitHub](https://github.com/ZJU-CTAG/TestUpdater) |
| TestSyncer | [ICPC 2026](https://conf.researchr.org/details/icpc-2026/icpc-2026-research/23/Leveraging-Change-Types-and-Contexts-to-Guide-LLMs-for-Automated-Test-Code-Updating) | [GitHub](https://github.com/TestSyncer/TestSyncer) |

PRBench 来自 MuMuTestUp，Updates4J 来自 TestUpdater。第三方源码和数据的归属及许可遵循原项目。账号凭据已排除或脱敏。
