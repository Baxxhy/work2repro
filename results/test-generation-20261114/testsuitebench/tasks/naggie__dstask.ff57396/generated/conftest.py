import os
import subprocess
from pathlib import Path

import pytest


EVAL_DIR = Path(__file__).resolve().parent
EXE = Path(os.environ.get("DSTASK_EXE", EVAL_DIR.parent / "executable")).resolve()


@pytest.fixture
def app(tmp_path):
    repo = tmp_path / "repo space ü"
    home = tmp_path / "home"
    home.mkdir()
    env = os.environ.copy()
    env.pop("DSTASK_CONTEXT", None)
    env.pop("DSTASK_FAKE_PTY", None)
    env["HOME"] = str(home)
    env["DSTASK_GIT_REPO"] = str(repo)

    def run(*args, input=None, more_env=None, cwd=None):
        e = env.copy()
        if more_env:
            e.update({k: str(v) for k, v in more_env.items()})
        return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or tmp_path,
                              env=e, input=input, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=15)

    def git(*args):
        return subprocess.run(["git", "-C", str(repo), *args], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=True)

    return {"run": run, "git": git, "repo": repo, "tmp": tmp_path, "env": env}


def json_tasks(result):
    import json
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return json.loads(result.stdout)
