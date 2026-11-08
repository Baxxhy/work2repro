import json, os, pathlib, shutil, signal, time
root=pathlib.Path('/root/Baxxhy/work2')
old=['reproductions/testexplora-sweagent','benchmarks/testexplora','datasets/TestExplora','datasets/TestExplora_真实数据阅读包.zip','activate-testexplora.sh','inference/vllm/serve-qwen35-sweagent.sh','inference/vllm/serve-qwen35-random300.sh','inference/vllm/active-goal-state.json']
# Stop only executables or Python entrypoints owned by the old experiment, not arbitrary matching shells.
stopped=[]
for p in pathlib.Path('/proc').iterdir():
    if not p.name.isdigit(): continue
    try:
        args=(p/'cmdline').read_bytes().split(b'\0'); args=[a.decode(errors='replace') for a in args if a]
        exe=(p/'exe').resolve(); owned=any(a.startswith(str(root/'reproductions/testexplora-sweagent')+'/') for a in args[:2])
        if owned and int(p.name)!=os.getpid():
            os.kill(int(p.name),signal.SIGTERM); stopped.append(int(p.name))
    except (OSError,ProcessLookupError):pass
if stopped: time.sleep(3)
for pid in stopped:
    try: os.kill(pid,signal.SIGKILL)
    except ProcessLookupError:pass
records=[]
for rel in old:
    p=root/rel
    if p.is_symlink() or p.is_file(): p.unlink(); status='deleted'
    elif p.is_dir(): shutil.rmtree(p); status='deleted'
    else: status='absent'
    records.append({'path':str(p),'status':status,'exists_after':p.exists()})
(root/'AGENTS.md').write_text('# Docker 存储\n\nDocker 持久数据继续使用 `/root/lby-docker` 下的已有服务 `unix:///run/mutate-docker.sock`。禁止影响其他项目。\n\n# 当前任务\n\n2026-10-30 用户授权删除旧 TestExplora 主动缺陷发现任务，转为 MuMuTestUp / PRBench，使用 Qwen3.5-27B。原 random300 约束已随旧任务撤销。\n')
(root/'README.md').write_text('# MuMuTestUp on 4x3090\n\n当前工作目录：`reproductions/mumutestup`。共用模型：`/root/Baxxhy/model/Qwen3.5-27B`；共用推理环境：`inference/vllm`。\n旧 TestExplora 实验已按用户要求删除；清理明细在 `reproductions/mumutestup/cleanup-remote.json`。\n')
report={'timestamp':time.time(),'stopped_pids':stopped,'paths':records,'model_preserved':(root.parent/'model/Qwen3.5-27B/config.json').is_file(),'inference_preserved':(root/'inference/vllm/.venv/bin/python').exists()}
(root/'reproductions/mumutestup/cleanup-remote.json').write_text(json.dumps(report,indent=2,ensure_ascii=False))
print(json.dumps(report,ensure_ascii=False))
