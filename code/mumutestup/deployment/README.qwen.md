# MuMuTestUp 的 Qwen3.5-27B 服务

目标主机为 `4x3090`，模型复用 `/root/Baxxhy/model/Qwen3.5-27B` 的完整 BF16 权重。推理 Python 环境位于 `/root/Baxxhy/work2/inference/vllm`，与 MuMuTestUp 的 Java/Python 环境分开。

## 配置

- API：`http://127.0.0.1:8000/v1/chat/completions`
- 模型名称：`qwen3.5-27b`
- GPU：仅0、1；TP=2；BF16，不量化。每张GPU卸载约10 GiB权重到CPU内存，以容纳完整27B模型。
- GPU 2、3释放供其他工作使用；硬件切换前72条终态结果保留，7条中断任务续跑时重试。
- 最大上下文：32768 token，包含输入与输出。
- vLLM 最大并行序列数：8；显存比例：0.90。
- vLLM 0.32.0，eager 执行；使用已验证的 NCCL cuMem 兼容设置。
- 请求加入 `chat_template_kwargs: {"enable_thinking": false}`，使方法要求的代码/JSON输出直接进入 content。

这只是服务容量配置；不同长度任务的实际吞吐以运行记录为准，不能将短提示并发验证当成完整PRBench任务已经成功。

## 启动

先确认已有服务状态，避免重复加载。当前双卡服务PID记录在 `qwen-tp2-process.json`，服务日志为 `qwen35-server-tp2-20261030.log`。四卡旧记录作为历史证据保留。

```bash
bash /root/Baxxhy/work2/reproductions/mumutestup/deployment/serve-qwen35-mumutestup.sh --check
nohup bash /root/Baxxhy/work2/reproductions/mumutestup/deployment/serve-qwen35-mumutestup.sh \
  > /root/Baxxhy/work2/reproductions/mumutestup/logs/qwen35-server.log 2>&1 </dev/null &
echo $! > /root/Baxxhy/work2/reproductions/mumutestup/deployment/qwen35-server.pid
```

## 验证证据

`probe_qwen_concurrency.py` 检查健康接口、模型标识、真实Java测试接口改名请求、带中文解释的 `response_format=json_object`，以及16个并发真实请求。结果保存为 `qwen-concurrency-verification.json`。`--wait-ready` 会等待已有服务完成冷加载，不重启它。

```bash
python3 /root/Baxxhy/work2/reproductions/mumutestup/deployment/probe_qwen_concurrency.py --wait-ready
```

API检查的提示是明确构造的说明性例子，不是PRBench样本，也不代表MuMuTestUp方法或论文结果已复现。是否通过应读取实际JSON结果及本次服务日志，不能仅依据脚本存在判断。

## 2026-10-30 原四卡配置实测（历史证据）

完整模型首次冷加载成功，权重读取耗时1288.47秒，主要受磁盘I/O限制。健康接口及模型列表均返回HTTP200；实际Java代码输出、JSON对象及中文解释通过，16个并发请求全部成功，共18次生成请求通过。

短提示并发批次耗时3.54秒，生成240个token，合计67.80输出token/s。服务日志在批次内采样到15个运行请求、0个排队请求。这个结果只描述本次短提示API检查，不是长上下文吞吐上限或PRBench表现。

证据：`qwen-concurrency-verification.json`、`qwen35-server-20261030.log`（本地日志快照）；远程完整服务日志仍位于 `../logs/qwen35-server.log`。验证时API进程PID为2576668，该四卡服务已按用户要求停止。

## 双卡切换记录

用户要求只使用两张GPU。切换归档位于 `../runs/qwen27b-full/hardware-transitions/tp4-to-tp2-20261030/transition.json`，含72条已完成记录的SHA256和7条中断任务名单。恢复沿用原数据、方法和模型，仅变更推理硬件布局与服务并发；不承诺不同TP布局逐token完全相同。双卡验证记录单独写入 `qwen-tp2-verification.json`，不覆盖历史四卡报告。

```bash
QWEN_PROBE_CONCURRENCY=8 \
QWEN_PROBE_OUTPUT=/root/Baxxhy/work2/reproductions/mumutestup/deployment/qwen-tp2-verification.json \
python3 /root/Baxxhy/work2/reproductions/mumutestup/deployment/probe_qwen_concurrency.py --wait-ready
```

共享启动器端口预检查增加SO_REUSEADDR，避免旧服务退出后的TIME_WAIT状态被误报为活跃占用；原文件备份 `inference/vllm/scripts/launch.py.pre-tp2-restart`。

用户随后要求直接后台运行、不继续监控：额外双卡API/并发探测已停止，不能声称双卡并发验证已通过。后台入口PID2715665等待健康接口后，校验72条历史结果并直接exec原实验`--resume`；不设置持续监控。
