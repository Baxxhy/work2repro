# 从软件规格生成测试：两项基线复现

本轮使用 **Codex CLI 0.160.0 + gpt-6-luna，reasoning=medium**。运行顺序为 TestSuiteBench 后 Req2Test-Bench。TestSuiteBench 为锁定版本的全部 165 个有效任务；Req2Test 为固定的 160 条分层随机子集，每项目 20 条，不是 2051 条 eval 全集。

最终于北京时间 **2026-11-14 02:43:47** 完成。325 个任务 ID 均有正式结果。完成表示产物和评测状态齐全，不表示所有测试通过。

## 最终指标

| Benchmark | 运行任务数 | 实际计分分母 | 指标 | 数值 |
|---|---:|---:|---|---:|
| TestSuiteBench | 165 | 165 | Validity | 74.666995% |
| TestSuiteBench | 165 | 165 | Mutation Score | 16.112327% |
| Req2Test 160 子集 | 160 | 159 | Pass@1 | 27.565789% |
| Req2Test 160 子集 | 160 | 159 | KillComplete@1 | 12.532895% |
| Req2Test 160 子集 | 160 | 159 | API F1 | 19.366232% |
| Req2Test 160 子集 | 160 | 159 | Coverage J | 23.755382% |
| Req2Test 160 子集 | 160 | 159 | Mutation R | 24.803743% |

TSB 先按任务计算指标再取平均。有效测试是在三次参考执行中稳定通过的测试；仅这些测试能贡献变异检出。Req2Test 使用官方 `leaderboard` 模式，8 项目等权平均；Sylius 的一个 `census_pass` 实例按 benchmark 1.1 官方人口规则排除，因此分母 159。官方摘要中的 `complete: false` 表示未覆盖整个 eval 人口，不表示这 160 条尚未完成；子集不能直接当作完整榜单成绩。

## 输入、输出与逐任务追溯

- [TSB 全部规格](../../data/test-generation-20261114/testsuitebench-specifications/)：165 个任务，每个任务是一份完整软件行为规格。
- [TSB 通用任务提示词](../../data/test-generation-20261114/testsuitebench-prompt.txt)：生成 `eval/run.sh`、测试文件和 JUnit XML 的协议。
- [Req2Test 输入](../../data/test-generation-20261114/req2test-tasks.jsonl)：160 条官方导出的 TH 任务视图描述、需求、目标接口、放置规则及环境说明。
- [生成产物索引](../../results/test-generation-20261114/task-artifacts.json)：连接 instance_id、文件摘要及原服务器记录位置。
- [TSB 生成测试与轨迹节选](../../results/test-generation-20261114/testsuitebench/tasks/)。
- [Req2Test 原格式预测](../../results/test-generation-20261114/req2test/predictions.jsonl)及[生成文件与轨迹节选](../../results/test-generation-20261114/req2test/tasks/)。
- [全部官方报告与逐任务指标](../../results/test-generation-20261114/reports/)。

例如真实任务 [`tomnomnom__gron.88a6234`](../../data/test-generation-20261114/testsuitebench-specifications/tomnomnom__gron.88a6234/spec.md)，模型生成了 [test_cli.py](../../results/test-generation-20261114/testsuitebench/tasks/tomnomnom__gron.88a6234/generated/test_cli.py) 和运行脚本。官方记录 43 个用例，其中 40 个稳定有效，检出 20/54 个变异体：Validity 93.023256%，Mutation Score 37.037037%。

## 修复与恢复的边界

TSB 的最后 3 条因镜像构建网络/依赖获取问题补跑。保留了 Node 24.22.2、Codex 0.160.0 等既有版本，APT 使用同一官方站点的 HTTPS；Go 工具链保持作者要求。补丁与修改依据保存在环境和代码目录。

Req2Test 的首次队列存在完成判定问题：官方生成器在超时后也会写预测行，外层曾以“预测文件存在”误判正常完成。审计发现 5 条网络停滞、2 条零调用超时、1 条启动前进程资源异常。仅恢复这 8 个 ID，其余 152 条预测和正式评分逐条校验完全不变。恢复的 8 条各进行一次新生成，最终只有 1 条测试通过；正常失败和没有交付文件的结果照实保留，没有按分数选优。

3 条 PHP 日志检查使用独立运行获取完整 stdout，确认是生成 Context 的依赖注入错误，诊断评分没有替换原成绩。缓存导入接入修复前产生的额外 Python/Kapua 执行记录保留为诊断，最终采用预先确定的原始 152 条证据。最后 Coddy 变异评测从 1 worker 升为 3 workers，保留 836 项检查点，完整执行剩余 130 项；官方 600 秒超时、变异体集合及计分规则不变。

修复前 Req2Test Pass@1 为 26.940789%，修复后为 27.565789%；KillComplete@1 不变。基础设施恢复无法解释其与论文的全部差距。本轮是 medium 与固定 160 子集，论文对应 Luna 行是 high 与 eval 全集，CLI 版本也不同，不能宣称同配置复现了论文成绩。

## 配置与重现

- [版本与依赖](../../environment/test-generation-20261114/)，包括仓库提交、数据 revision、完整任务选择、调用预算和并发修改记录。
- [实跑控制器、认证传输适配与补丁](../../code/test-generation-20261114/)。这里保留原服务器路径，属于实跑快照；迁移时需准备自己的目录、Docker 和模型认证，不能把已结束的历史队列当成新任务直接启动。
- TSB 使用 rootful Docker，Req2Test 使用专用普通用户 `r2tbench` 和官方管理的 rootless Docker。Docker 持久目录位于 `/root/lby-docker`，两个服务没有互相切换或重启。
- TSB 只运行 `test_gen`，未开启 `--testgen-with-code`。生成预算 21600 秒/任务；Req2Test 预算 200 次模型调用、3600 秒/任务。模型调用通过实际可用的认证服务，未导出任何账户凭据，真实费用不可得。
- 正式数据应从锁定的官方数据源获取；本仓库仅发布模型允许看到的输入和自己的生成结果，不打包参考实现、参考测试、变异体、大型运行包或 Docker 镜像。

TSB 单任务官方入口的实跑参数形式为：

```bash
bash scripts/agents/generate_tests_codex.sh \
  --task tomnomnom__gron.88a6234 --cleanroom ground_truth/spec \
  --output YOUR_OUTPUT --model gpt-6-luna --reasoning medium \
  --timeout 21600 --docker-cpus 2
```

Req2Test 使用锁定官方 `req2test.inference.run_agent`，由 `req_agent.py` 只适配模型服务、medium 和 JSON 轨迹；沙箱、任务提示词、文件收集和预算沿用官方。官方 evaluate/report 执行评分。配置中的模型网关是原服务器的根用户托管传输层，重新运行时须配置自己的认证，不包含公共可用账户或 endpoint。

## 发布内容与限制

轨迹文件是**可见操作轨迹节选**：保留消息、命令、文件变更、工具结果等，单个长字符串截取前 4000 字符并明确标记截断。完整原始轨迹和详细执行矩阵保留在服务器，可从 `original_record` 追溯。生成文件按原字节保存并附 SHA-256；未把 `results.xml`、pytest 缓存或 Python 字节码当作生成测试上传。

CI 只核验发布文件完整性、计分汇总与离线回归，不重新调用模型，也不把 CI 当成重新运行完整 benchmark 的证据。

## 原始来源

- TestSuiteBench：[论文](https://arxiv.org/abs/2610.13065)、[作者仓库](https://github.com/eth-sri/testsuitebench)。
- Req2Test-Bench：[论文](https://arxiv.org/abs/2610.36584)、[作者仓库](https://github.com/code-philia/Req2Test-Bench)。

第三方规格、数据字段和源码补丁的归属及许可遵循对应上游；上游 LICENSE 副本见代码目录。这里没有用本次结果证明新方法有效。
