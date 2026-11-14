import os
from pathlib import Path

import pytest


@pytest.fixture
def executable():
    # run.sh changes cwd to eval; resolve the target independently of cwd.
    candidate = Path('/workspace/executable')
    if candidate.exists():
        return str(candidate)
    return str((Path(__file__).resolve().parent.parent / 'executable').resolve())


@pytest.fixture
def run_prog(executable):
    import subprocess

    def run(*args, cwd=None, env=None, timeout=5):
        proc_env = os.environ.copy()
        proc_env.update({'TERM': 'dumb', 'LANG': 'C.UTF-8'})
        if env:
            for k, v in env.items():
                if v is None:
                    proc_env.pop(k, None)
                else:
                    proc_env[k] = str(v)
        return subprocess.run([executable, *map(str, args)], cwd=cwd,
                              env=proc_env, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    return run
