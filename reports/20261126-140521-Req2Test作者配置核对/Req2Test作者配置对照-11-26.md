# Req2Test 全量 Medium 与作者 Luna 配置对照

北京时间 2026-11-26 14:04 至 14:05 核查，14:05:21 取得运行器证据。范围为 4x3090 上已经结算的 2,051 条 Target-hidden 任务，与论文 Table 4 的 Codex CLI / GPT-6 Luna 对照。

| 项目 | 作者公开配置 | 4x3090 本轮 |
|---|---|---|
| 模型与推理 | GPT-6 Luna，high | GPT-6 Luna，medium。原批次 1,738/1,738 条、补跑 313/313 条最后一次生成任务的首次上游请求均核实为该配置 |
| 数据与视图 | 全部 2,051 个 eval 实例，论文同时评测 TH 和 AH | 2,051 个 eval ID，TH。按 Benchmark 1.1 计分人口和执行有效性规则纳入 2,036 条 |
| CLI 和预算 | Codex CLI 0.153.4，3,600 秒，最多 200 次模型请求 | CLI 0.153.4，3,600 秒，发布版运行器的 200 次调用预算 |
| 生成运行包 | 论文禁用 Runtime Packs | 两批适配器均替换运行包初始化，仅传入工作区 |
| 提示词、运行器和访问路径 | 论文描述公开协议，论文实际提示词与每项沙箱绑定未做逐条对照 | 使用发布版 build_prompt 和运行器，外层增加本地 ChatGPT 网关、JSON 轨迹与断点续跑。基准仓库为 c0d7138f408bb7935d2c82e0fed82884f519b199，现场无已跟踪源码差异 |
| 正式评测 | 原生运行器、覆盖与变异，两种视图均报告 Pass@1、KillComplete@1、API F1、Coverage J 和 Mutation R | 只完成 TH 的 exec 评测与 Pass@1 汇总，32.34%。PrestaShop 恢复批次用 10 个评测 worker，其余项目为单 worker |

可将结果描述为按照作者公开协议运行的 **GPT-6 Luna Medium 全量 TH 执行基线**。公开资料和现场证据不足以确认作者实际提示词、模型服务状态、宿主与评测容器配置逐项一致。论文 TH 行的 66.2% 与本轮 32.34% 的差距缺少同环境全量 High 对照，不能单独归因于推理档位。

## 证据入口

- [论文实验配置与流程](https://arxiv.org/html/2610.36584v1#S4.SS3)
- [官方排行榜与论文运行包说明](https://github.com/code-philia/Req2Test-Bench/blob/main/results/leaderboard.md)
- [官方代理协议的锁定版本](https://github.com/code-philia/Req2Test-Bench/blob/c0d7138f408bb7935d2c82e0fed82884f519b199/docs/agents.md)
- [本轮全量结算](../20261126-004751-Req2Test断网恢复/Req2Test全量结算-11-26.md)
- 远端 `/root/Baxxhy/work2/reproductions/req2test/` 下的 `req2test-medium-full-20261123` 和 `req2test-medium-recovery313-20261126`。从各批次 `state.json` 选取每个生成完成 ID 的最后一次生成作业，仅统计 `first-provider-request.json` 的模型及推理档位。运行器配置取自冻结配置、实际 `agent.py` 和评测监督器。
