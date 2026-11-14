"""Transport/model adapter around the locked official Req2Test generator.

The official prompt, view, collection, 200-call stop, timeout and scoring are
unchanged. Credentials stay in the root-owned gateway, outside the sandbox.
"""
import os
from req2test.inference import run_agent as official

official.CODEX_PROVIDERS['baseline'] = ('OpenAI ChatGPT', os.environ['BASELINE_GATEWAY_URL'],
                                      'BASELINE_GATEWAY_KEY', 'gpt-6-luna')
original = official.codex
def command(model):
    args = original(model)
    args = ['model_reasoning_effort=medium' if x == 'model_reasoning_effort=high' else x for x in args]
    args.insert(-1, '--json')
    return args
official.codex = command
raise SystemExit(official.main())
