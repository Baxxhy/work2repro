import os
from pathlib import Path
from req2test.inference import run_agent as runner

arm = os.environ['PAIRED_ARM']
runner.CODEX_PROVIDERS['baseline'] = ('OpenAI ChatGPT', os.environ['BASELINE_GATEWAY_URL'], 'BASELINE_GATEWAY_KEY', 'gpt-6-luna')
original = runner.codex
def command(model):
    args = original(model)
    if arm == 'a':
        args = ['model_reasoning_effort=medium' if arg == 'model_reasoning_effort=high' else arg for arg in args]
    args.insert(-1, '--json')
    return args

def without_pack(project, iid, workspace):
    ws = str(Path(workspace).resolve())
    return dict(workspace=ws, binds=[dict(source=ws, target=ws, writable=True)], home_links=[], path_prepend='/nonexistent-req2test-pack/bin')

if arm == 'b':
    os.environ['PATH']='/root/lby-docker/req2test/paper-cli-01534/package/vendor/x86_64-unknown-linux-musl/bin:'+os.environ['PATH']
    runner.packs.setup_attempt=without_pack
runner.codex=command
raise SystemExit(runner.main())
