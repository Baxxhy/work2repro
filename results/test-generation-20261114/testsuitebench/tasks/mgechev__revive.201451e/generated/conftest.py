import json
import os
import subprocess
from pathlib import Path

import pytest


EVALUATION_DIR = Path(__file__).resolve().parent
EXECUTABLE = Path(os.environ.get("EXECUTABLE", "/workspace/executable")).resolve()


@pytest.fixture
def invoke(tmp_path):
    def run(*args, cwd=None, env=None, timeout=8):
        work = Path(cwd) if cwd is not None else tmp_path
        work.mkdir(parents=True, exist_ok=True)
        child_env = os.environ.copy()
        child_env.pop("REVIVE_FORCE_COLOR", None)
        if env:
            child_env.update({str(k): str(v) for k, v in env.items()})
        return subprocess.run(
            [str(EXECUTABLE), *map(str, args)], cwd=work, env=child_env,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout,
        )
    return run


def write_go(directory, name, text):
    path = Path(directory) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def config(directory, content):
    path = Path(directory) / "revive-test.toml"
    path.write_text(content, encoding="utf-8")
    return path


def json_findings(result):
    assert result.stderr == b""
    return json.loads(result.stdout.decode("utf-8"))
