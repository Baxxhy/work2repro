import os
import subprocess
from pathlib import Path

import pytest


EXECUTABLE = Path("/workspace/executable")


@pytest.fixture
def invoke(tmp_path):
    """Run atlas in an isolated cwd/home so stateful notices are deterministic."""
    def run(*args, cwd=None, env=None, stdin=None):
        work = Path(cwd) if cwd is not None else tmp_path
        home = work / "home"
        home.mkdir(parents=True, exist_ok=True)
        child_env = os.environ.copy()
        child_env.update({"HOME": str(home), "ATLAS_NO_UPDATE_NOTIFIER": "1"})
        if env:
            child_env.update({str(k): str(v) for k, v in env.items()})
        return subprocess.run(
            [str(EXECUTABLE), *map(str, args)], cwd=work, env=child_env,
            input=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=30,
        )
    return run


def write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content.encode("utf-8") if isinstance(content, str) else content)
    return path

