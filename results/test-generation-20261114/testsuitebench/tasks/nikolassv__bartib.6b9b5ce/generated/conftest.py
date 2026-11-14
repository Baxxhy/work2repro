import os
import subprocess
from pathlib import Path

import pytest


EVAL_DIR = Path(__file__).resolve().parent
EXE = Path(os.environ.get("EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def invoke(tmp_path):
    """Run executable with an isolated log and return process plus log path."""
    log = tmp_path / "activity log.txt"

    def run(*args, content=None, env=None, path=log, cwd=None):
        if content is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        child_env = os.environ.copy()
        child_env.pop("BARTIB_FILE", None)
        child_env.pop("EDITOR", None)
        child_env.update({"BARTIB_FILE": str(path)})
        if env:
            for key, value in env.items():
                if value is None:
                    child_env.pop(key, None)
                else:
                    child_env[key] = str(value)
        p = subprocess.run([str(EXE), *map(str, args)], cwd=cwd or tmp_path,
                           env=child_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p, path
    return run


def text(data):
    return data.decode("utf-8", "replace")


def plain(data):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text(data)).replace("\u00a0", " ")
