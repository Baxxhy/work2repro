# Req2Test Medium 全量结算

4x3090 对 GPT-6-luna Medium 的 313 条任务补跑覆盖八个项目，执行结果齐全，85/313 条通过。与原有 1,738 条合并后于北京时间 2026-11-26 09:17:40 完成结算。北京时间 14:00 至 14:01 复核确认 2,051 个唯一 ID，原批次与补跑 ID 无重叠，全集与最终结算逐条记录一致。

按官方排行榜的八项目宏平均口径，Pass@1 为 **32.34%**。官方口径计入 2,036 条，573 条通过，按任务汇总为 28.14%。该轮执行评测没有补测变异指标。

| 项目 | 补跑条数 | 全量计分分母 | 通过条数 | Pass@1 |
|---|---:|---:|---:|---:|
| algorand-sdk | 16 | 111 | 52 | 46.85% |
| coddy-agent | 47 | 273 | 87 | 31.87% |
| coreshop | 52 | 328 | 15 | 4.57% |
| e-petitions | 13 | 98 | 36 | 36.73% |
| kapua | 52 | 330 | 74 | 22.42% |
| prestashop | 50 | 348 | 49 | 14.08% |
| python-docx | 33 | 237 | 185 | 78.06% |
| sylius | 50 | 311 | 75 | 24.12% |

[结算核验](全量结算核验-11-26.json)包含完整计数。现场证据位于 4x3090 的 `/root/Baxxhy/work2/reproductions/req2test/req2test-medium-recovery313-20261126`，入口为 `recovery-result-check.json`、`final-pass-at-1.json` 和 `final-instances.jsonl`。[断网恢复记录](Req2Test断网修复与续跑-11-26.md)
