import json
import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture
def server():
    port = free_port()
    env = os.environ.copy()
    env['RUST_LOG'] = 'info'
    p = subprocess.Popen([str(BIN), 'server', '--listen', f'127.0.0.1:{port}'],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    try:
        deadline = time.time() + 5
        output = b''
        while time.time() < deadline:
            if p.poll() is not None:
                raise AssertionError(f'server exited: {p.stdout.read()!r} {p.stderr.read()!r}')
            import select
            ready, _, _ = select.select([p.stdout], [], [], .1)
            if ready:
                output += os.read(p.stdout.fileno(), 4096)
                if b'listening on' in output:
                    break
        assert b'listening on' in output, f'server did not announce startup: {output!r}'
        yield port, p
    finally:
        p.terminate()
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            p.kill(); p.wait(timeout=3)
        assert b'panic' not in p.stderr.read().lower()


def invoke(*args, timeout=8):
    env = os.environ.copy()
    env.pop('RUST_LOG', None)
    return subprocess.run([str(BIN), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, timeout=timeout)


def test_client_transfer_reports_metrics(server):
    port, _ = server
    p = invoke('client', f'127.0.0.1:{port}', '--duration=1', '--interval=1',
               '--download-size=4k', '--upload-size=2k')
    out = p.stdout.decode(errors='replace')
    assert p.returncode == 0 and p.stderr == b''
    assert 'Overall stats:' in out and 'RPS:' in out and 'Stream metrics:' in out
    assert 'Upload Throughput' in out and 'Download Throughput' in out
    assert 'Mb/s' in out


def test_json_file_has_report_interval_schema(server, tmp_path):
    port, _ = server
    path = tmp_path / 'stats.json'
    p = invoke('client', f'127.0.0.1:{port}', '--duration=1', '--interval=1',
               '--download-size=1k', '--upload-size=1k', '--json', str(path))
    assert p.returncode == 0 and p.stderr == b''
    assert path.exists() and not any(line.startswith('{') for line in p.stdout.decode().splitlines())
    data = json.loads(path.read_text())
    assert set(data) == {'start', 'intervals'}
    assert set(data['start']) == {'timestamp'} and data['start']['timestamp']['timesecs'] > 0
    assert len(data['intervals']) >= 1
    for interval in data['intervals']:
        assert set(interval) == {'streams', 'sum'}
        sm = interval['sum']
        assert set(sm) == {'start', 'end', 'seconds', 'bytes', 'bits_per_second', 'sender'}
        for stream in interval['streams']:
            assert set(stream) == {'id', 'start', 'end', 'seconds', 'bytes', 'bits_per_second', 'sender'}
            assert stream['seconds'] > 0 and stream['end'] >= stream['start']
            assert abs(stream['bits_per_second'] - stream['bytes'] * 8 / stream['seconds']) <= max(1, stream['bits_per_second'] * .001)


def test_operational_dns_error_is_logged_to_stdout():
    p = invoke('client', 'this-host-name-should-not-exist.invalid:4433', '--duration=1')
    assert p.returncode == 0 and p.stderr == b''
    assert 'resolving host:' in p.stdout.decode(errors='replace')


def test_zero_body_workload_is_reported_as_zero_requests(server):
    port, _ = server
    p = invoke('client', f'127.0.0.1:{port}', '--duration=1', '--interval=1',
               '--download-size=0', '--upload-size=0')
    assert p.returncode == 0
    assert 'RPS: 0.00 (0 requests in 1.00s)' in p.stdout.decode(errors='replace')

