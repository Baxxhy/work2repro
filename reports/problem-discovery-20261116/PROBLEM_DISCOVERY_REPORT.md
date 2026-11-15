# 增量式研究问题发现阶段报告

当前完成 TSB 165/165 条、Req2Test 780/2051 条，后者完成比例 38.03%。计分分母分别为 165 和 774，Req2Test 完成任务中有 6 条官方人口排除项。当前完成项目有选择性，结论适用于当前快照。

## 自动统计

| Benchmark | 可观测筛选类别 | 任务数 |
|---|---|---:|
| req2test | execution_assertion_failure | 178 |
| req2test | execution_binding_failure | 44 |
| req2test | execution_compilation_failure | 121 |
| req2test | execution_execution_failure | 13 |
| req2test | execution_generation_failure | 133 |
| req2test | execution_infrastructure_excluded | 1 |
| req2test | killcomplete_control | 127 |
| req2test | officially_excluded | 6 |
| req2test | passing_with_survivors | 157 |
| testsuitebench | no_reference_passing_tests | 5 |
| testsuitebench | valid_tests_with_survivors | 160 |

这些类别来自官方指标。语义标签需要需求、全部生成测试和执行证据支持。TSB 部分测试有效的套件按照有效测试调查，完整套件通过与单个测试通过分别解释。

## 语义证据

固定 60 个开发分析任务，包含此前 40 个案例及新增 20 个分层任务。分层规则和来源保存在 semantic_selection.json，样本比例不用于总体发生率。当前复核 4 个 Req2Test 案例。1 个 CoreShop 案例证实使用替代业务对象断言，2 个存在真实调用和具体断言但仍有存活变异体，1 个 python-docx 成功对照杀死全部 113 个变异体。替代业务对象现象的确认数量为 1，涉及 1 个项目，普遍性尚待验证。

## 复用与增量

原始 TASK_INVENTORY.csv 保留，原报告备份位于 preserved-before-incremental。快照按内容哈希保存。incremental_analysis.py 以 benchmark 和 instance_id 唯一计数，比较新增 ID、变化行和首次出现的筛选类别。重复同一输入已验证新增 0、变化 0。refresh.py 只读取已完成评测，生成和评测调用数均为 0。

运行 `python3 diagnostics/problem-discovery-20261116/refresh.py` 可更新统计。语义记录追加到 semantic_batches，已有记录按任务复用。报告中的阶段性数字对应本次快照，后续以 incremental_progress.json 的更新时间和数字为准。

## 未完成与判断边界

56 个案例仍待语义复核，尚无跨项目复现的已确认行为机制。变异体源码级因果检查、TSB 行为案例、多个问题共现关系和语义标签与分数关联尚待完成。当前不具备分类饱和证据，研究问题保留待验证状态。依赖、语法、fixture 等执行问题单列为工程因素。
