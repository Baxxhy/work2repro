import os
import pathlib
import subprocess
import tempfile

import pytest


EVAL_DIR = pathlib.Path(__file__).resolve().parent
EXECUTABLE = pathlib.Path(os.environ.get("MDBOOK_EXECUTABLE", "/workspace/executable"))


@pytest.fixture
def tmp_path():
    # Keep all generated files beneath eval as required by the harness.
    base = EVAL_DIR / ".tmp"
    base.mkdir(exist_ok=True)
    path = pathlib.Path(tempfile.mkdtemp(prefix="case-", dir=base))
    yield path


def make_book(root, summary="- [Chapter 1](chapter_1.md)\n", chapters=None, config=None):
    root = pathlib.Path(root)
    (root / "src").mkdir(parents=True, exist_ok=True)
    (root / "src" / "SUMMARY.md").write_text(summary, encoding="utf-8")
    for name, content in (chapters or {"chapter_1.md": "# Chapter 1\n\nHello world.\n"}).items():
        path = root / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if config is not None:
        (root / "book.toml").write_text(config, encoding="utf-8")
    return root


def run_mdbook(*args, cwd=None, env=None, input_text=None, timeout=30):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [str(EXECUTABLE), *map(str, args)], cwd=cwd, env=merged,
        input=input_text, text=True, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, timeout=timeout,
    )

