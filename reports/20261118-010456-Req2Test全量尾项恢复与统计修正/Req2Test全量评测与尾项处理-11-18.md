# Req2Test全量评测与尾项处理

开始时间：北京时间2026年11月18日01:04:56。完成核对时间：2026-11-18T01:40:06.237598+08:00。

## 最终状态

**eval清单2051条、8个项目均有官方逐任务记录，没有遗漏或额外ID。官方汇总的8项目complete均为true。** 这表示官方流程的结果收集完整，不表示所有生成测试都通过，也不表示所有任务都进入同一计分分母。

本轮已经实际补跑4条原异常任务。最终4条仍按作者规则列为基础设施排除，没有修改生成测试、补写成功状态或改变评分规则。因此控制器仍保留2047条finished、4条infra_blocked，不能称为2051条全部正常执行。任务结束后服务退出是本轮有界队列到达终态，不是还有348条PrestaShop在等待运行。

全量官方结果采用项目等权平均：

|指标|全量结果|
|---|---:|
| Pass@1 | 29.73% |
| KillComplete@1 | 13.33% |
| API F1 | 19.73% |
| Coverage J | 26.14% |
| Mutation R | 27.31% |

配置：Codex CLI 0.160.0，gpt-6-luna，medium，Target-hidden视图。作者仓库锁定提交c0d7138f408bb7935d2c82e0fed82884f519b199。运行中的超时扩展与记录器修复沿用已归档配置，本轮没有新增模型调用。

## 分母与排除

|层次|数量|处理|
|---|---:|---|
|原始eval任务清单|2051|全部保留逐任务结果|
|官方人口规则排除|14|11条census_pass、3条zero_body；仍保留原始记录|
|协议人口|2037|KillComplete@1使用各项目的协议人口分母|
|基础设施排除|4|Coddy 2条、PrestaShop 2条|
|outside_ladder排除|2|Coddy、CoreShop各1条passed_but_nonzero_exit|
|Pass@1各项目分母合计|2031|先按项目计算，再对8项目等权平均|

不能把2051、2047、2037或2031混称为“所有指标的分母”。API F1与Coverage J沿用作者I-set口径及leaderboard缩放，Mutation R沿用作者聚合公式。逐项目人数及分母见《各项目指标与分母-11-18.csv》，完整规则与结果见原始官方JSON/Markdown。

## 修复了什么

1. **修复控制器误报整项目阻塞。** 原控制器只要发现项目中有一条基础设施排除，就把整个项目标为infra_blocked，导致把Coddy274条、PrestaShop348条都显示成未完成。现在按官方逐任务结果更新状态，真正待处理的是4条，不是622条。
2. **修复基础设施补跑的两层缓存衔接。** fixture_consumed被官方计分器列为基础设施，但外层execute及内层runner的恢复集合遗漏了它。仅在本次授权恢复中把它纳入有界重试；正常通过、正常失败及已完成变异不重跑，计分归类保持原样。
3. **补充Coddy原生执行证据。** 使用作者支持的evidence_dir记录2条异常的stdout和native事件。首次诊断把元数据先写进了要求为空的目录，导致0.2秒时被拒绝；已修正为元数据在父目录、官方capture目录保持空，并新增回归检查。这一技术失败及正确重跑日志均保留。
4. **补齐全量官方报告。** 两个带排除项的项目此前没有被控制器合并到全量报告中；现已合并8个项目并完成2051条ID核对，保留原项目路径的符号链接。

以上修改在独立恢复wrapper与控制器中，作者checkout保持不变。它们是调度、统计与附加日志修复，不是生成方法改进。

## 四条最终异常

|项目与任务|实际复核证据|最终处理|
|---|---|---|
|Coddy hooks_subagents.feature:28|测试期望子任务被钩子阻止，但实际产生成功子任务；断言调用外层t.Fatalf，触发parent FailNow并留下不完整native记录|保留作者harness_error，不改断言、不把它人工改成普通失败或成功|
|Coddy llm_limit_wait.feature:45|Before钩子将Godog返回的testingT断言为支持TempDir的对象；实际接口不支持，发生类型转换异常，官方native校验拒绝|保留作者harness_error，不通过更换依赖或修改测试来救该样本|
|PrestaShop add_virtual_product_file.feature:104|在全新隔离worker实际执行，仍报告fixture_consumed，约151.4秒|保留作者基础设施排除|
|PrestaShop update_product_type.feature:236|在全新隔离worker实际执行，仍报告fixture_consumed，约150.3秒|保留作者基础设施排除|

PrestaShop作者的prestashop_resources.py明确规定：被上传流程移动或删除的dummyFile样例会恢复原始字节，并报告fixture_consumed。故不能把这两条简单归因于服务器缺文件，也不能通过取消保护或改写生成测试伪造正常结果。

## 原结果保护与验证

- 2047条非目标任务的执行记录逐字段一致。
- 2051条生成产物的produced_files逐字段一致。
- 8项目共59558条唯一变异记录全部完成，并与恢复前快照逐键逐内容一致。Coddy10869条、PrestaShop1031条没有重跑。
- 4条目标任务均不属于原固定160条子集；原固定子集报告和已发布成绩保留。
- 2051个官方逐任务ID与冻结任务清单一一对应，无缺失、无重复、无额外ID。
- 7项控制器/诊断目录回归通过；额外核对作者外层_finished和内层_resume_set仅恢复基础设施记录、保留正常通过和失败记录。

原生证据见《Coddy两条原生执行证据-11-18.json》，定向运行日志、官方原始报告、逐任务指标、全量清单和离线核验脚本均在本目录。

## 实际作业与路径

主控制器：req2test-eval2051-resume-20261117-v1.service。初次尾项恢复InvocationID为7a7820023f4645e0abbcc3ecb21a8b82；缓存衔接修复后的InvocationID为52104d24da5c42e0848c8010e2168bf6。

PrestaShop最终作业：3ad7b05c87e24f9f9df636e4d5996a1b，2个隔离worker，已经实际完成2条补跑。
Coddy最终定向单元：req2test-tail-coddy-native-20261118-v2.service，InvocationID为be8eae3dc846451a88fa9beda7308227，2个隔离worker，退出码0。

运行根目录：/root/Baxxhy/work2/reproductions/req2test/req2test-eval2051-resume-20261117-v1。
官方结果根目录：/root/lby-docker/req2test/user/benchmark/runs/req2test-eval2051-resume-20261117-v1。
原始生成、轨迹、大型缓存和完整原生证据仍在服务器；本次没有删除或重新下载。

## 重复核验

```bash
python3 verify_full_delivery.py
python3 -m unittest discover -s . -p test_project_status.py
```

这两项是离线交付核验，不重新运行模型或Benchmark。全量结果也不代表已有固定160条的语义分析自动扩展到了2051条。
