import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


@pytest.fixture
def project(tmp_path):
    return tmp_path


def invoke(args=(), *, cwd=None, input=None, env=None, timeout=15):
    merged = os.environ.copy()
    merged.update({'NO_COLOR': '1', 'RUMDL_COLOR': 'never'})
    if env:
        merged.update(env)
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, input=input,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=merged, timeout=timeout)


@pytest.fixture
def run():
    return invoke
