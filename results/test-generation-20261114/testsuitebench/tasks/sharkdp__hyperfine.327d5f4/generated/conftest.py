import os
import subprocess
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')

@pytest.fixture
def invoke():
    def run(*args, timeout=45, cwd=None):
        return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL_DIR,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout)
    return run

@pytest.fixture
def workdir(tmp_path):
    return tmp_path
