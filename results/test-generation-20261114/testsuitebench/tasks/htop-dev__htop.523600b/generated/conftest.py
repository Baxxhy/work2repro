import os
import subprocess
from pathlib import Path

import pytest


EXECUTABLE = Path(__file__).resolve().parent.parent / "executable"


@pytest.fixture
def invoke():
    def _invoke(*args, env=None, timeout=8):
        child_env = os.environ.copy()
        child_env.setdefault("TERM", "xterm")
        if env:
            child_env.update({str(k): str(v) for k, v in env.items()})
        return subprocess.run(
            [str(EXECUTABLE), *map(str, args)], stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, env=child_env, timeout=timeout,
        )
    return _invoke


@pytest.fixture
def plain():
    """Remove terminal escapes for assertions about visible text."""
    import re
    def _plain(data):
        text = data.decode("utf-8", "replace")
        return re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    return _plain
