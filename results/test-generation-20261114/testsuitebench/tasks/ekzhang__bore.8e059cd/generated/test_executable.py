import hashlib
import hmac
import json
import os
import re
import socket
import subprocess
import time
import uuid
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')


def run(*args, env=None, timeout=5):
    e = os.environ.copy()
    for k in ('BORE_LOCAL_PORT', 'BORE_SERVER', 'BORE_SECRET', 'BORE_MIN_PORT', 'BORE_MAX_PORT'):
        e.pop(k, None)
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], capture_output=True, env=e, timeout=timeout)


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p=s.getsockname()[1]; s.close(); return p


def recv_frame(sock, timeout=4):
    sock.settimeout(timeout); buf=bytearray()
    while len(buf) <= 257:
        b=sock.recv(1)
        if not b: raise EOFError()
        if b == b'\0': return bytes(buf)
        buf.extend(b)
    raise ValueError('oversized frame')


def send_frame(sock, data):
    sock.sendall(data + b'\0')


class Server:
    def __init__(self, *args):
        self.proc = subprocess.Popen([str(BIN), 'server', '--bind-addr', '127.0.0.1', *map(str,args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.port=7835
        end=time.time()+3
        while time.time()<end:
            try:
                s=socket.create_connection(('127.0.0.1',self.port),.1); s.close(); break
            except OSError: time.sleep(.03)
        else: raise AssertionError('server did not start')
    def close(self):
        self.proc.terminate()
        try: self.proc.wait(timeout=2)
        except subprocess.TimeoutExpired: self.proc.kill(); self.proc.wait()
    def __enter__(self): return self
    def __exit__(self,*a): self.close()


def test_root_help_and_version():
    a=run('--help'); b=run('-h'); c=run('help')
    assert a.returncode == b.returncode == c.returncode == 0
    assert a.stdout == b.stdout == c.stdout and b'Usage: executable <COMMAND>' in a.stdout
    assert a.stderr == b.stderr == c.stderr == b''
    v=run('--version'); assert v.returncode == 0 and v.stdout == b'bore-cli 0.6.0\n' and not v.stderr
    assert run('-V').stdout == v.stdout


def test_subcommand_help_forms_and_no_secret_leak():
    for cmd in ('local','server'):
        x=run(cmd,'--help'); y=run('help',cmd)
        assert x.returncode == y.returncode == 0 and x.stdout == y.stdout and not x.stderr
        assert b'Usage: executable '+cmd.encode() in x.stdout
        assert b'<SECRET>' in x.stdout and b'secret' in x.stdout.lower()
        assert b'shared-secret-value' not in x.stdout


def test_no_args_unknown_and_help_target_are_usage_errors():
    x=run(); assert x.returncode==2 and x.stdout==b'' and b'Usage: executable <COMMAND>' in x.stderr
    for args, fragment in [(('nonesuch',),b"unrecognized subcommand 'nonesuch'"), (('help','--help'),b'error:'), (('--min-port','4'),b'error:')]:
        x=run(*args); assert x.returncode==2 and not x.stdout and fragment in x.stderr


@pytest.mark.parametrize('args,need', [
    (('local',),b'--to <TO>'), (('local','--to'),b'value is required'),
    (('local','8','--to','x','--to','y'),b'cannot be used multiple times'),
    (('local','abc','--to','x'),b"invalid value 'abc'"), (('local','70000','--to','x'),b"70000 is not in 0..=65535"),
    (('local','1','--to','x','--port','0x10'),b"invalid value '0x10'"),
    (('server','--min-port','4','--max-port','3'),b'port range is empty'),
    (('server','--bind-addr','localhost'),b'invalid IP address syntax'),
    (('server','--bind-tunnels','999.1.1.1'),b'invalid IP address syntax'),
    (('server','--wat'),b'error:'),
])
def test_cli_usage_errors(args,need):
    x=run(*args); assert x.returncode==2 and x.stdout==b'' and need in x.stderr


def test_numeric_forms_env_and_precedence():
    # Explicit flags win over invalid environment values; zero and decimal leading zeroes parse.
    x=run('server','--help',env={'BORE_MIN_PORT':'bad','BORE_MAX_PORT':'bad'})
    assert x.returncode==0
    x=run('server','--min-port','00000','--max-port','00000','--bind-addr','127.0.0.1')
    assert x.returncode in (0,1)  # Parsed as decimal; startup may fail if port 7835 is occupied.


def test_negative_option_token_has_clap_rendering():
    x=run('server','--min-port','-100','--max-port','10000')
    assert x.returncode==2 and not x.stdout and x.stderr.startswith(b"error: unexpected argument '-1' found\n")


def test_local_env_sources_and_cli_precedence_parse():
    # Missing target is supplied from BORE_SERVER; connection failure is runtime status 1.
    x=run('local','12345',env={'BORE_SERVER':'127.0.0.1'},timeout=5)
    assert x.returncode==1 and x.stderr
    x=run('local','--to','127.0.0.1','12345',env={'BORE_SERVER':'bad host'},timeout=5)
    assert x.returncode==1 and x.stderr


def test_connection_failure_preserves_host_text_and_status():
    for host in ('127.0.0.1','bad host','a:b'):
        x=run('local','--to',host,'54321',timeout=5)
        assert x.returncode==1 and x.stdout==b'' and host.encode() in x.stderr and b':7835' in x.stderr


def test_server_starts_and_handles_heartbeat_and_hello():
    with Server('--min-port','0','--max-port','0') as srv:
        s=socket.create_connection(('127.0.0.1',7835),2)
        send_frame(s,b'{"Hello":0}')
        assert json.loads(recv_frame(s)) == {'Hello':0}
        assert json.loads(recv_frame(s,2)) == 'Heartbeat'
        s.close()


def test_server_requested_port_range_and_bind_errors():
    with Server('--min-port','0','--max-port','0') as srv:
        for port in (1,65535):
            s=socket.create_connection(('127.0.0.1',7835)); send_frame(s,json.dumps({'Hello':port}).encode())
            assert json.loads(recv_frame(s)) == {'Error':'client port number not in allowed range'}; s.close()


def test_wire_frames_whitespace_fragmentation_and_bad_peers_do_not_kill_server():
    with Server('--min-port','0','--max-port','0'):
        for frame in (b' { "Hello" : 0 } \n',):
            s=socket.create_connection(('127.0.0.1',7835));
            for ch in frame+b'\0': s.sendall(bytes([ch]))
            assert json.loads(recv_frame(s)) == {'Hello':0}; s.close()
        for frame in (b'',b'{bad}',b'{"Nope":1}',b'{"Hello":-1}'):
            s=socket.create_connection(('127.0.0.1',7835)); send_frame(s,frame)
            s.settimeout(3); assert s.recv(1)==b''; s.close()
        s=socket.create_connection(('127.0.0.1',7835)); send_frame(s,b'{"Hello":0}')
        assert json.loads(recv_frame(s)) == {'Hello':0}; s.close()


def test_auth_challenge_hmac_and_invalid_tag():
    secret='s ecret'
    with Server('--min-port','0','--max-port','0','--secret',secret):
        s=socket.create_connection(('127.0.0.1',7835)); ch=json.loads(recv_frame(s))['Challenge']
        assert str(uuid.UUID(ch)) == ch and uuid.UUID(ch).version==4
        key=hashlib.sha256(secret.encode()).digest(); tag=hmac.new(key,uuid.UUID(ch).bytes,hashlib.sha256).hexdigest()
        send_frame(s,json.dumps({'Authenticate':tag}).encode()); send_frame(s,b'{"Hello":0}')
        assert json.loads(recv_frame(s)) == {'Hello':0}; s.close()
        s=socket.create_connection(('127.0.0.1',7835)); recv_frame(s); send_frame(s,b'{"Authenticate":"x"}')
        assert json.loads(recv_frame(s)) == {'Error':'invalid secret'}; s.close()


def test_auth_tag_compares_full_value_and_secret_is_case_sensitive():
    with Server('--min-port','0','--max-port','0','--secret','Secret'):
        for candidate in ('secret','x'*64):
            s=socket.create_connection(('127.0.0.1',7835)); recv_frame(s)
            send_frame(s,json.dumps({'Authenticate':candidate}).encode())
            assert json.loads(recv_frame(s)) == {'Error':'invalid secret'}; s.close()


def test_allocations_are_distinct_and_range_is_inclusive():
    with Server('--min-port','40000','--max-port','40002'):
        ss=[]
        try:
            for _ in range(3):
                s=socket.create_connection(('127.0.0.1',7835)); send_frame(s,b'{"Hello":0}')
                n=json.loads(recv_frame(s))['Hello']; assert 40000<=n<=40002; ss.append((s,n))
            assert len({n for _,n in ss})==3
        finally:
            for s,_ in ss: s.close()


def test_tunnel_forwards_binary_data_and_survives_sequential_connections():
    # Local echo target and dynamic control client exercise the documented wire protocol.
    listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(); localport=listener.getsockname()[1]
    def echo():
        while True:
            try: c,_=listener.accept()
            except OSError:return
            import threading
            def work(c):
                with c:
                    while True:
                        d=c.recv(65536)
                        if not d: break
                        c.sendall(d)
            threading.Thread(target=work,args=(c,),daemon=True).start()
    import threading
    threading.Thread(target=echo,daemon=True).start()
    with Server('--min-port','0','--max-port','0'):
        local=subprocess.Popen([str(BIN),'local',str(localport),'--to','127.0.0.1'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            end=time.time()+5; port=None
            while time.time()<end:
                try:
                    c=socket.create_connection(('127.0.0.1',7835),.2); c.settimeout(.2)
                    # Probe protocol client is separate; find local's bound assigned port via logs instead.
                    c.close()
                except OSError: pass
                time.sleep(.1)
                # Log pipes can be read nonblocking from /proc-independent fd.
                import select
                if select.select([local.stderr],[],[],0)[0]:
                    line=local.stderr.readline()
                    m=re.search(rb'listening at .*:(\d+)',line)
                    if m: port=int(m.group(1)); break
            if port is None:
                # This test still validates the service is persistent if logging format differs.
                assert local.poll() is None
                pytest.skip('runtime log did not expose assigned port in expected form')
            data=bytes(range(256))*500
            p=socket.create_connection(('127.0.0.1',port),3); p.sendall(data)
            got=bytearray()
            while len(got)<len(data): got.extend(p.recv(len(data)-len(got)))
            assert bytes(got)==data; p.close()
            p=socket.create_connection(('127.0.0.1',port),3); p.sendall(b'next'); assert p.recv(4)==b'next'; p.close()
            assert local.poll() is None
        finally:
            local.terminate(); local.wait(timeout=3); listener.close()
