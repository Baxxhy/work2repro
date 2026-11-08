"""Read existing checkpoint files sequentially to warm the OS cache; no writes."""
import json
from pathlib import Path
import time

root = Path('/root/Baxxhy/model/Qwen3.5-27B')
buffer = bytearray(8 * 1024 * 1024)
started = time.monotonic()
for path in sorted(root.glob('*.safetensors')):
    size = 0
    with path.open('rb', buffering=0) as stream:
        while count := stream.readinto(buffer):
            size += count
    print(json.dumps({'file': path.name, 'bytes': size,
                      'elapsed': round(time.monotonic() - started, 1)}), flush=True)
