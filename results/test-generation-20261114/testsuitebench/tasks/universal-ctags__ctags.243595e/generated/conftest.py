import os, subprocess
from pathlib import Path
import pytest

EXE = Path('/workspace/executable')

@pytest.fixture

def invoke(tmp_path):
    def run(*args, input=None, cwd=None):
        return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or tmp_path,
            input=input, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return run


def records(out):
    return [line.split('\t') for line in out.splitlines() if line and not line.startswith('!_TAG_')]
