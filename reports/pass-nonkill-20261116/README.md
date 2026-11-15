# Req2Test 固定24条专项分析

快照日期为2026-11-16，锁定harness提交为c0d7138f408bb7935d2c82e0fed82884f519b199。

## 交付文件

- [24条逐任务需求、代码、参考与存活证据](PASS_NONKILL_CASE_ANALYSIS.md)
- [10条KillComplete对照](KILL_COMPLETE_CONTROL_ANALYSIS.md)
- [机制分类数据库](FAILURE_MECHANISM_DATABASE.csv)
- [跨项目发现与反例](CROSS_PROJECT_FINDINGS.md)
- [研究问题更新](RESEARCH_PROBLEM_UPDATE.md)

## 来源与验证

分析对象来自publication/work2repro的test-generation-20261114发布快照。参考代码和gold kill标签取自现有官方kit；候选执行和变异结果取自req2test-recovery8-20261113-v1对应项目目录。每条任务的metrics.json记录原始生成路径，execution.json保留执行尾日志、逐步骤结果和produced_files。

任务JSON的benchmark_version、执行JSON的dataset_version和各kit版本分别保留源值，不将不同字段的版本字符串视为同一概念。

验证覆盖34个唯一任务、833个存活变异对、787个成功对照变异对。发布生成文件SHA256同时匹配提取文件和执行记录produced_files，发布逐任务指标摘要也匹配。之前7份问题发现报告的摘要保存于protected-report-hashes.json，专项目录外的内容只读。

Kapua两条任务的record_count_anomaly=true和record_count=2保留在原始执行记录中。它们的最终步骤均passed，变异记录按(instance_id,mutant_id)核对唯一。该标记未被清除，若后续需要解释多记录来源，应检查既有harness日志。

来源报告包含官方排除、timeout/drop/crash计分口径。本轮case分类是人工语义判断，脚本只做提取、关联、计数与渲染。逐变异参考堆栈未提取，代码路径解释未经新干预复验。

## 离线复查

```bash
cd /root/Baxxhy/work2/diagnostics/pass-nonkill-20261116
python3 prepare.py
python3 annotate.py
python3 build_reports.py
python3 verify.py
```

上述命令读取固定证据，重新渲染本专项派生报告，不调用模型或评测器。extract.py、gold.py、source_context.py和control_mutants.py是从实验服务器读取现有证据的提取工具；再次使用应保留当前证据快照。

案例缓存位于evidence/<artifact_id>/analysis.json。全量评测仍属于此前已启动的独立工作，本阶段分析新增生成及评测调用均为0。
