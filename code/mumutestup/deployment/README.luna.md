# GPT-6 Luna 小批量配置

2026-11-04 已在 4x3090 完成 20 条独立样本：19 条返回的测试实际通过，6 条达到 MuMuTestUp 指标。MockServer 因环境与报告读取问题补跑，原始记录保留。

逐条结果在 `runs/luna20-20261104/summary.md`，运行限制和补跑原因在同目录 `run-notes.md`。本轮是 Codex 文本适配版小批量验证。

| 项目 | 配置 |
|---|---|
| 模型 | `gpt-6-luna`，medium，Standard |
| 调用方式 | `codex-app-server-text-adapter`，本机 `127.0.0.1:8012/v1` |
| 认证 | 由桥接进程管理 ChatGPT 登录；实验进程只持有本机接口的占位 key |
| 方法 | 保留 MuMuTestUp 原有各代理提示、最多四轮、编译运行、JaCoCo、PIT 和语义检索 |
| 样本 | 10 个项目各取前 2 条；MockServer 仅有 1 条，补入 Druid 的 index 2，合计 20 条；最多 2 个 worker |
| 嵌入 | 本机 CPU `all-MiniLM-L6-v2`，端口 8001 |
| 新源码 | `upstream-luna`，从已有 `upstream` 复制后单独适配 |
| 新结果 | 默认 `runs/luna20-20261104`，可用 `MUMU_LUNA_OUTPUT` 指定另一个新目录 |

桥接使用 Codex app-server，每次请求创建新 thread，禁止外部工具，传入 MuMuTestUp 原提示。这是 Codex 的文本适配方式，仍包含 Codex 框架的影响。记录中的 `native_model_api` 为 `false`，`temperature` 为 `null`。

## 准备与启动

在普通 SSH 环境中启动桥接，让它沿用 Codex 已可用的登录和网络配置；桥接不读取 MuMu 的接口环境。随后完成真实请求验证和预检：

```bash
export MUMU_LUNA_OUTPUT=/root/Baxxhy/work2/reproductions/mumutestup/runs/luna20-20261104
bash /root/Baxxhy/work2/reproductions/mumutestup/deployment/start_luna_bridge.sh
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime-luna.sh
python /root/Baxxhy/work2/reproductions/mumutestup/deployment/warm_luna_bridge.py
bash /root/Baxxhy/work2/reproductions/mumutestup/deployment/start_luna_small.sh --preflight-only
bash /root/Baxxhy/work2/reproductions/mumutestup/deployment/start_luna_small.sh
```

预检只检查服务存活、配置和环境，不会声称模型调用成功。`status.json` 已存在时入口拒绝再次使用该结果目录。重新试验须指定新目录；不使用 `--resume`。

当前入口每个项目使用新 Python 进程，防止日志与执行包装残留到下一个项目；Maven 使用已验证的本机 7890 代理。Surefire 默认验证 XML，项目禁用 XML 时，仅接受带精确单方法选择参数的新鲜单测试文本报告。

`patch_luna_backend.py` 先在临时目录准备源码，通过语法检查后才建立 `upstream-luna`。它保留 Java、运行路径、检索 ID 对接等既有修正，并同时移除主代理和检索代理中的 Qwen 参数。原始 `upstream`、数据和旧结果均不修改。旧依赖下载缓存可复用，新生成代码、结果、执行报告和检索索引重新产生。

## 桥接接口约定

- `GET /health` 返回 HTTP 200。此项只证明本机服务存活。
- `POST /v1/chat/completions` 接收 `model`、`messages`，以及可选 `response_format`。模型固定为 `gpt-6-luna`，返回标准 `choices[0].message.content`。
- `MUMU_LLM_FATAL_FILE` 默认指向 `$MUMU_LUNA_OUTPUT/bridge-fatal.json`。桥接遇到认证失败、套餐额度耗尽或不可恢复的接口错误，应先原子写入这个 JSON，再返回错误。文件只包含错误类别、时间和脱敏说明，不保存凭据。
- 主流程和检索调用都会检查该文件，停止继续请求。当前未完成样本记录为 `interrupted / backend_unavailable`，未开始样本不生成虚假失败记录，批次标记为 `stopped_backend_error`。
- 模型异常会停止批次，保留错误记录。调用日志保存实际模型名、推理设置、token 用量、请求总耗时和调用次数。

这批按固定顺序取样，共 20 条，只用于检查新后端与框架能否一起工作。其结果不能代表完整 571 条数据的效果。当前保留作者“新版本测试类中更新指定方法”的执行协议。
