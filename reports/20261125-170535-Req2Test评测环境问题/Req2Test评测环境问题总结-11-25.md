# Req2Test 在 4x3090 上的评测环境问题

记录时间（北京时间）：2026-11-25 17:05:35 开始，17:07:00 完成核查。范围为 11 月 11 日的环境搭建和 11 月 25 日 GPT-6-luna Medium 全量运行的 PrestaShop 并发切换。

**8/8 个项目通过修复后的运行时预检。** 完整的官方样本校验有 python-docx 的 1/1 条记录。今天影响进度的是 PrestaShop 的 298 条输入，其中 29 条无可执行预测，269 条需要执行。切换时已完成 225/269（83.6%），剩 44 条。10 个 PHP worker 容器已启动，最新日志到达 10-worker reset-probe（重置检查）。截至核查时尚无新池的用例耗时，所以不能据此计算提速倍数。

| 环节 | 实际遇到的问题 | 处理和验证 |
|---|---|---|
| Docker 服务选择 | 评测账号 r2tbench 连接项目常用的 mutate-docker socket 得到 permission denied。Req2Test 同时会忽略环境变量 DOCKER_HOST，按自己的配置连接 Docker。 | 沿用已授权的专属 rootless daemon，镜像和容器数据位于 /root/lby-docker/req2test/user/benchmark/docker/data。核查时该服务下可见本轮 10 个 PHP 容器、数据库和模板容器。 |
| 容器启动 | 首次 python-docx validate 创建 worker 时出现 Mount too revealing。环境记录将原因定位到宿主 NVIDIA 的 proc 子挂载与新 user namespace 不兼容。 | 只对专用用户的 systemd 会话配置非递归 /proc 绑定。修复后最小容器可启动，后续 python-docx 官方单样本校验通过。 |
| 变异测试读取权限 | 较早一轮 python-docx 的 20/20 条普通执行通过，但变异阶段读取父目录失败。只看前半段会高估环境验证范围。 | 调整专用账号对所需父目录的 ACL 后，另用 1 条样本跑通完整链路，154/154 个变异对均被杀死，API F1 和 coverage J 均为 1.0。20 条的完整变异复验没有记录。 |
| 生成沙箱 | Ubuntu 的 user namespace 限制造成 bubblewrap 设置 loopback 时 RTM_NEWADDR 被拒。测试容器能启动，生成端仍可能失败。 | 为专用 bwrap 安装命名 AppArmor profile。修复后 python-docx、algorand-sdk、kapua、coddy-agent、coreshop、sylius、prestashop、e-petitions 的运行时预检退出码均为 0。 |
| 调度并发 | 实际生效的 supervise_diagnostic.py 把执行参数写成 --workers 1，同一时间只派一个评测组。PrestaShop 单 worker 日志约 148 秒/条。 | 给旧执行器发正常停止信号，核对逐条断点，备份 225 条执行记录及 29 条无预测记录；用同一 run ID 独立续跑，主调度器继续后续项目。 |
| PrestaShop 并发上限 | 申请 11 个 worker 时，第 11 个容器名 test_prestashop_ecae116aa_php_10 长 32 字符。dbadmin.py 对该标识符最多允许 31 字符，建池在 worker 规划阶段抛出 DatabaseRefused。 | 回收该次失败环境，改为编号 0–9 的 10 个 worker，已通过此前失败的命名步骤。这个上限取决于当前命名模板；此次报错本身不能证明 CPU 或内存耗尽。 |

## 怎样判断这轮是否真正恢复

主调度器快照中有 6 个项目组标为 finished，Sylius 为 running，PrestaShop 原单 worker 组为 infra_blocked。最后一个状态来自主动停止旧作业。独立续跑服务和汇总服务均为 active，核实进度要查看续跑日志及同一 run 下的 exec/raw。最终验收应看到剩余 44 条获得执行记录，并在 exec.jsonl 中按 ID 汇合为 298 条。全量生成状态另有 313/2051 条标为 infra_blocked；本次检查没有逐条归因，不能把它们计作本地配环境失败。

## 证据入口

以下路径相对于 4x3090。历史根因来自安装记录，复验结果、并发报错、容器数量和当前阶段来自日志、代码及现场查询。

- 专用用户目录 /root/lby-docker/req2test/user 下的 configuration-notes.md、validate-setup.log、validate-smoke.log、preflight-fixed.log 和 preflight/overall.exit。
- 同目录 repo/benchmark/r2t/bench/dbadmin.py 的 _IDENT 校验，以及 repo/req2test/execute.py 的逐条恢复与最终合并逻辑。
- 运行目录 /root/Baxxhy/work2/reproductions/req2test/req2test-medium-full-20261123 下的 state.json、control/supervise_diagnostic.py、parallel-resume-1/attempt-11-job.log、parallel-resume-1/job.log 和 parallel-resume-1/raw/。
