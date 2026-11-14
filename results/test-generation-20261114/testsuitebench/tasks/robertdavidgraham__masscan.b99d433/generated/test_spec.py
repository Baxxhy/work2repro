import ipaddress
import json
import os
import struct
import subprocess
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')
WARN = ('[-] FAIL: failed to load libpcap shared library\n'
        '    [hint]: you must install libpcap or WinPcap\n')


def run(*args, cwd=None, data=None):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd or EVAL,
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=8)


def out(p):
    return p.stdout.decode('utf-8', 'replace')


def err(p):
    return p.stderr.decode('utf-8', 'replace')


def echoed(*args):
    p = run(*args, '--echo')
    assert p.returncode == 0, err(p)
    assert WARN in err(p)
    return out(p), err(p)


def write_config(path, text):
    path.write_bytes(text.encode())
    return path


def v4_status(ts, ip, proto=6, port=80, reason=1, ttl=64, typ=6):
    return bytes([typ, 13]) + struct.pack('>II BHBB', ts, int(ipaddress.IPv4Address(ip)), proto, port, reason, ttl)


def v4_banner(ts, ip, proto=6, port=80, app=4, ttl=64, payload=b'hello'):
    body = struct.pack('>IIBHHB', ts, int(ipaddress.IPv4Address(ip)), proto, port, app, ttl) + payload
    return bytes([9, len(body)]) + body


def native(records, header=b'masscan/1.1\n'):
    h = header + b'\0' * (99-len(header))
    return h + b''.join(records) + b'masscan/1.1' + b'\0' * 88


def test_informational_modes_and_version():
    p = run('--help')
    assert p.returncode == 1 and p.stderr == b''
    assert p.stdout.decode() == (EVAL/'help.txt').read_text()
    p = run('--nmap')
    assert p.returncode == 1 and p.stderr == b''
    assert p.stdout.decode() == (EVAL/'nmap.txt').read_text()
    for option in ('--version', '-V'):
        p = run(option)
        lines = out(p).splitlines()
        assert p.returncode == 1 and p.stderr == b'' and lines[0] == ''
        assert lines[1].startswith('Masscan version ') and lines[2].startswith('Compiled on: ')
        assert lines[3].startswith('Compiler: ') and lines[4] == 'OS: Linux'
        assert lines[5].startswith('CPU: ') and lines[5].endswith(' (64 bits)')
        assert lines[6].startswith('GIT version: ')


def test_no_arguments_short_usage_and_warning():
    p = run()
    assert p.returncode == 1 and out(p).startswith('usage: masscan [options]')
    assert 'examples:' in out(p) and WARN in err(p)


def test_default_echo_shape_and_seed():
    s, e = echoed()
    assert e == WARN
    lines = s.splitlines()
    seed = int(lines[0].split(' = ')[1])
    assert 0 < seed < 2**64
    assert lines[1] == 'rate = 100       ' and lines[2] == 'shard = 1/1'
    assert lines[3:5] == ['nocapture = servername'] * 2
    assert lines[6] == '# TARGET SELECTION (IP, PORTS, EXCLUDES)' and lines[7] == 'ports = '


def test_long_short_and_equals_options_share_canonical_state():
    for args in [('-p80', '10.0.0.1'), ('--ports', '80', '10.0.0.1'), ('--ports=80', '10.0.0.1')]:
        s, _ = echoed(*args)
        assert 'ports = 80\nrange = 10.0.0.1\n' in s
    s, _ = echoed('--max-rate', '10000', '--source-ip', '10.1.2.3', '--source-port', '1234',
                  '--interface', 'eth0', '--output-file', 'a b.xml', '--output-format', 'XML', '-p80', '10.0.0.1')
    assert 'rate = 10000     \n' in s
    assert 'output-filename = a b.xml\noutput-format = xml\n' in s
    assert 'adapter = eth0\nadapter-ip = 10.1.2.3\nadapter-port = 1234\n' in s


def test_config_grammar_order_and_merge(tmp_path):
    f = write_config(tmp_path/'cfg file.conf', ' # comment\r\nrate = 222\r\nrotate-dir = two\r\nports = 80,81\r\n')
    s, _ = echoed('--max-rate', '333', '--rotate-dir', 'cli', '-c', f, '-p82', '10.0.0.1')
    assert 'rate = 222' in s and 'rotate-dir = two' in s
    assert 'ports = 80-82' in s
    s, _ = echoed('-c', f, '--rate', '333', '--rotate-dir', 'cli')
    assert 'rate = 333' in s and 'rotate-dir = cli' in s
    empty = write_config(tmp_path/'empty', '\n # only\n')
    assert echoed('-c', empty)[0].startswith('seed = ')


def test_config_split_equals_inline_hash_and_unknown(tmp_path):
    f = write_config(tmp_path/'hash.conf', 'rate = 222 # inline\n')
    s, e = echoed('-c', f)
    assert 'rate = 100       ' in s and 'CONF: non-digit in rate spec: rate=222 # inline' in e
    bad = write_config(tmp_path/'bad.conf', 'not-a-key = value\n')
    p = run('-c', bad, '--echo')
    assert p.returncode == 1 and 'unknown config option' in err(p)


def test_unknown_missing_and_parser_compatibility():
    p = run('--bogus')
    assert p.returncode == 1 and 'bogus: empty parameter\n' in err(p) and WARN in err(p)
    assert p.stdout.decode() == (EVAL/'short-help.txt').read_text()
    p = run('--range')
    assert p.returncode == 1 and 'range: empty parameter\n' in err(p) and WARN in err(p)
    assert p.stdout.decode() == (EVAL/'short-help.txt').read_text()
    p = run('--adapter-ip', '--echo')
    assert p.returncode == 1 and out(p) == '' and WARN not in err(p)
    assert err(p).startswith('[-] _parser_next(): unknown coding failure\nFAIL: bad source IP address: adapter-ip=--echo\n')
    p = run('-r10')
    assert p.returncode == 1 and err(p) == "nmap(-r10): wat? randomization is our raison d'etre!! rethink prease\n"
    p = run('-oX')
    assert p.returncode == 1 and err(p) == 'missing output filename\n' and not out(p)
    p = run('-oZ', 'file')
    assert p.returncode == 1 and err(p) == 'nmap(-oZ): unknown output format\n' and not out(p)


def test_target_canonicalization_merging_and_invalids():
    s, _ = echoed('--range', '192.168.1.129/28,10.0.0.1,10.0.0.2,10.0.0.3', '-p80')
    assert 'range = 10.0.0.1-10.0.0.3\nrange = 192.168.1.128/28\n' in s
    s, _ = echoed('0.0.0.0/0', '-p80')
    assert 'range = 0.0.0.0/0\n' in s
    s, e = echoed('--range', '999.1.2.3,192.168.1.,10.0.0.1-10.0.0.0', '-p80')
    assert 'ERROR: bad IP address/range: 999.1.2.3' in e
    assert 'range = 192.168.1.0\n' in s and '10.0.0.1-10.0.0.0' not in s


def test_ipv6_normalization_and_echo_cidr():
    s, _ = echoed('--range', '[2001:DB8::1]/64,2001:db8::1,::1', '-p80')
    assert 'range = 2001:db8::/64' in s and 'range = ::1' in s
    p = run('--echo-cidr', '--range', '192.168.1.0-192.168.1.100')
    assert p.returncode == 0 and out(p).splitlines() == ['192.168.1.0/26','192.168.1.64/27','192.168.1.96/30','192.168.1.100/32']
    p = run('--echo', '--range', '2001:db8::/32', '-p80')
    assert p.returncode == 1 and not out(p) and 'requested is 97 bits' in err(p) and WARN in err(p)


def test_include_and_exclusion_files(tmp_path):
    inc = write_config(tmp_path/'targets', ' # comment\n10.0.0.1\n10.0.0.2\n2001:db8::1\n')
    exc = write_config(tmp_path/'exclude', '10.0.0.1\n10.0.0.2\n')
    s, e = echoed('--includefile', inc, '--excludefile', exc, '-p80')
    assert '10.0.0.1' not in s and '10.0.0.2' not in s and 'range = 2001:db8::1' in s
    assert f'{exc}: excluding 1 ranges from file' in e
    p = run('--echo', '-p80', '10.0.0.0/24', '--excludefile', '/dev/null')
    assert p.returncode == 0 and err(p) == WARN


def test_ports_protocols_topports_exclusions_and_errors():
    s, _ = echoed('-sU', '-p', '53,10-12,11', '--exclude-ports', '11', '--topports', '10')
    assert 'ports = U:10,U:12,U:21-25,U:80,U:443,U:990,U:992,U:8080' in s
    assert 'ports = 1-65535' in echoed('-p-')[0]
    assert 'ports = 80,443,U:53,S:7' in echoed('-p', 'T:80,T:443,U:53,S:7')[0]
    p = run('-p99999')
    assert p.returncode == 1 and err(p) == '[-] FAIL: bad target port: 99999\n    Hint: a port is a number [0..65535]\n'
    p = run('--echo', '-p', '80-79', '10.0.0.1')
    assert p.returncode == 1 and err(p) == '[-] FAIL: bad target port: 80-79\n    Hint: a port is a number [0..65535]\n'
    p = run('--echo', '--ports', '')
    assert p.returncode == 0 and 'ports = \n' in out(p)


def test_scan_validation_exclusions_and_offline(tmp_path):
    p = run('10.0.0.1')
    assert p.returncode == 1 and WARN in err(p) and 'FAIL: no ports were specified' in err(p)
    p = run('-p80')
    assert p.returncode == 1 and WARN in err(p) and 'FAIL: target IP address list empty' in err(p)
    p = run('--offline', '-p80', '10.0.0.1', '--output-format', 'list', '--output-file', tmp_path/'out')
    assert WARN in err(p) and 'offline = true' in echoed('--offline')[0]
    assert (tmp_path/'out').exists()


def test_rate_seed_shard_retries_ttl_and_rotation():
    s, e = echoed('--rate', '0.5', '--seed', '18446744073709551615', '--shard', '2/4', '--retries', '-1', '--ttl', '300')
    assert 'rate = 0.5' in s and 'seed = 18446744073709551615' in s and 'shard = 2/4' in s
    assert 'retries' not in s and 'ttl =' not in s
    assert 'FAIL: retries=<n>: expected number less than 1000' in e and 'ttl=<n>' in e
    s, _ = echoed('--rotate-time', 'hourly', '--rotate-offset', '-5h', '--rotate-filesize', '2g', '--hello-timeout', '7')
    assert 'rotate = 3600' in s and 'rotate-offset = 68400' in s and 'rotate-size = 2147483648' in s and 'hello-timeout = 7' in s
    p = run('--rotate', '2d', '--echo')
    assert p.returncode == 1 and not out(p) and err(p) == '--rotate-offset: value is greater than 1 day\n'


def test_adapter_mac_vlan_packet_and_banner_settings():
    s, e = echoed('--banners', '--rawudp', '--source-ip', '10.0.0.1,10.0.0.2', '--adapter-mac', 'AABBCCDDEEFF', '--router-mac', '01:02:03:04:05:06', '--vlan', '37', '--tcp-mss', '1460', '--tcp-wscale', '15', '--tcp-tsecho', '--tcp-sackok', '--noreset', '--min-packet', '64', '--data-length', '100', '-pU:161', '10.0.0.1')
    for needle in ('banners = true','rawudp = true','adapter-ip = 10.0.0.1','adapter-mac = aa-bb-cc-dd-ee-ff','router-mac-ipv4 = 01-02-03-04-05-06','router-mac-ipv6 = 01-02-03-04-05-06','tcp-mss = enable','tcp-wscale = 15','tcp-tsecho = enable','tcp-sackok = enable','noreset = true','min-packet = 64','ports = U:161'):
        assert needle in s
    assert 'vlan =' not in s and 'data-length =' not in s
    assert e == WARN


def test_capture_type_and_vuln_serialization():
    s, _ = echoed('--banners', '--capture', 'heartbleed')
    assert s.count('capture = heartbleed') == 2 and s.count('nocapture = servername') == 2
    s, _ = echoed('--capture', 'servername')
    assert 'nocapture' not in s and 'capture = servername' not in s
    s, _ = echoed('--vuln', 'poodle')
    assert 'banners = true\nnocapture = cert\nnocapture = servername\nnocapture = cert\nnocapture = servername' in s
    p = run('--vuln', 'invalid')
    assert p.returncode == 1 and "FAIL: vuln check 'invalid' does not exist" in err(p) and WARN not in err(p)


def test_http_hello_and_freeform_values(tmp_path):
    s, _ = echoed('--http-host', '[::1]:8080', '--http-user-agent', 'Agent/Ünicode', '--http-cookie', 'a=b; c=d', '--http-header', 'X-Custom: Value', '--http-field[10]', 'X-Ten:V', '--hello-string', '[80]GET\r\n', '--hello-string[443]', 'abc', '--hello', 'ssl')
    assert 'http-host = [::1]:8080' in s and 'http-user-agent = Agent/Ünicode' in s
    assert 'http-header = X-Custom:Value' in s and 'http-header = X-Ten:V' in s
    assert 'hello-string[0] = [80]GET\r\n' in s and 'hello-string[443] = abc' in s and 'hello = ssl' in s
    p = run('--http-query', 'a=b=c', '--echo')
    assert p.returncode == 1 and not out(p) and 'CONF: unknown config option: http-query=a=b=c' in err(p)
    f = tmp_path/'hi.bin'; f.write_bytes(b'hello')
    s, _ = echoed(f'--hello-file[80]={f}')
    assert 'hello-string[80] = aGVsbG8=' in s


def test_output_aliases_validation_and_files(tmp_path):
    s, _ = echoed('-oH', 'x.out', '--append-output', '--ndjson-status', '--stylesheet', 'x.xsl')
    assert 'output-format = hostonly' in s and 'output-filename = x.out' in s
    assert 'output-append = true' in s and 'ndjson-status = true' in s and 'stylesheet = x.xsl' in s
    p = run('--echo', '--output-format', 'cert')
    assert p.returncode == 0 and 'output-format =' not in out(p) and 'FAIL: unknown output-format: cert' in err(p)
    p = run('--output-format', 'xml', '--output-filename', '')
    assert p.returncode == 1 and 'examples:' in out(p) and 'no ports' not in err(p)
    p = run('--echo', '--output-format', 'xml', '--output-file', tmp_path/'missing'/'x')
    # Echo does not open output destinations.
    assert p.returncode == 0


def test_nmap_compatibility_errors():
    cases = [('-b', "nmap(-b): FTP bounce scans will never be supported\n"),
             ('-f', 'nmap(-f): fragmentation not yet supported\n'),
             ('--dns-servers','nmap(dns-servers): unsupported: DNS lookups too synchronous\n'),
             ('--host-timeout','nmap(host-timeout): unsupported: this is an asynchronous tool, so no timeouts\n')]
    vals = {'--dns-servers':'8.8.8.8','--host-timeout':'10m'}
    for opt, expected in cases:
        p = run(opt, *([vals[opt]] if opt in vals else []))
        assert p.returncode == 1 and p.stdout == b'' and err(p) == expected
    p = run('-sT', '-p80')
    assert p.returncode == 1 and 'nmap(-sT): connect()' in err(p) and WARN in err(p)


def test_selftest_and_list_scan():
    for opt in ('--selftest','--self-test','--regress'):
        p = run(opt)
        assert p.returncode == 0 and p.stdout == b'' and WARN in err(p) and 'regression test: success!\n' in err(p)
    p = run('-sL', '--seed', '12345', '10.0.0.0/30')
    assert p.returncode == 0 and out(p).splitlines() == ['10.0.0.0','10.0.0.3','10.0.0.1','10.0.0.2']
    p = run('-sL', '--seed', '12345', '2001:db8::/126')
    assert out(p).splitlines() == ['2001:db8::','2001:db8::3','2001:db8::1','2001:db8::2']


def test_readscan_binary_and_json_roundtrip(tmp_path):
    f = tmp_path/'scan.bin'; f.write_bytes(native([v4_status(1640000000,'192.0.2.1'), v4_banner(1640000001,'192.0.2.2',payload=b'hi')]))
    p = run('--readscan', f)
    assert p.returncode == 0 and '[+] --readscan' in err(p) and 'Discovered open port 80/tcp on 192.0.2.1' in out(p)
    assert 'Banner on port 80/tcp on 192.0.2.2: [http] hi' in out(p)
    j = tmp_path/'result.json'
    p = run('--readscan', f, '-oJ', j)
    assert p.returncode == 0 and WARN in err(p)
    data = json.loads(j.read_text())
    assert len(data) == 2 and data[0]['ip'] == '192.0.2.1' and data[1]['service']['name'] == 'http'
    b = tmp_path/'round.bin'; p = run('--readscan', f, '-oB', b)
    assert p.returncode == 0 and b.read_bytes().startswith(b'masscan/1.1\n')


def test_readscan_filters_and_conversion_formats(tmp_path):
    f = tmp_path/'scan.bin'; f.write_bytes(native([v4_status(1,'192.0.2.1',port=80), v4_status(2,'192.0.2.1',port=443), v4_status(3,'192.0.2.2',proto=17,port=53,typ=7)]))
    for fmt in ('-oL','-oG','-oD','-oX','-oU','-oH'):
        target=tmp_path/(fmt[2:]+'.out')
        p=run('--readscan',f,fmt,target,'--show','all')
        assert p.returncode == 0 and target.exists() and target.stat().st_size > 0
    h=tmp_path/'host'; run('--readscan',f,'-oH',h,'--show','all')
    assert h.read_text().splitlines() == ['192.0.2.1','192.0.2.1','192.0.2.2']
    p=run('--readscan',f,'--show','all','--ports','U:53','-oL',tmp_path/'filtered')
    assert p.returncode == 0 and (tmp_path/'filtered').read_bytes() == b''


def test_readscan_bad_input_is_bounded_and_nonfatal(tmp_path):
    f=tmp_path/'bad'; f.write_bytes(b'')
    p=run('--readscan',f)
    assert p.returncode == 0 and 'file too short' in err(p)
    unknown=tmp_path/'unknown'; unknown.write_bytes(b'masscan/1.1\n'+b'\0'*88+b'c\x00')
    p=run('--readscan',unknown)
    assert p.returncode == 0 and 'unknown file format' in err(p)


def test_banner1_valid_and_missing(tmp_path):
    ethernet = b'\0'*12 + b'\x08\0'
    ip_header = bytes([0x45,0,0,40,0,0,0,0,64,6,0,0]) + b'\0'*8
    tcp_header = b'\0'*20
    frame = ethernet + ip_header + tcp_header
    good=tmp_path/'ok.pcap'
    good.write_bytes(struct.pack('<IHHIIII',0xa1b2c3d4,2,4,0,0,65535,1)+struct.pack('<IIII',1,2,len(frame),len(frame))+frame)
    p=run('--banner1',good)
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b''
    p=run('--banner1',tmp_path/'missing')
    assert p.returncode == 1 and 'could not open capture file' in err(p) and WARN not in err(p)


def test_banner_and_capture_debug_and_iflist():
    p=run('--debug-tcp','--echo')
    assert p.returncode == 0 and 'debug-tcp' not in out(p) and err(p) == WARN
    p=run('-dd','--echo')
    assert p.returncode == 0 and 'pfring: error: dlopen' in err(p)
    p=run('--iflist')
    assert p.returncode == 0 and WARN in err(p) and 'libpcap not loaded' in err(p)


def test_ancillary_recognized_and_unknown_options():
    s,_=echoed('--interactive','--nostatus','--status','--reason','--datadir','dir with spaces','--debug','7','--nobacktrace','--status-ndjson','-p80','10.0.0.1')
    assert 'ndjson-status = true' in s and 'datadir' not in s and 'interactive' not in s
    for args, expected in [(("--ssl-versions","tls1.2,tls1.3"),'ssl-versions=tls1.2,tls1.3'),
                           (("--status-timer","5"),'status-timer=5'),
                           (("--redis-password","pw"),'redis-password=pw')]:
        p=run(*args,'--echo')
        assert p.returncode == 1 and not out(p) and f'unknown config option: {expected}' in err(p)
    p=run('--status','true','--echo')
    assert p.returncode == 1 and 'unknown command-line parameter "true"' in err(p)


def test_missing_config_paths_and_missing_required_mode(tmp_path):
    spelling = '/nonexistent/file with spaces.conf'
    p = run('--conf', spelling, '--echo', cwd='/workspace')
    assert p.returncode == 0 and f'[-] {spelling}: No such file or directory' in err(p)
    assert '[-] cwd = /workspace\n' in err(p) and err(p).endswith(WARN)
    p = run('--conf', spelling, cwd='/workspace')
    assert p.returncode == 1 and p.stdout.decode() == (EVAL/'short-help.txt').read_text()
    assert f'[-] {spelling}: No such file or directory' in err(p) and err(p).endswith(WARN)


def test_target_include_grammar_and_subtraction(tmp_path):
    targets = tmp_path/'targets.txt'
    targets.write_text(' ; ignored\n// ignored\n- also ignored\n192.168.1.0/24\n')
    exclusions = tmp_path/'ex.txt'
    exclusions.write_text('192.168.1.1-192.168.1.10\n')
    s, e = echoed('-iL', targets, '--exclude-file', exclusions, '-p80')
    assert 'range = 192.168.1.0\nrange = 192.168.1.11-192.168.1.255\n' in s
    assert 'excluding 1 ranges from file' in e
    dash = tmp_path/'dash.txt'; dash.write_text('192.168.1.1–192.168.1.10\n')
    assert 'range = 192.168.1.1-192.168.1.10' in echoed('--include-file', dash, '-p80')[0]


def test_ipv6_cidr_echo_and_parser_exception():
    p = run('--echo-cidr', '--range', '2001:db8::1-2001:db8::ff')
    assert p.returncode == 0
    assert out(p).splitlines() == ['2001:db8::1/128','2001:db8::2/127','2001:db8::4/126','2001:db8::8/125','2001:db8::10/124','2001:db8::20/123','2001:db8::40/122','2001:db8::80/121']
    p = run('--echo', 'ffff:ffff:ffff:ffff:ffff:ffff:ffff:ffff', '-p80')
    assert p.returncode == 1 and not out(p) and 'FAIL: unknown command-line parameter' in err(p)


def test_port_exclusions_and_no_target_or_port_scan_failures():
    p = run('--echo', '-p', '1-100', '--exclude-ports', '50-60')
    assert p.returncode == 0 and 'ports = 1-49,61-100' in out(p)
    p = run('-p80', '10.0.0.1', '--exclude-ports', '1-65535')
    assert p.returncode == 1 and 'all ports were removed by exclusion ranges' in err(p)
    p = run('-p80', '10.0.0.1', '--exclude', '10.0.0.0/24')
    assert p.returncode == 1 and 'all addresses were removed by exclusion ranges' in err(p)


def test_echo_order_additive_hello_strings_and_capture_variants():
    s, _ = echoed('--hello-string[80]', 'first', '--hello-string[80]', 'last', '--hello-string[443]', 'ssl', '--banners', '--capture', 'cert')
    assert s.index('hello-string[443] = ssl') < s.index('hello-string[80] = last') < s.index('hello-string[80] = first')
    assert 'banners = true\nhello-string' in s
    assert 'capture = cert' not in s
    s, _ = echoed('--banners', '--capture', 'servername', '--capture', 'heartbleed')
    assert s.count('capture = heartbleed') == 2 and 'capture = servername' not in s
    s, _ = echoed('--banners', '--capture', 'heartbleed', '--nocapture', 'heartbleed')
    assert s.count('nocapture = servername') == 2 and 'capture = heartbleed' not in s


def test_service_probe_and_nmap_payload_files(tmp_path):
    probe = tmp_path/'nmap-service-probes'
    probe.write_text('Exclude 1\nProbe TCP Test q|hello|\nports 80\nmatch http m|^HTTP/1| p/HTTP/\n')
    p = run('--nmap-service-probes', probe, '--echo')
    assert p.returncode == 0 and 'nmap-service-probes = ' + str(probe) in out(p)
    assert 'Probe TCP Test q|hello|' in out(p) and 'ports 80' in out(p)
    assert 'match http m/^HTTP/1/ p/HTTP/ ' in out(p)
    payload = tmp_path/'payloads'; payload.write_text('udp 53 "DNS" source 0\n')
    p = run('--nmap-payloads', payload, '--echo')
    assert p.returncode == 0 and 'nmap-payloads = ' + str(payload) in out(p)
    missing = run('--pcap-payloads', tmp_path/'absent', '--echo')
    assert missing.returncode == 0 and 'pcap-payloads =' in out(missing) and "payloads: can't read from file" in err(missing)


def test_benchmark_sections_and_round_control():
    p = run('--benchmark', '--blackrock-rounds', '6')
    s = out(p)
    assert '=== benchmarking (64-bits) ===' in s
    for section in ('-- blackrock-1 -- ', '-- blackrock-2 -- ', '-- smack-1 -- '):
        assert section in s
    assert 'rounds = 6' in s
    assert 'iterations/second =' in s and 'bits/second =' in s


def test_script_lua_unavailable_and_empty_script():
    p = run('--script', 'anything.lua', '--echo')
    assert p.returncode == 1 and 'liblua: failed to load Lua shared library' in err(p)
    assert all(f'liblua: {name}: failed' in err(p) for name in ('lua_version','luaL_newstate','luaL_openlibs','luaL_loadfilex','lua_pcallk','lua_close'))
    assert 'Segmentation fault: please post this backtrace to:' in out(p) and 'script =' not in out(p)
    p = run('--script', '', '--echo')
    assert p.returncode == 1 and out(p) == (EVAL/'short-help.txt').read_text() and err(p) == WARN
