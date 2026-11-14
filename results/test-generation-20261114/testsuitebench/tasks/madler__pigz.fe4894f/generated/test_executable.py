import gzip
import os
import pathlib
import random
import struct
import subprocess
import zipfile
import zlib

import pytest


EXE = pathlib.Path('/workspace/executable')
HELP = """Usage: pigz [options] [files ...]
  will compress files in place, adding the suffix '.gz'. If no files are
  specified, stdin will be compressed to stdout. pigz does what gzip does,
  but spreads the work over multiple processors and cores when compressing.

Options:
  -0 to -9, -11        Compression level (level 11, zopfli, is much slower)
  --fast, --best       Compression levels 1 and 9 respectively
  -A, --alias xxx      Use xxx as the name for any --zip entry from stdin
  -b, --blocksize mmm  Set compression block size to mmmK (default 128K)
  -c, --stdout         Write all processed output to stdout (won't delete)
  -C, --comment ccc    Put comment ccc in the gzip or zip header
  -d, --decompress     Decompress the compressed input
  -f, --force          Force overwrite, compress .gz, links, and to terminal
  -F  --first          Do iterations first, before block split for -11
  -h, --help           Display a help screen and quit
  -H, --huffman        Use only Huffman coding for compression
  -i, --independent    Compress blocks independently for damage recovery
  -I, --iterations n   Number of iterations for -11 optimization
  -J, --maxsplits n    Maximum number of split blocks for -11
  -k, --keep           Do not delete original file after processing
  -K, --zip            Compress to PKWare zip (.zip) single entry format
  -l, --list           List the contents of the compressed input
  -L, --license        Display the pigz license and quit
  -m, --no-time        Do not store or restore mod time
  -M, --time           Store or restore mod time
  -n, --no-name        Do not store or restore file name or mod time
  -N, --name           Store or restore file name and mod time
  -O  --oneblock       Do not split into smaller blocks for -11
  -p, --processes n    Allow up to n compression threads (default is the
                       number of online processors, or 8 if unknown)
  -q, --quiet          Print no messages, even on error
  -r, --recursive      Process the contents of all subdirectories
  -R, --rsyncable      Input-determined block locations for rsync
  -S, --suffix .sss    Use suffix .sss instead of .gz (for compression)
  -t, --test           Test the integrity of the compressed input
  -T  --no-time        Do not store or restore mod time
  -U, --rle            Use run-length encoding for compression
  -v, --verbose        Provide more verbose output
  -V, --version        Show the version of pigz
  -Y  --synchronous    Force output file write to permanent storage
  -z, --zlib           Compress to zlib (.zz) instead of gzip format
  --                   All arguments after "--" are treated as files
"""


def run(args=(), data=b'', cwd=None, env=None, timeout=30):
    e = os.environ.copy()
    e.pop('GZIP', None)
    e.pop('PIGZ', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=timeout)


def assert_roundtrip(args, payload):
    p = run(args, payload)
    assert p.returncode == 0, p.stderr
    return p.stdout


@pytest.mark.parametrize('args,payload', [
    ([], b''), ([], b'x'), (['-c'], bytes(range(256))),
    (['-'], 'snowman ☃'.encode()), (['-p4', '-9'], b'abcd' * 10000),
], ids=['empty-stdin', 'one-byte-stdin', 'all-byte-values', 'unicode-bytes', 'worker-level'])
def test_gzip_stdin_roundtrip(args, payload):
    out = assert_roundtrip(args, payload)
    assert out[:2] == b'\x1f\x8b'
    assert gzip.decompress(out) == payload
    assert struct.unpack('<II', out[-8:]) == (zlib.crc32(payload), len(payload) & 0xffffffff)


def test_empty_stream_is_valid_nonempty_member():
    out = assert_roundtrip([], b'')
    assert 10 <= len(out) <= 50
    assert gzip.decompress(out) == b''


def test_file_compression_keep_metadata_and_permissions(tmp_path):
    src = tmp_path / 'name with ü.txt'
    src.write_bytes(b'hello' * 200)
    src.chmod(0o751)
    os.utime(src, (1600000000, 1600000000))
    p = run(['-k', str(src)])
    assert p.returncode == 0, p.stderr
    gz = pathlib.Path(str(src) + '.gz')
    assert src.read_bytes() == b'hello' * 200
    b = gz.read_bytes()
    assert b[3] & 8
    assert struct.unpack('<I', b[4:8])[0] == 1600000000
    name = b[10:b.index(b'\0', 10)]
    assert name == src.name.encode()
    assert gzip.decompress(b) == src.read_bytes()


@pytest.mark.parametrize('opts,flags,mtime', [
    (['-n'], 0, 0), (['-N', '-m'], 8, 0), (['-m', '-N'], 8, 1600000000),
    (['-n', '-N'], 8, 1600000000), (['-N', '-n'], 0, 0),
], ids=['no-name', 'name-no-time', 'time-then-name', 'no-name-then-name', 'name-then-no-name'])
def test_gzip_metadata_order(tmp_path, opts, flags, mtime):
    src = tmp_path / 'meta.bin'
    src.write_bytes(b'metadata')
    os.utime(src, (1600000000, 1600000000))
    p = run(['-c', *opts, str(src)])
    assert p.returncode == 0, p.stderr
    assert p.stdout[3] & 8 == flags
    assert struct.unpack('<I', p.stdout[4:8])[0] == mtime


def test_comment_encoding_and_order(tmp_path):
    src = tmp_path / 'c.txt'
    src.write_bytes(b'comment test')
    p = run(['-c', '-C', 'é\tline\n', '-k', str(src)])
    assert p.returncode == 0, p.stderr
    data = p.stdout
    assert data[3] & 0x10
    assert data[3] & 0x08
    end_name = data.index(b'\0', 10) + 1
    assert data[end_name:data.index(b'\0', end_name)] == 'é\tline\n'.encode()


@pytest.mark.parametrize('level', ['-0', '-1', '-3', '-5', '-7', '-9', '-11'],
                         ids=['level-0', 'level-1', 'level-3', 'level-5', 'level-7', 'level-9', 'level-11'])
def test_levels_roundtrip(level):
    payload = b'compressible phrase ' * 4000
    out = assert_roundtrip([level], payload)
    assert gzip.decompress(out) == payload


def test_level_aliases_and_process_determinism():
    data = b'alpha beta gamma ' * 2000
    assert assert_roundtrip(['--fast'], data) == assert_roundtrip(['-1'], data)
    assert assert_roundtrip(['--best'], data) == assert_roundtrip(['-9'], data)
    assert assert_roundtrip(['-p1'], data) == assert_roundtrip(['-p4'], data)
    a = [len(assert_roundtrip([f'-{n}'], data)) for n in (1, 3, 5, 7, 9)]
    assert a == sorted(a, reverse=True)
    assert a[-1] < a[0]


def test_zlib_header_adler_autodetect_and_comment_warning():
    payload = bytes(range(256)) * 20
    p = run(['-z'], payload)
    assert p.returncode == 0
    assert p.stdout[0] == 0x78
    assert (p.stdout[0] * 256 + p.stdout[1]) % 31 == 0
    assert struct.unpack('>I', p.stdout[-4:])[0] == zlib.adler32(payload)
    assert zlib.decompress(p.stdout) == payload
    assert run(['-d'], p.stdout).stdout == payload
    q = run(['-z', '-C', 'note'], payload)
    assert q.returncode == 1 and b"can't store comment in zlib format" in q.stderr
    q = run(['-z', '-C', 'note', '-q'], payload)
    assert q.returncode == 1 and q.stderr == b'' and zlib.decompress(q.stdout) == payload


def test_zip_stream_alias_comment():
    payload = b'zip payload' * 100
    p = run(['-K', '-A', 'subdir/nested.txt', '-C', 'entry comment'], payload)
    assert p.returncode == 0, p.stderr
    with __import__('io').BytesIO(p.stdout) as bio, zipfile.ZipFile(bio) as zf:
        assert zf.namelist() == ['subdir/nested.txt']
        assert zf.read(zf.namelist()[0]) == payload
        assert zf.getinfo(zf.namelist()[0]).comment == b'entry comment'


def test_file_suffix_keep_and_decompress(tmp_path):
    src = tmp_path / 'source.dat'
    src.write_bytes(b'contents' * 100)
    p = run(['-k', '-S', '.custom-long-suffix', str(src)])
    assert p.returncode == 0, p.stderr
    packed = pathlib.Path(str(src) + '.custom-long-suffix')
    assert packed.exists() and src.exists()
    assert gzip.decompress(packed.read_bytes()) == src.read_bytes()
    assert run(['-t', str(packed)]).returncode == 0

    packed2 = tmp_path / 'restore.gz'
    packed2.write_bytes(gzip.compress(b'restored'))
    q = run(['-dk', str(packed2)])
    assert q.returncode == 0, q.stderr
    assert (tmp_path / 'restore').read_bytes() == b'restored'
    assert packed2.exists()


@pytest.mark.parametrize('args,expected', [(['-V'], b'pigz 2.8\n'), (['--version'], b'pigz 2.8\n')],
                         ids=['short-version', 'long-version'])
def test_version(args, expected):
    p = run(args)
    assert p.returncode == 0 and p.stdout == expected and p.stderr == b''


def test_help_exact_and_precedence():
    p = run(['--help', '--not-a-real-option'])
    assert p.returncode == 0 and p.stdout == b'' and p.stderr.decode() == HELP


def test_license_prefix():
    p = run(['--license'])
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'pigz 2.8\nCopyright (C) 2007-2023 Mark Adler\nSubject to the terms of the zlib license.\nNo warranty is provided or implied.\n')
    assert b'Mark Adler' in p.stdout and b'zlib license' in p.stdout


@pytest.mark.parametrize('args,stderr', [
    (['--invalid-flag'], b'executable: abort: invalid option: --invalid-flag\n'),
    (['-X'], b'executable: abort: invalid option: -X\n'),
    (['-b'], b'executable: abort: missing parameter after -b\n'),
    (['-p'], b'executable: abort: missing parameter after -p\n'),
    (['-S'], b'executable: abort: missing parameter after -S\n'),
    (['-A'], b'executable: abort: missing parameter after -A\n'),
    (['-C'], b'executable: abort: missing parameter after -C\n'),
    (['-I'], b'executable: abort: missing parameter after -I\n'),
    (['-J'], b'executable: abort: missing parameter after -J\n'),
    (['-S.zzz'], b'executable: abort: invalid usage: -S must be followed by space\n'),
    (['-b', 'abc'], b'executable: abort: invalid numeric parameter: abc\n'),
    (['-b', '31'], b'executable: abort: block size too small (must be >= 32K)\n'),
    (['-b', '999999999999'], b'executable: abort: block size too large: 999999999999\n'),
    (['-p', '0'], b'executable: abort: invalid number of processes: 0\n'),
    (['-S', ''], b'executable: abort: suffix cannot be empty\n'),
    (['-10'], b'executable: abort: only levels 0..9 and 11 are allowed\n'),
    (['-Z'], b'executable: abort: invalid option: LZW output not supported: -Z\n'),
    (['-a'], b'executable: abort: invalid option: no ascii conversion: -a\n'),
], ids=['unknown-long','unknown-short','missing-b','missing-p','missing-S','missing-A','missing-C','missing-I','missing-J','joined-S','bad-number','small-block','large-block','zero-process','empty-suffix','bad-level','lzw-output','ascii'])
def test_invocation_errors(args, stderr):
    p = run(args)
    assert p.returncode == 22
    assert p.stderr == stderr


@pytest.mark.parametrize('args', [['-p', '-1'], ['-b', '-1'], ['-I', '-1'], ['-J', '-1']],
                         ids=['process-negative-option', 'block-negative-option', 'iterations-negative-option', 'splits-negative-option'])
def test_negative_value_is_missing_parameter(args):
    p = run(args)
    assert p.returncode == 22 and b'missing parameter' in p.stderr


def test_dashdash_and_help_like_filename(tmp_path):
    f = tmp_path / '--help'
    f.write_bytes(b'file data')
    p = run(['-k', '--', str(f)])
    assert p.returncode == 0, p.stderr
    assert pathlib.Path(str(f) + '.gz').exists()


def test_list_and_test_valid_and_bad_crc(tmp_path):
    src = tmp_path / 'test.txt'
    src.write_bytes(b'listing data' * 30)
    packed = tmp_path / 'test.gz'
    packed.write_bytes(gzip.compress(src.read_bytes(), mtime=0))
    p = run(['-lt', str(packed)])
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith(b'compressed   original reduced  name\n')
    assert b'test.txt' in p.stdout
    assert run(['-t', str(packed)]).stdout == b''
    damaged = bytearray(packed.read_bytes())
    damaged[-8] ^= 0xff
    bad = tmp_path / 'damaged.gz'
    bad.write_bytes(damaged)
    q = run(['-lt', str(bad)])
    assert q.returncode == 1 and q.stdout == b''
    assert b'corrupted -- crc32 mismatch' in q.stderr


@pytest.mark.parametrize('mutation,phrase', [
    ('crc', b'corrupted -- crc32 mismatch'), ('length', b'corrupted -- length mismatch'),
    ('truncate', b'corrupted -- missing trailer'),
], ids=['wrong-crc', 'wrong-length', 'missing-trailer'])
def test_integrity_diagnostics(tmp_path, mutation, phrase):
    b = bytearray(gzip.compress(b'payload for validation'))
    if mutation == 'crc':
        b[-8] ^= 1
    elif mutation == 'length':
        b[-4] ^= 1
    else:
        b = b[:-8]
    f = tmp_path / 'broken.gz'
    f.write_bytes(b)
    p = run(['-t', str(f)])
    assert p.returncode == 1 and phrase in p.stderr


def test_concatenated_gzip_members():
    a, b = gzip.compress(b'first'), gzip.compress(b'second')
    assert run(['-dc'], a + b).stdout == b'firstsecond'
    assert run(['-t'], a + b).returncode == 0


def test_force_cat_passthrough_and_trailing_junk(tmp_path):
    raw = b'not gzip'
    p = run(['-cdf'], raw)
    assert p.returncode == 0 and p.stdout == raw
    member = gzip.compress(b'valid')
    p = run(['-cdf'], member + b'xyz')
    assert p.returncode == 0 and p.stdout == b'validxyz'
    f = tmp_path / 'junk.gz'
    f.write_bytes(member + b'xyz')
    q = run(['-dv', str(f)])
    assert q.returncode == 1
    assert (tmp_path / 'junk').read_bytes() == b'valid'
    assert b'trailing junk was ignored' in q.stderr


def test_verbose_stream_and_quiet_errors():
    p = run(['-v', '-c'], b'abc')
    assert p.returncode == 0 and gzip.decompress(p.stdout) == b'abc'
    assert p.stderr == b'<stdin> to <stdout> \n'
    q = run(['-q', '--no-such-option'])
    assert q.returncode == 22 and q.stderr == b''


def test_environment_options_and_precedence():
    p = run([], b'x' * 100, env={'GZIP': '-1', 'PIGZ': '-k'})
    assert p.returncode == 0 and gzip.decompress(p.stdout) == b'x' * 100
    p = run(['-9'], b'x' * 100, env={'GZIP': '-1'})
    assert p.returncode == 0
    q = run([], b'', env={'GZIP': 'fileoperand'})
    assert q.returncode == 22 and b'cannot provide files in GZIP environment variable' in q.stderr
    q = run([], b'', env={'PIGZ': 'fileoperand'})
    assert q.returncode == 22 and b'cannot provide files in PIGZ environment variable' in q.stderr


def test_directory_and_existing_output_rules(tmp_path):
    d = tmp_path / 'dir'
    d.mkdir()
    p = run([str(d)])
    assert p.returncode == 1 and b'is a directory' in p.stderr
    src = tmp_path / 'exists.txt'
    src.write_bytes(b'new')
    out = pathlib.Path(str(src) + '.gz')
    out.write_bytes(b'keep me')
    p = run([str(src)])
    assert p.returncode == 1 and out.read_bytes() == b'keep me' and src.exists()
    p = run(['-f', str(src)])
    assert p.returncode == 0 and not src.exists() and gzip.decompress(out.read_bytes()) == b'new'


def test_file_failure_does_not_stop_later_operand(tmp_path):
    missing = tmp_path / 'missing'
    later = tmp_path / 'later'
    later.write_bytes(b'later')
    p = run(['-k', str(missing), str(later)])
    assert p.returncode == 1
    assert b'does not exist' in p.stderr
    assert pathlib.Path(str(later) + '.gz').exists()


def test_recursive_depth_and_r_file(tmp_path):
    root = tmp_path / 'tree'
    current = root
    for i in range(6):
        current = current / f'd{i}'
        current.mkdir(parents=True, exist_ok=True)
    f = current / 'leaf'
    f.write_bytes(b'leaf')
    p = run(['-rk', str(root)])
    assert p.returncode == 0, p.stderr
    assert pathlib.Path(str(f) + '.gz').exists()
    plain = tmp_path / 'plain'
    plain.write_bytes(b'plain')
    assert run(['-rk', str(plain)]).returncode == 0
    assert pathlib.Path(str(plain) + '.gz').exists()


def test_unpigz_basename_defaults_to_decompression(tmp_path):
    src = tmp_path / 'source'
    src.write_bytes(b'unpigz')
    packed = pathlib.Path(str(src) + '.gz')
    packed.write_bytes(gzip.compress(b'unpigz'))
    link = tmp_path / 'unpigz'
    link.symlink_to(EXE)
    p = subprocess.run([str(link), str(packed)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    assert p.returncode == 0, p.stderr
    assert src.read_bytes() == b'unpigz' and not packed.exists()


def test_mtime_restore_name_switch(tmp_path):
    original = tmp_path / 'original.txt'
    original.write_bytes(b'timed')
    os.utime(original, (1600000123, 1600000123))
    packed = tmp_path / 'different_name.gz'
    packed.write_bytes(gzip.compress(b'timed', mtime=1600000123))
    # Create a member with the stored original name through this implementation.
    member = run(['-c', str(original)])
    packed.write_bytes(member.stdout)
    p = run(['-dkN', str(packed)])
    assert p.returncode == 0, p.stderr
    restored = tmp_path / 'original.txt'
    assert restored.read_bytes() == b'timed'
    assert int(restored.stat().st_mtime) == 1600000123


def test_suffixless_in_place_refused_but_stdout_allowed(tmp_path):
    f = tmp_path / 'suffixless'
    f.write_bytes(gzip.compress(b'x'))
    p = run(['-d', str(f)])
    assert p.returncode == 1 and b'does not have compressed suffix' in p.stderr
    q = run(['-dc', str(f)])
    assert q.returncode == 0 and q.stdout == b'x'

