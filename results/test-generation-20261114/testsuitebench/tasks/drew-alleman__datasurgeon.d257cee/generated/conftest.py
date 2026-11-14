import os
import subprocess
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = EVAL.parent / "executable"


@pytest.fixture
def envdir(tmp_path):
    home = tmp_path / "home"
    (home / ".DataSurgeon").mkdir(parents=True)
    (home / ".DataSurgeon" / "plugins.json").write_text("[]", encoding="utf-8")
    return home


def invoke(args=(), *, data=None, cwd=None, home=None):
    env = os.environ.copy()
    if home is not None:
        env["HOME"] = str(home)
    return subprocess.run([str(EXE), *map(str, args)], input=data, cwd=cwd or EVAL,
                          env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=10)


@pytest.fixture
def run(envdir):
    def _run(args=(), data=None, cwd=None):
        return invoke(args, data=data, cwd=cwd, home=envdir)
    return _run
