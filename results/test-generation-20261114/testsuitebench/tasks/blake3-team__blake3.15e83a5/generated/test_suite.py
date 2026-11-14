import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')
EMPTY = 'af1349b9f5f9a1a6a0404dea36dcc9499bcb25c9adc112b7cc9a93cae41f3262'
FOO = '04e0bb39f30b1a3feb89f536c93be15055482df748674b00d26e5a75777702e9'
TEST = '4878ca0425c739fa427f7eda20fe845f6b2e46ba5fe2a14df5b1e32f50603215'


def run(args=(), data=b'', cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd)


def standard(hex_digest, name):
    return f'{hex_digest}  {name}\n'.encode()


def test_help_short_and_long_describe_executable():
    for flag in ('--help', '-h'):
        p = run([flag])
        assert p.returncode == 0 and p.stderr == b''
        text = p.stdout.decode()
        assert text.startswith('Usage: executable [OPTIONS] [FILE]...\n')
        assert 'b3sum' not in text
        for option in ('--keyed', '--derive-key', '--length', '--seek', '--num-threads',
                       '--no-mmap', '--no-names', '--raw', '--tag', '--check', '--quiet',
                       '--version'):
            assert option in text


def test_version_exact():
    p = run(['--version'])
    assert (p.returncode, p.stdout, p.stderr) == (0, b'b3sum 1.8.4\n', b'')


@pytest.mark.parametrize('value_form', ['--length abc', '--length=abc', '--seek abc',
                                          '--seek=abc', '--num-threads abc', '--num-threads=abc'],
                         ids=['length-separated', 'length-equals', 'seek-separated',
                              'seek-equals', 'threads-separated', 'threads-equals'])
def test_invalid_decimal_diagnostic(value_form):
    option, value = value_form.split(' ', 1) if ' ' in value_form else value_form.split('=', 1)
    longopt, metav = {'--length': ('--length <LEN>', 'LEN'), '--seek': ('--seek <SEEK>', 'SEEK'),
                      '--num-threads': ('--num-threads <NUM>', 'NUM')}[option]
    p = run([option, value]) if ' ' in value_form else run([value_form])
    expected = (f"error: invalid value 'abc' for '{longopt}': invalid digit found in string\n\n"
                "For more information, try '--help'.\n").encode()
    assert p.returncode == 2 and p.stdout == b'' and p.stderr == expected


@pytest.mark.parametrize('args', [('--length',), ('--seek',), ('--num-threads',)],
                         ids=['missing-length', 'missing-seek', 'missing-threads'])
def test_missing_option_value_is_usage_error(args):
    assert run(args).returncode == 2


def test_default_stdin_and_explicit_dash_and_empty_sources(tmp_path):
    assert run(data=b'').stdout == standard(EMPTY, '-')
    assert run(['-'], data=b'').stdout == standard(EMPTY, '-')
    empty = tmp_path / 'empty file'
    empty.write_bytes(b'')
    assert run([empty]).stdout == standard(EMPTY, str(empty))
    assert run(['/dev/null']).stdout == standard(EMPTY, '/dev/null')


def test_known_hashes_binary_input_and_stream_boundaries(tmp_path):
    assert run(data=b'foo').stdout == standard(FOO, '-')
    assert run(data=b'test').stdout == standard(TEST, '-')
    binary = bytes(range(256)) + b'\x00\xff\xc3\x28'
    for size in [63, 64, 65, 1023, 1024, 1025, 2047, 2048, 2049, 65537]:
        payload = (binary * ((size // len(binary)) + 1))[:size]
        f = tmp_path / f'data-{size}'
        f.write_bytes(payload)
        p = run([f])
        assert p.returncode == 0 and p.stderr == b''
        # Verify the same bytes through stdin, exercising independent input routes.
        assert run(data=payload).stdout.split(b'  ')[0] == p.stdout.split(b'  ')[0]


def test_operand_order_repeated_stdin_and_independent_hashes(tmp_path):
    a, b = tmp_path / 'a', tmp_path / 'b'
    a.write_bytes(b'foo'); b.write_bytes(b'test')
    p = run([a, '-', b, '-'], data=b'input')
    rows = p.stdout.splitlines()
    assert [r.split(b'  ', 1)[1] for r in rows] == [str(a).encode(), b'-', str(b).encode(), b'-']
    assert rows[0].startswith(FOO.encode()) and rows[1] != rows[3]
    assert rows[3].startswith(EMPTY.encode())


def test_symlink_and_path_spelling(tmp_path):
    f = tmp_path / 'target'; f.write_bytes(b'foo')
    link = tmp_path / 'link'; link.symlink_to(f)
    rel = os.path.relpath(f, os.getcwd())
    p = run([rel, link])
    assert p.stdout == standard(FOO, rel) + standard(FOO, str(link))


def test_text_layout_no_names_tag_length_zero_and_composition(tmp_path):
    assert run(['--length', '0']).stdout == b'  -\n'
    assert run(['--length=0', '--no-names']).stdout == b'\n'
    assert run(['--tag'], data=b'foo').stdout == f'BLAKE3 (-) = {FOO}\n'.encode()
    assert run(['--no-names'], data=b'foo').stdout == (FOO + '\n').encode()
    assert run(['--length=+1', '--seek=+1', '--num-threads=+2', '--no-mmap'], data=b'foo').returncode == 0
    f = tmp_path / 'spaced name'; f.write_bytes(b'foo')
    assert run(['--num-threads', '100', '--tag', f]).stdout == f'BLAKE3 ({f}) = {FOO}\n'.encode()


def test_raw_exact_bytes_and_rejects_multiple_inputs(tmp_path):
    assert run(['--raw'], data=b'foo').stdout == bytes.fromhex(FOO)
    assert run(['--raw', '--tag'], data=b'foo').stdout == bytes.fromhex(FOO)
    a = tmp_path / 'a'; b = tmp_path / 'b'; a.write_bytes(b'a'); b.write_bytes(b'b')
    p = run(['--raw', a, b])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'Error: Only one filename can be provided when using --raw\n'


def test_names_with_control_bytes_are_escaped(tmp_path):
    name = 'a\nb\\c\r'
    path = tmp_path / name
    path.write_bytes(b'foo')
    expected = b'\\' + FOO.encode() + b'  a\\nb\\\\c\\r\n'
    assert run([path]).stdout == expected
    assert run(['--no-names', path]).stdout == (FOO + '\n').encode()


def test_keyed_mode_lengths_and_stdin_rules(tmp_path):
    key = bytes(range(32)); f = tmp_path / 'f'; f.write_bytes(b'foo')
    p = run(['--keyed', f], data=key)
    assert p.returncode == 0 and p.stdout.startswith(b'') and p.stderr == b''
    # Identical key and bytes must give identical selected bytes across files.
    assert run(['--keyed', '--no-names', f, f], data=key).stdout.splitlines()[0] == \
           run(['--keyed', '--no-names', f], data=key).stdout.strip()
    p = run(['--keyed'], data=key)
    assert p.returncode == 2
    for data, expected in [(b'abc', b'Error: expected 32 key bytes from stdin, found 3\n'),
                           (key + b'x', b'Error: read more than 32 key bytes from stdin\n')]:
        p = run(['--keyed', f], data=data)
        assert p.returncode == 1 and p.stdout == b'' and p.stderr == expected
    p = run(['--keyed', '-'], data=key)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'b3sum: -: Cannot open `-` in keyed mode\n'


def test_mode_conflicts_exact():
    p = run(['--keyed', '--derive-key', 'test', 'file'])
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == (b"error: the argument '--keyed' cannot be used with '--derive-key <CONTEXT>'\n\n"
                        b'Usage: executable --keyed <FILE>...\n\nFor more information, try \'--help\'.\n')


def test_xof_lengths_seek_slices_and_raw(tmp_path):
    payload = b'foo'
    long = run(['--length', '160'], data=payload).stdout.split(b'  ')[0]
    for offset in [0, 1, 10, 32, 63, 64, 65]:
        p = run(['--seek', str(offset), '--length', '19', '--no-names'], data=payload)
        assert p.stdout == long[offset*2:(offset+19)*2] + b'\n'
        raw = run(['--raw', '--seek', str(offset), '--length', '19'], data=payload)
        assert raw.stdout == bytes.fromhex(long.decode())[offset:offset+19]
    assert run(['--seek', '18446744073709551615', '--length', '1'], data=payload).returncode == 0
    assert run(['--length', '100000'], data=payload).returncode == 0


@pytest.mark.parametrize('mode', ['keyed', 'derived'], ids=['keyed-xof', 'derive-xof'])
def test_xof_slicing_is_consistent_in_keyed_and_derive_modes(mode, tmp_path):
    f = tmp_path / 'message'; f.write_bytes(b'foo')
    key = bytes(range(32))
    prefix = ['--keyed'] if mode == 'keyed' else ['--derive-key', 'non-ascii ☃ context']

    def invoke(extra):
        return run([*prefix, '--no-names', *extra, f], data=key if mode == 'keyed' else b'')

    whole = invoke(['--length', '100']).stdout.rstrip(b'\n')
    for start, size in [(1, 1), (31, 4), (63, 3), (64, 8)]:
        part = invoke(['--seek', str(start), '--length', str(size)]).stdout.rstrip(b'\n')
        assert part == whole[start * 2:(start + size) * 2]


def test_derive_key_and_strategy_options_are_deterministic(tmp_path):
    f = tmp_path / 'input'; f.write_bytes(b'foo')
    base = run(['--derive-key', 'ctx', f]).stdout
    for args in [('--derive-key', 'ctx', '--num-threads', '0', '--no-mmap', f),
                 ('--no-mmap', '--num-threads=100', f)]:
        p = run(args)
        assert p.returncode == 0
        if args[0] == '--derive-key':
            assert p.stdout == base
        else:
            assert p.stdout == standard(FOO, str(f))


def test_normal_hash_continues_after_failed_operands(tmp_path):
    good1 = tmp_path / 'one'; good2 = tmp_path / 'two'
    good1.write_bytes(b'foo'); good2.write_bytes(b'test')
    missing = tmp_path / 'absent'
    p = run([good1, missing, '/tmp', good2])
    assert p.returncode == 1
    assert p.stdout == standard(FOO, str(good1)) + standard(TEST, str(good2))
    assert p.stderr == (f'b3sum: {missing}: No such file or directory (os error 2)\n'
                        'b3sum: /tmp: Is a directory (os error 21)\n').encode()


def test_check_valid_formats_order_and_quiet(tmp_path):
    f = tmp_path / 'file'; f.write_bytes(b'foo')
    standard_line = f'{FOO}  {f}\r\n'.encode()
    tag_line = f'BLAKE3 ({f}) = {FOO}'.encode()
    listing = tmp_path / 'checks'; listing.write_bytes(standard_line + tag_line)
    p = run(['--check', listing])
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == f'{f}: OK\n{f}: OK\n'.encode()
    assert run(['--check', '--quiet', listing]).stdout == b''
    empty = tmp_path / 'empty'; empty.write_bytes(b'')
    assert run(['--check', empty]).returncode == 0
    assert run(['--check'], data=standard_line).stdout == f'{f}: OK\n'.encode()


def test_check_failures_and_summary(tmp_path):
    f = tmp_path / 'file'; f.write_bytes(b'foo')
    listing = tmp_path / 'checks'
    listing.write_text(f'{EMPTY}  {f}\n{TEST}  {tmp_path / "missing"}\n\n')
    p = run(['--check', listing])
    assert p.returncode == 1
    assert p.stdout == (f'{f}: FAILED\n{tmp_path / "missing"}: FAILED (No such file or directory (os error 2))\n').encode()
    assert p.stderr.endswith(b'b3sum: Empty line\n' + b'b3sum: WARNING: 3 computed checksums did NOT match\n')
    q = tmp_path / 'one'; q.write_text(f'{EMPTY}  {f}\n')
    assert run(['--check', q]).stderr.endswith(b'b3sum: WARNING: 1 computed checksum did NOT match\n')
    assert run(['--check', '--quiet', q]).stdout == b''


@pytest.mark.parametrize('line,reason', [
    (b'', 'Empty line'), (b'bad', 'Invalid check line format'),
    (b'abc  x', 'Invalid hash length'), (b'G' * 64 + b'  x', 'Invalid hex'),
    (b'BLAKE3 (x) = ' + b'a' * 63, 'Invalid hash length'),
    (b'BLAKE3 (x) = ' + b'A' * 64, 'Invalid hex'),
    (b'a' * 64 + b' x', 'Invalid check line format'),
], ids=['blank', 'format', 'short-hash', 'bad-hex', 'tag-short', 'tag-uppercase', 'one-space'])
def test_check_line_diagnostics(line, reason, tmp_path):
    listing = tmp_path / 'list'; listing.write_bytes(line)
    p = run(['--check', listing])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(f'b3sum: {reason}\n'.encode())


def test_check_standard_path_spacing_and_raw_backslash(tmp_path):
    weird = tmp_path / 'three  spaces\tand\\slash'; weird.write_bytes(b'foo')
    line = f'{FOO}   {weird.name}\n'.encode()
    listing = tmp_path / 'list'; listing.write_bytes(line)
    p = run(['--check', listing], cwd=tmp_path)
    assert p.stdout == f' {weird.name}: OK\n'.encode()
    win = r'C:\folder\file'
    listing.write_bytes(f'{FOO}  {win}\n'.encode())
    p = run(['--check', listing], cwd=tmp_path)
    assert p.stdout == f'{win}: FAILED (No such file or directory (os error 2))\n'.encode()


def test_check_escaped_path_round_trip(tmp_path):
    name = 'a\nb\\c\r'
    f = tmp_path / name; f.write_bytes(b'foo')
    escaped = name.replace('\\', '\\\\').replace('\n', '\\n').replace('\r', '\\r')
    listing = tmp_path / 'list'; listing.write_bytes(('\\' + FOO + '  ' + escaped + '\n').encode())
    p = run(['--check', listing], cwd=tmp_path)
    assert p.returncode == 0 and p.stdout == ('\\' + escaped + ': OK\n').encode()


@pytest.mark.parametrize('escape,reason', [(b'\\q', 'Invalid backslash escape'),
                                           (b'abc\\', 'Invalid backslash escape'),
                                           (b'\\0', 'Invalid backslash escape')],
                         ids=['unknown', 'trailing', 'nul-escape'])
def test_check_invalid_escapes(escape, reason, tmp_path):
    listing = tmp_path / 'list'; listing.write_bytes(b'\\' + FOO.encode() + b'  ' + escape + b'\n')
    p = run(['--check', listing])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(f'b3sum: {reason}\n'.encode())


@pytest.mark.parametrize('name_bytes,reason', [(b'\\x00', 'Null character in path'),
                                                (b'\xef\xbf\xbd', 'Unicode replacement character in path'),
                                                (b'', 'empty file path')],
                         ids=['decoded-nul', 'replacement-character', 'empty-escaped-path'])
def test_check_rejects_forbidden_decoded_paths(name_bytes, reason, tmp_path):
    listing = tmp_path / 'list'
    listing.write_bytes(b'\\' + FOO.encode() + b'  ' + name_bytes + b'\n')
    p = run(['--check', listing])
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(f'b3sum: {reason}\n'.encode())


def test_check_rejects_conflicts():
    for args, first, usage in [
        (['--check', '--keyed', 'list'], "error: the argument '--check' cannot be used with '--keyed'", 'Usage: executable --check <FILE>...'),
        (['--check', '--derive-key', 'x', 'list'], "error: the argument '--check' cannot be used with '--derive-key <CONTEXT>'", 'Usage: executable --check <FILE>...'),
        (['--check', '--length', '1', 'list'], "error: the argument '--check' cannot be used with '--length <LEN>'", 'Usage: executable --check <FILE>...'),
        (['--check', '--raw', 'list'], "error: the argument '--check' cannot be used with '--raw'", 'Usage: executable --check <FILE>...'),
        (['--raw', '--check', 'list'], "error: the argument '--raw' cannot be used with '--check'", 'Usage: executable --raw [FILE]...'),
        (['--check', '--tag', 'list'], "error: the argument '--check' cannot be used with '--tag'", 'Usage: executable --check <FILE>...'),
        (['--check', '--no-names', 'list'], "error: the argument '--check' cannot be used with '--no-names'", 'Usage: executable --check <FILE>...'),
    ]:
        p = run(args)
        assert p.returncode == 2 and p.stdout == b''
        assert p.stderr.startswith(first.encode() + b'\n\n' + usage.encode() + b'\n')


def test_check_seek_verifies_selected_segment(tmp_path):
    f = tmp_path / 'x'; f.write_bytes(b'x')
    listing = tmp_path / 'list'
    listing.write_text(f'735346fb7a91417776e1ac03b26699484ecc2b754111b9474f7d0252846ec1a0  {f}\n')
    p = run(['--check', '--seek', '99', '--num-threads=0', '--no-mmap', listing])
    assert p.returncode == 0 and p.stdout == f'{f}: OK\n'.encode()
    q = run(['--check', listing])
    assert q.returncode == 1 and b': FAILED\n' in q.stdout
