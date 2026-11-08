#!/usr/bin/env python3
"""Two small real requests validate the text adapter before experiment samples."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import time
import urllib.error
import urllib.request


def main():
    output = Path(os.environ['MUMU_LUNA_OUTPUT']) / 'bridge-warmup.json'
    base = os.environ['MUMU_LUNA_BRIDGE_URL'].rstrip('/')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    deadline = time.monotonic() + 45
    while True:
        try:
            with opener.open(base.removesuffix('/v1') + '/health', timeout=3) as response:
                health = json.load(response)
            if not health.get('ok'):
                raise RuntimeError(health)
            break
        except (urllib.error.URLError, TimeoutError):
            if time.monotonic() > deadline:
                raise
            time.sleep(1)

    def request(kind):
        payload = {'model': 'gpt-6-luna', 'messages': [
            {'role': 'system', 'content': 'Return only the text requested by the user.'},
            {'role': 'user', 'content': 'Reply with exactly LUNA_OK.' if kind == 'text'
             else 'Return exactly this JSON object: {"ok":true,"model":"gpt-6-luna"}'}]}
        if kind == 'json':
            payload['response_format'] = {'type': 'json_object'}
        req = urllib.request.Request(base + '/chat/completions',
                                     data=json.dumps(payload).encode(),
                                     headers={'Content-Type': 'application/json'})
        start = time.monotonic()
        try:
            with opener.open(req, timeout=660) as response:
                data = json.load(response)
            content = data['choices'][0]['message']['content']
            valid = content.strip() == 'LUNA_OK' if kind == 'text' else json.loads(content) == {'ok': True, 'model': 'gpt-6-luna'}
            valid = valid and data['model'] == 'gpt-6-luna'
            record = {'kind': kind, 'ok': valid, 'seconds': round(time.monotonic() - start, 3), 'response': data}
        except Exception as exc:
            message = exc.read().decode() if isinstance(exc, urllib.error.HTTPError) else str(exc)
            record = {'kind': kind, 'ok': False, 'seconds': round(time.monotonic() - start, 3), 'error': message}
        print(json.dumps(record), flush=True)
        return record

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(request, ['text', 'json']))
    output.write_text(json.dumps({'ok': all(r['ok'] for r in results), 'results': results}, indent=2) + '\n')
    if not all(r['ok'] for r in results):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
