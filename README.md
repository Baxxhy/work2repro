# 测试生成基线复现

TestSuiteBench 与 Req2Test-Bench 的 Codex CLI 基线：根据软件规格或需求生成可执行测试，并使用锁定版本的官方评测流程评分。

**Agent：Codex CLI 0.160.0；模型：GPT-6 Luna；思考等级：medium。** 本轮于北京时间 2026-11-14 02:43:47 完成。

## 最终结果

| Benchmark | 范围 | 最终指标 |
|---|---|---|
| TestSuiteBench | **165/165 全量** | Validity **74.67%**；Mutation Score **16.11%** |
| Req2Test-Bench | **160/160 固定子集，实际计分 159 条** | Pass@1 **27.57%**；KillComplete@1 **12.53%**；API F1 **19.37%**；Coverage J **23.76%**；Mutation R **24.80%** |

Req2Test 每个项目随机选取 20 条，共 8 个项目，种子为 20261112。官方排除 1 条 Sylius census_pass 实例；指标按项目等权平均。它不是 eval 的 2051 条全集，不能直接作为完整榜单成绩。

## 从这里查看

- [完整复现报告与说明](reports/test-generation-20261114/README.md)
- [官方原始报告、逐任务指标和各项目结果](results/test-generation-20261114/reports/)
- [325 条任务的生成产物与原始位置索引](results/test-generation-20261114/task-artifacts.json)
- [输入数据与软件规格](data/test-generation-20261114/)
- [生成测试与轨迹节选](results/test-generation-20261114/)
- [实际运行代码与环境补丁](code/test-generation-20261114/)
- [版本、预算、任务选择和环境记录](environment/test-generation-20261114/)

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
