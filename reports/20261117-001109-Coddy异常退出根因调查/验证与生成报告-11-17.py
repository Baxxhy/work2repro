import pathlib,json,csv,datetime
p=pathlib.Path('/root/Baxxhy/work2/diagnostics/20261117-001109-Coddy异常退出根因调查')
d=json.loads((p/'底层执行与分类源码-11-17.json').read_text())
assert len(d['captures'])==5
assert 'ActiveState=inactive' in d['service'] and 'ExecMainStatus=0' in d['service']
final=[json.loads(l) for l in d['final_rows'].splitlines() if l];assert len(final)==5
assert all(x['outcome']=='passed_but_nonzero_exit' for x in final)
rows=[]
for c in d['captures']:
 m=c['mutant'];n=[json.loads(l) for l in c['native'].splitlines()];s=c['stdout'];assert c['returncode']==1
 assert n[-1]['event']=='exit' and n[-1]['code']==0
 statuses=[e for e in n if e['event']=='status'];assert statuses and all(e['status']=='passed' for e in statuses),statuses
 assert 'fatal error: sync:' in s and 'unlocked' in s and 'testing.(*common).runCleanup' in s
 mid=m['id'];(p/(mid+'-退出堆栈-11-17.txt')).write_text(s);(p/(mid+'-原生事件-11-17.jsonl')).write_text(c['native'])
 fatal=next(l for l in s.splitlines() if l.startswith('fatal error:'))
 rows.append({'变异体ID':mid,'源码':m['file'],'变异行':m['start_line'],'删除操作':m['original'],'原生步骤数':len(statuses),'原生退出码':n[-1]['code'],'Go退出码':c['returncode'],'根因':fatal,'阶段':'testing.Cleanup -> Server.Drain','官方分类':'passed_but_nonzero_exit'})
with (p/'逐变异体根因核对-11-17.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
(p/'根因调查结论-11-17.md').write_text('''# Coddy 测试通过但进程异常退出的根因

开始时间为北京时间 2026-11-17 00:11:09，归档时间为 '''+now+'''。

## 已确认的结果

5/5 对均已复现并取得完整 stdout、Go 堆栈和原生事件。全部来自同一任务 coddy-agent/features/subagents_http.feature:32。

每一对都是 Godog 场景步骤全部通过、原生结束码为 0，随后 Go 清理回调崩溃，外层 go test 返回 1。直接原因均为作者提供的 MethodCallRemoval 变异删除了 Lock()，保留了 Unlock()，触发 Go 的解锁未加锁互斥量错误。

|变异体|删除 Lock 的位置|清理中触发的位置|
|---|---|---|
|067d32a367e1f45f|codex_auth_http.go:40|cancelCodexAuthLogins，报错位置 47|
|53e3121a97c34639|neuraldeep_auth_http.go:51|cancelNeuralDeepAuthLogins，报错位置 58|
|a9b81946ed00195a|bgtask/pool.go:707|Pool.StopAll，报错位置 712|
|4e6505b87460587e|session/provider_usage.go:175|注销用量观察器回调，报错位置 177|
|275ee7bf98602829|session/turn_events.go:53|注销轮次观察器回调，报错位置 55|

## 一条完整执行链

候选测试在 start() 中注册 `b.t.Cleanup(srv.Drain)`。场景执行目录查询、检查内置与项目子代理、设置信任、再次查询并检查信任状态。随后 Godog 写出 `R2T_GODOG_EXIT TestSubagentsHTTPFeature 0`，原生事件也写出 exit=0。

Go 随后执行 testing.Cleanup 中的 Server.Drain，进入认证取消、观察器注销或后台任务停止。变异删除加锁却留下解锁，触发 fatal error。第一对实测堆栈为 `testing.runCleanup -> Server.Drain -> cancelCodexAuthLogins -> Mutex.Unlock`，直接报错 `fatal error: sync: unlock of unlocked mutex`。后台任务池一对对应 RWMutex，报错 `sync: Unlock of unlocked RWMutex`。

五对日志均有该顺序，执行中未触发 600 秒超时。

## 为什么官方继续排除

锁定源码 c0d7138f408bb7935d2c82e0fed82884f519b199 中，runtime._capture_attempt 会识别 Go fatal 堆栈，但使用 read_crash_prefix 确认崩溃时，要求原生事件没有 terminal exit。本例已有完整的 exit=0 事件，这条崩溃计分分支无法接纳。

之后执行器按完整原生记录读取到所有步骤 passed，外层退出码为 1。RunResult.outcome 因而生成 passed_but_nonzero_exit，官方变异规则将其排除。相关源码片段在底层执行与分类源码 JSON 中。

本轮证据明确了生产代码中的变异在清理阶段被触发并导致进程崩溃，既有官方分类仍为 dropped。本轮保留官方计分结果。当前证据只针对该任务的这五对，无法据此推断其余任务。

## 诊断配置与验证

本轮使用独立目录和 run-id req2test-coddy-exit-diagnosis-20261117-v1，workers=1，原生成文件与 600 秒候选预算沿用原配置。复用 160 条执行及 4,751 对有效变异记录，仅重放五对异常。官方参考测试首先通过。模型调用数为 0。

额外诊断脚本只在 capture_execution 返回后将已有结果写入独立目录，并原样返回对象。测试源码、官方仓库及分类逻辑沿用原件。首次诊断入口缺少 r2t 模块路径，补充官方 ENGINE_ROOT 路径后重新启动，失败过程保存在日志。诊断作业正常结束，退出码为 0。

逐对验证命令为 `python /tmp/finalize-coddy-root.py`。检查五个唯一变异 ID、五份所有步骤通过的原生记录、内层 exit=0、外层 exit=1、fatal 堆栈和 testing.runCleanup，以及官方五条最终分类，全部通过。验证脚本另存本目录。

## 证据入口

- 逐变异体根因核对 CSV 包含每对修改、状态与原因。
- 每个变异 ID 对应退出堆栈 TXT 与原生事件 JSONL。
- 五个变异体及代码证据 JSON 保存变异清单和生成测试、原生产代码片段。
- 底层执行与分类源码 JSON 保存原始捕获和官方分类源码。
- 准备、启动、采集脚本保留诊断操作，可核对复用范围。

旧结果保留，后续全量 2,051 队列超出本轮范围。
''')
print('PASS: 5 unique mutants, all native steps passed, native exit 0, Go exit 1, cleanup fatal, official dropped; service exit 0')
