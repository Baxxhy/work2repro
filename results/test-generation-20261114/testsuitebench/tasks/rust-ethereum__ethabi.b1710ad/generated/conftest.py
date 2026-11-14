import json
import os
import subprocess
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parent
EXE = Path(os.environ.get("EXECUTABLE", "/workspace/executable"))

@pytest.fixture
def invoke():
    def run(*args):
        return subprocess.run([str(EXE), *map(str, args)], cwd=ROOT, text=True,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    return run

@pytest.fixture
def abi_file(tmp_path):
    def write(entries, name="abi.json"):
        p = tmp_path / name
        p.write_text(json.dumps(entries))
        return str(p)
    return write

@pytest.fixture
def wordhex():
    return lambda n: f"{n % (1 << 256):064x}"
