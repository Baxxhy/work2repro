import os
import subprocess
from pathlib import Path

import pytest


EVAL_DIR = Path(__file__).resolve().parent
EXECUTABLE = Path(os.environ.get("PLS_EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def invoke(tmp_path):
    def run(*args, cwd=None, env=None):
        work = Path(cwd) if cwd is not None else tmp_path
        work.mkdir(parents=True, exist_ok=True)
        merged = os.environ.copy()
        merged["HOME"] = str(tmp_path / "home")
        merged.pop("PLS_CONFIG", None)
        merged.pop("PLS_COLUMNS", None)
        merged.pop("COLUMNS", None)
        merged["TERM"] = "dumb"
        if env:
            merged.update({str(k): str(v) for k, v in env.items()})
        return subprocess.run([str(EXECUTABLE), *map(str, args)], cwd=work,
                              env=merged, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, check=False)
    return run


@pytest.fixture
def names():
    def create(directory, *entries):
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=True)
        for entry in entries:
            p = directory / entry
            if entry.endswith("/"):
                p.mkdir(exist_ok=True)
            else:
                p.write_text("x", encoding="utf-8")
    return create
