import os
import subprocess
from pathlib import Path

import pytest


EVAL_DIR = Path(__file__).resolve().parent
EXECUTABLE = Path(os.environ.get("DUCKDB_EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def run(tmp_path):
    def invoke(*args, stdin=None, env=None, cwd=None, timeout=30):
        merged_env = os.environ.copy()
        if env:
            merged_env.update(env)
        return subprocess.run(
            [str(EXECUTABLE), *map(str, args)],
            input=stdin,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd or tmp_path,
            env=merged_env,
            timeout=timeout,
        )
    return invoke


def ok(result):
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)


def failed(result, phrase):
    assert result.returncode != 0, (result.stdout, result.stderr)
    assert phrase in result.stderr, (phrase, result.stderr)
