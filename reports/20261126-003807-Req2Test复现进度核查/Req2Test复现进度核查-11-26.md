# Req2Test 在 4x3090 上的复现进度

核查时间为北京时间 2026-11-26 00:38:07 至 00:42:06。通过 SSH 只读检查 4x3090 上的生成、评测、补跑和结算记录。进程快照中没有活动的 Req2Test 生成或评测进程。

## 全量 Medium

GPT-6-luna Medium 本轮共 2,051 条，覆盖八个项目。1,738 条生成任务结束且拥有逐条执行结果（84.7%），313 条在生成阶段因网络中断（15.3%）。按 ID 核对，1,738 条生成完成记录与执行结果一一对应。执行结果中有 489 条通过（489/1,738，28.1%）。这个比例的分母是已有执行结果的任务，计数包含无预测等执行结局，且未计算变异指标。全量结算服务因结果少 313 条而在完整性检查处退出。

| 项目 | 总任务 | 有执行结果 | 执行通过 | 网络中断 |
|---|---:|---:|---:|---:|
| algorand-sdk | 111 | 95 | 44 | 16 |
| coddy-agent | 274 | 227 | 72 | 47 |
| coreshop | 334 | 282 | 14 | 52 |
| e-petitions | 98 | 85 | 31 | 13 |
| kapua | 330 | 278 | 63 | 52 |
| prestashop | 348 | 298 | 43 | 50 |
| python-docx | 237 | 204 | 154 | 33 |
| sylius | 319 | 269 | 68 | 50 |
| 合计 | 2,051 | 1,738 | 489 | 313 |

执行结果另有 failed 482 条、parse_or_compile_error 214 条、undefined_steps 191 条、container_error 157 条、no_files_returned 139 条、no_scenario_ran 49 条、solution_error 16 条和 harness_error 1 条。本次核查未逐条归因这些执行结局，也未验证网络中断的具体故障点。

- 网络补跑清单中的 260 个 ID 全在 313 个缺失 ID 内。260 条全部以 network_interruption 结束，产生 0 条新执行记录。另有 53 条未纳入该补跑。
- PrestaShop 的 10 worker 实际处理了尾部 44 条，作业落盘的退出码为 0，合并后的执行文件共 298 行，其中 43 条通过。systemd 中续跑和汇总服务仍保留失败状态。汇总日志显示它检查退出记录时未通过断言，现场以合并文件、最终项目组和逐条结果交叉验证。
- 11 月 20 日的 [历史全量基线](../20261120-161942-Req2Test最终结算/官方最终报告-11-20.md) 已按官方排行榜口径结算，八项目宏平均 Pass@1 为 30.2%，KillComplete@1 为 13.6%。本轮的 489/1,738 是执行记录的汇总计数，使用不同分母和聚合口径。

## 其他批次

两组配对使用同一批 80 个 ID，八项目各 10 条，两组均有 80 条执行记录。A 通过 31/80（38.8%），B 通过 39/80（48.8%）。24 条两组都通过，34 条两组都未通过，15 条只在 B 通过，7 条只在 A 通过。该统计限于配对样本。

论文配置增量批次有 1,971 条新生成任务，7 条生成结束，8 条停留在 running，1,956 条停留在 pending。最近的状态文件写于北京时间 11 月 23 日 15:27:20，现场没有相应运行进程。现有 10 条对照执行结果来自原预测的 algorand-sdk 项目组。

## 证据和验证

- 远端运行根目录为 `/root/Baxxhy/work2/reproductions/req2test/`。本次读取了其中的 `req2test-medium-full-20261123`、`req2test-medium-network260-1123`、`req2test-b-incremental-20261123` 和两个 `req2test-paired80-20261123-*` 下的 `state.json`、`completion.json`（存在时）和 `result_comparison.json`。生成及执行计数按任务 ID 关联，另核对 `settlement-coverage.json` 的缺失数。
- PrestaShop 续跑证据为全量目录中的 `parallel-resume-1/exit.json`、`parallel-resume-1/job.log`，以及基准运行目录 `req2test-medium-full-20261123-regenerated-prestashop/prestashop/th/exec.jsonl`。服务退出和汇总失败来自对应 systemd journal。
- 本记录只归档聚合结果与证据位置，远端原始实验产物保留在原位置。
