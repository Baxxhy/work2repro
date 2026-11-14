import os
import pathlib
import subprocess
import sys

import pytest


EVAL = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')
BOT = EVAL / 'fixture_bot.py'


@pytest.fixture
def game(tmp_path):
    def run(*args, cwd=None, timeout=40):
        env = os.environ.copy()
        env['PYTHONUNBUFFERED'] = '1'
        return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or tmp_path,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              timeout=timeout, env=env)
    return run


def command(mode='empty', label=None):
    cmd = f'{sys.executable} {BOT} {mode}'
    return cmd + (f' {label}' if label is not None else '')


@pytest.fixture
def botcmd():
    return command


@pytest.fixture
def eval_dir():
    return EVAL
