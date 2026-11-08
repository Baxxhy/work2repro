# TestUpdater：Updates4J 与 PRBench 全量实验

部署位置：4x3090 `/root/Baxxhy/work2/reproductions/testupdater`。

- 数据：作者当前公开 Updates4J **195 条／7 项目**；PRBench **571 条／10 项目**。合计 766 条。先前口头说成 245 条是加总错误，以逐条清单为准。
- 模型：GPT-6 Luna，medium、Standard；沿用服务器已登录账号。Codex 文本桥接模式，不是原生模型 API，temperature 不实际施加。TestUpdater 多轮消息按原顺序、原文本及角色标签转接成对话历史；这属于接口适配，不是原生多轮 API 复现。
- 并发：两套数据共用模型请求并发 **2**，项目进程最多 **10**；同项目串行。各项目使用独立副本，保留原 MuMuTestUp 结果。
- 方法：作者原 pipeline.py 的上下文收集、过滤、生成、两轮错误反馈修正及失败后的 basic-answer 步骤；不改提示。
- PRBench 适配：bCommit/bSource 为旧版本，aCommit/aSource 为新版本；提供 focal 方法前后代码和旧测试。保留 focal diff 为空的样本，不私自增加额外提示。
- 评测协议：沿用作者在新版本测试类中替换目标测试方法的协议；目标新测试仅用于替换位置及作者上下文查找。不是盲仓库测试定位任务。
- 执行检查：必须唯一替换目标方法，并产生新鲜的目标 Surefire 测试记录；Maven 返回成功但未执行目标测试，不能记通过。
- 环境适配：Java 8/11/17/21；Maven 3.9.9；tree-sitter 0.21.3 适配 Python 3.12；JDTLS 堆 2GB；构建并发每项目 1。作者原脚本的全局 `pkill language_servers` 已移除，改为自身上下文管理器关闭。
- 稳定性：桥接重连与请求重试，调用端指数退避；样本独立保存执行日志与状态，模型测试编译／断言失败与框架异常分开。
- 禁用 LangSmith 对外追踪。

## 文件

- `upstream/`：原始作者代码。
- `runtime/`（服务器）：配置后的执行副本。
- `datasets/updates4j`、`datasets/prbench`（服务器）：输入及适配结果。
- `data-verification.json`（服务器）：766 条目标commit、文件与唯一替换预检。
- `runs/smoke-20261105`（服务器）：两套数据各一条真实验证，不计入全量。
- `runs/luna-full-20261105`（服务器）：全量结果与独立模型审计。

该任务是运行作者方法在两套数据上的全量实验。当前作者主流水线按编译与执行反馈更新测试；与 MuMuTestUp 的覆盖/变异复合阈值不能直接当作同一个成功率。
