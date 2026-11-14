import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def exe():
    return Path(os.environ.get("EXECUTABLE", "/workspace/executable"))


def invoke(exe, *args, html=None, cwd=None):
    return subprocess.run(
        [str(exe), *map(str, args)], input=None if html is None else html.encode("utf-8"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, timeout=20,
    )


@pytest.fixture
def run(exe):
    return lambda *args, html=None, cwd=None: invoke(exe, *args, html=html, cwd=cwd)
