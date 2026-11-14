import os
import subprocess
from pathlib import Path

import pytest

EVALUATOR = Path('/workspace/executable')

@pytest.fixture
def exe():
    return str(EVALUATOR)

@pytest.fixture
def run():
    def invoke(args, *, input_bytes=None, env=None, cwd=None, timeout=8):
        merged = os.environ.copy()
        if env:
            merged.update(env)
        return subprocess.run([str(EVALUATOR), *map(str, args)], input=input_bytes,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              env=merged, cwd=cwd, timeout=timeout)
    return invoke

@pytest.fixture
def raw16(tmp_path):
    def make(name, samples, rate=8000, channels=1):
        import struct
        p = tmp_path / name
        p.write_bytes(struct.pack('<' + 'h' * len(samples), *samples))
        return p
    return make

@pytest.fixture
def make_wav(tmp_path):
    def make(name, samples, rate=8000, channels=1, width=2):
        import wave
        import struct
        p = tmp_path / name
        with wave.open(str(p), 'wb') as w:
            w.setnchannels(channels); w.setsampwidth(width); w.setframerate(rate)
            fmt = {1:'b', 2:'h', 4:'i'}[width]
            w.writeframes(struct.pack('<' + fmt*len(samples), *samples))
        return p
    return make
