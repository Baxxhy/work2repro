#!/usr/bin/env python3
"""Bounded official app-server model access probe. Never prints credentials."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time


def main():
    work = Path('/tmp/mumu-luna-probe')
    work.mkdir(mode=0o700, exist_ok=True)
    disabled = ['shell_tool', 'apps', 'plugins', 'multi_agent', 'code_mode',
                'code_mode_host', 'view_image', 'image_generation', 'browser_use',
                'computer_use', 'skill_search', 'hooks', 'sleep_tool', 'goals']
    cmd = ['codex', 'app-server', '--listen', 'stdio://', '-c', 'web_search="disabled"',
           '-c', 'project_doc_max_bytes=0', '-c', 'mcp_servers={}',
           '-c', 'features.skip_host_skill_discovery=true']
    for flag in disabled:
        cmd += ['--disable', flag]
    log_path = work / 'server.stderr.log'
    q = queue.Queue()
    result = {'model': 'gpt-6-luna', 'started_at': time.time(), 'route': 'codex-app-server-text-adapter'}
    with log_path.open('w') as err:
        p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=err,
                             text=True, bufsize=1, cwd=work)
        def read():
            for line in p.stdout:
                try:
                    q.put(json.loads(line))
                except json.JSONDecodeError:
                    q.put({'parse_error': True})
            q.put({'eof': True})
        threading.Thread(target=read, daemon=True).start()
        def send(method, params, id=None):
            row = {'method': method, 'params': params}
            if id is not None:
                row['id'] = id
            p.stdin.write(json.dumps(row) + '\n')
            p.stdin.flush()
        def response(id, timeout=30):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                row = q.get(timeout=max(.1, deadline-time.monotonic()))
                if row.get('id') == id:
                    if 'error' in row:
                        raise RuntimeError(json.dumps(row['error']))
                    return row['result']
                if row.get('eof'):
                    raise RuntimeError('app-server exited')
                if 'id' in row and 'method' in row:
                    p.stdin.write(json.dumps({'id': row['id'], 'error': {'code': -32601, 'message': 'Probe does not execute tools or approvals'}})+'\n')
                    p.stdin.flush()
            raise TimeoutError('RPC response timeout')
        try:
            send('initialize', {'clientInfo': {'name': 'mumu_luna_probe', 'title': 'MuMuTestUp Luna access probe', 'version': '1.0'}, 'capabilities': {'experimentalApi': True}}, 1)
            result['initialize'] = response(1)
            send('initialized', {})
            send('model/list', {'includeHidden': True, 'limit': 100}, 2)
            models = response(2)
            result['matching_models'] = [x for x in models.get('data', []) if 'luna' in x.get('model', '')]
            send('account/read', {'refreshToken': False}, 3)
            account = response(3)
            result['auth'] = {k: account.get('account', {}).get(k) for k in ('type', 'planType')}
            send('thread/start', {'model': 'gpt-6-luna', 'modelProvider': 'openai',
                 'approvalPolicy': 'never', 'sandbox': 'read-only', 'cwd': str(work),
                 'ephemeral': True, 'environments': [], 'dynamicTools': [],
                 'serviceTier': 'default', 'allowProviderModelFallback': False,
                 'baseInstructions': 'Return only the requested text. You have no tools and must not access files or external sources.',
                 'developerInstructions': ''}, 4)
            thread = response(4)
            tid = thread['thread']['id']
            result['thread_model'] = thread.get('model')
            result['thread_id'] = tid
            send('turn/start', {'threadId': tid, 'model': 'gpt-6-luna', 'effort': 'medium',
                 'environments': [], 'input': [{'type': 'text', 'text': 'Reply with exactly LUNA_OK.'}]}, 5)
            response(5)
            messages = []
            types = []
            deadline = time.monotonic() + 120
            while time.monotonic() < deadline:
                row = q.get(timeout=max(.1, deadline-time.monotonic()))
                method = row.get('method', '')
                params = row.get('params', {})
                if method == 'item/completed':
                    item = params.get('item', {})
                    types.append(item.get('type'))
                    if item.get('type') == 'agentMessage':
                        messages.append(item.get('text', ''))
                    if item.get('type') in ('commandExecution', 'mcpToolCall', 'dynamicToolCall', 'fileChange', 'webSearch'):
                        raise RuntimeError('Unexpected tool use: ' + item['type'])
                elif method == 'thread/tokenUsage/updated':
                    result['usage'] = params.get('tokenUsage')
                elif method == 'turn/completed':
                    result['turn'] = params.get('turn')
                    break
                elif method == 'error':
                    result.setdefault('events_errors', []).append(params.get('error', {}))
                elif row.get('eof'):
                    raise RuntimeError('app-server exited during inference')
            else:
                raise TimeoutError('Inference deadline exceeded')
            result['item_types'] = types
            result['text'] = '\n'.join(messages)
            result['ok'] = result.get('turn', {}).get('status') == 'completed' and result['text'].strip() == 'LUNA_OK' and result['thread_model'] == 'gpt-6-luna'
        except Exception as exc:
            result.update(ok=False, error=str(exc))
        finally:
            p.terminate()
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait()
    result['elapsed_seconds'] = round(time.time() - result['started_at'], 3)
    (work / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    # Account email, tokens, and server diagnostics are deliberately excluded.
    print(json.dumps({k: result.get(k) for k in ('ok', 'model', 'thread_model', 'auth', 'text', 'usage', 'error', 'elapsed_seconds', 'events_errors')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
