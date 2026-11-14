import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

AGE = Path('/workspace/executable')


def run(*args, data=b'', env=None, cwd=None):
    return subprocess.run([str(AGE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, cwd=cwd, timeout=45)


def err(p):
    return p.stderr.decode('utf-8', 'replace')


def successful(p):
    assert p.returncode == 0, err(p)


def failed(p, fragment):
    assert p.returncode != 0
    assert fragment in err(p), err(p)


@pytest.fixture(scope='module')
def keys(tmp_path_factory):
    tool = shutil.which('age-keygen')
    if not tool:
        pytest.skip('age-keygen helper unavailable')
    d = tmp_path_factory.mktemp('keys')
    f = d / 'identity key.txt'
    p = subprocess.run([tool, '-o', str(f)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert p.returncode == 0, p.stderr.decode('utf-8', 'replace')
    text = f.read_text()
    m = re.search(r'(?m)^# public key: (\S+)', text)
    assert m, text
    return f, m.group(1)


def test_no_args_and_help():
    p = run()
    failed(p, 'usage')
    assert p.stdout == b''
    p = run('-h', '-p')
    successful(p)
    assert p.stdout == b''
    for word in ('--encrypt', '--decrypt', '--recipient', '--recipients-file', '--identity', '--passphrase', '--armor'):
        assert word in err(p)


def test_unknown_flag_mentions_parser_error():
    failed(run('--definitely-unknown'), 'flag provided but not defined')


@pytest.mark.parametrize('args,fragment', [
    (('-e','-d'), "-e/--encrypt can't be used with -d/--decrypt"),
    (('-d','-a'), "-a/--armor can't be used with -d/--decrypt"),
    (('-d','-p'), "-p/--passphrase can't be used with -d/--decrypt"),
    (('-d','-r','age1bad'), "-r/--recipient can't be used with -d/--decrypt"),
    (('-p','-r','age1bad'), "-p/--passphrase can't be combined with -r/--recipient"),
    (('-p','-R','x'), "-p/--passphrase can't be combined with -R/--recipients-file"),
    (('-p','-i','x'), '-i/--identity and -j can\'t be used in encryption mode'),
    (('-e','-i','x'), '-i/--identity and -j can\'t be used in encryption mode'),
    (('-e',), 'missing recipients'),
    (('--encrypt','--recipient=age1bad','a','b'), 'too many INPUT arguments'),
])
def test_invalid_option_combinations(args, fragment):
    failed(run(*args), fragment)


def test_invalid_combo_hints_and_stdin_conflict():
    p = run('-d','-a')
    assert 'note that armored files are detected automatically' in err(p)
    failed(run('-d','-R','-', '-i','-'), 'standard input is used for multiple purposes')


def test_missing_input_diagnostic():
    p = run('-r','age1bad','/definitely/not/a/real/input')
    failed(p, 'failed to open input file')
    assert '/definitely/not/a/real/input' in err(p)
    assert 'no such file or directory' in err(p)


def test_recipient_syntax_errors():
    failed(run('-r','github:someone'), 'github:" recipients were removed from the design')
    failed(run('-r','AGE1QQQQQQ'), 'unknown recipient type')
    failed(run('-r','age1notpqkey123456789abcdef'), 'invalid recipient encoding')


def test_recipient_file_validation(tmp_path):
    f=tmp_path/'recipients.txt'
    f.write_bytes(b'\xff')
    failed(run('-R',f), 'recipients file is not valid UTF-8')
    f.write_text('# comment\n\n')
    failed(run('-R',f), 'no recipients found')
    f.write_text('not-a-recipient\n')
    p=run('-R',f)
    failed(p, 'failed to parse recipient file')
    assert 'malformed recipient at line 1' in err(p)
    failed(run('-R',tmp_path/'missing'), 'failed to parse recipient file')


def test_identity_validation_precedes_ciphertext(tmp_path):
    cases=[(b'', 'no identities found'), (b'age1something\n','apparent recipient found in identities file'),
           (b'not-an-identity\n','unknown identity type'), (b'\xff','identities file is not valid UTF-8')]
    for i,(content,fragment) in enumerate(cases):
        f=tmp_path/f'id{i}'; f.write_bytes(content)
        p=run('-d','-i',f, data=b'test')
        failed(p,fragment)
        assert 'unexpected intro' not in err(p)
    failed(run('-d','-i',tmp_path/'absent',data=b'test'),'failed to open file')


def test_empty_and_bad_headers():
    failed(run('-d',data=b''),'file is empty')
    failed(run('-d',data=b'bad-header\n'),'unexpected intro')
    failed(run('-d',data=b'age-encryption.org/v1\n'),'failed to read header')
    p=run('-d',data=b'age-encryption.org/v1\r\n')
    failed(p,'invalid header intro')
    assert 'PowerShell redirection' in err(p)


def test_same_input_output_rejected(tmp_path, keys):
    ident, recipient=keys
    f=tmp_path/'same'; f.write_bytes(b'hello')
    failed(run('-r',recipient,'-o',f,f), 'input and output file are the same')
    assert f.read_bytes()==b'hello'


def test_binary_roundtrip_stdin_stdout(keys):
    ident, recipient=keys
    payload=bytes(range(256))*256+b'\x00tail'
    c=run('-r',recipient,data=payload); successful(c)
    assert c.stdout != payload
    d=run('-d','-i',ident,data=c.stdout); successful(d)
    assert d.stdout==payload
    assert c.stderr==d.stderr==b''


def test_encryptions_are_random(keys):
    _,recipient=keys
    a=run('-r',recipient,data=b'same'); b=run('-r',recipient,data=b'same')
    successful(a); successful(b)
    assert a.stdout != b.stdout


def test_armor_roundtrip_and_shape(keys):
    ident,recipient=keys
    payload=b'armored\x00data'
    c=run('-a','-r',recipient,data=payload); successful(c)
    assert c.stdout.startswith(b'-----BEGIN AGE ENCRYPTED FILE-----\n')
    assert c.stdout.endswith(b'-----END AGE ENCRYPTED FILE-----\n')
    assert all(len(line)<=64 for line in c.stdout.splitlines()[1:-1])
    d=run('-d','-i',ident,data=c.stdout); successful(d); assert d.stdout==payload


@pytest.mark.parametrize('blob,fragment,case_id', [
    (b'-----BEGIN AGE ENCRYPTED FILE-----\n', 'invalid armor: unexpected EOF', 'missing-footer'),
    (b'-----BEGIN AGE ENCRYPTED FILE-----\n\n-----END AGE ENCRYPTED FILE-----\n', 'invalid armor: empty line in armored data', 'empty-data-line'),
    (b'-----BEGIN AGE ENCRYPTED FILE-----\n!!!!\n-----END AGE ENCRYPTED FILE-----\n', 'invalid armor: illegal base64 data', 'bad-base64'),
    (b'-----BEGIN AGE ENCRYPTED FILE-----\n' + b'A'*65 + b'\n-----END AGE ENCRYPTED FILE-----\n', 'invalid armor: column limit exceeded', 'long-line'),
    (b'-----BEGIN AGE ENCRYPTED FILE-----\nYQ==\n-----END PEM FILE-----\n', 'invalid armor: invalid closing line', 'bad-footer'),
    (b'-----BEGIN AGE ENCRYPTED FILE-----\nYQ==\n-----END AGE ENCRYPTED FILE-----\ntrailing', 'invalid armor: trailing data after armored file', 'trailing'),
], ids=['missing-footer','empty-data-line','bad-base64','long-line','bad-footer','trailing'])
def test_malformed_armor_is_rejected(blob, fragment, case_id):
    failed(run('-d', data=blob), fragment)


def test_corrupt_ciphertext_does_not_succeed(keys):
    ident,recipient=keys
    c=run('-r',recipient,data=b'authenticated'); successful(c)
    damaged=bytearray(c.stdout); damaged[-1]^=1
    p=run('-d','-i',ident,data=bytes(damaged))
    assert p.returncode != 0
    assert p.stdout==b''


def test_duplicate_recipient_warns(keys):
    _,recipient=keys
    p=run('-r',recipient,'-r',recipient,data=b'x'); successful(p)
    assert 'duplicate recipient' in err(p)


def test_output_created_for_empty_plaintext(keys,tmp_path):
    ident,recipient=keys
    encrypted=tmp_path/'cipher'; plain=tmp_path/'empty'
    successful(run('-r',recipient,'-o',encrypted,data=b''))
    successful(run('-d','-i',ident,'-o',plain,encrypted))
    assert plain.exists() and plain.read_bytes()==b''


def test_recipient_errors_do_not_create_output(tmp_path):
    output=tmp_path/'should-not-exist'
    failed(run('-r','not-a-recipient','-o',output,data=b'x'), 'unknown recipient type')
    assert not output.exists()


@pytest.mark.parametrize('size', [0,1,65535,65536,65537], ids=['empty','one','chunk-minus-one','chunk','chunk-plus-one'])
def test_chunk_boundaries(keys,size):
    ident,recipient=keys
    payload=bytes((i*37)%256 for i in range(size))
    c=run('-r',recipient,data=payload); successful(c)
    d=run('-d','-i',ident,data=c.stdout); successful(d)
    assert d.stdout==payload
