import os
import re
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, data=b'', env=None):
    e = os.environ.copy()
    e.pop('NO_COLOR', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=30)


def ordinary(data=b'', *args, **kw):
    return run(*args, data=data, **kw)


def test_help_exact_and_preempts_bad_tail():
    p = run('--help', '--definitely-not-a-flag')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == (b'Futuristic take on hexdump, made in Rust.\n\n\nUsage: executable [OPTIONS] [INPUTFILE]\n\nArguments:\n'
      b'  [INPUTFILE]  Pass file path as an argument, or input data may be passed via stdin\n\nOptions:\n'
      b'  -c, --cols <columns>        Set column length\n  -l, --len <len>             Set <len> bytes to read\n'
      b'  -f, --format <format>       Set format of octet: Octal (o), LowerHex (x), UpperHex (X), Binary (b) [possible values: o, x, X, b]\n'
      b'  -t, --color <color>         Set color tint terminal output. 0 to disable, 1 to enable [possible values: 0, 1]\n'
      b'  -a, --array <array_format>  Set source code format output: rust (r), C (c), golang (g), python (p), kotlin (k), java (j), swift (s), fsharp (f) [possible values: r, c, g, p, k, j, s, f]\n'
      b'  -u, --func <func_length>    Set function wave length\n  -p, --places <func_places>  Set function wave output decimal places\n'
      b'  -r, --prefix <prefix>      Include prefix in output (e.g. 0x/0b/0o). 0 to disable, 1 to enable [possible values: 0, 1]\n'
      b'  -h, --help                  Print help\n  -V, --version               Print version\n')


def test_version_exact_and_precedence():
    p = run('--cols=2', '-V', '/does/not/exist')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'hx 0.7.0\n', b'')

@pytest.mark.parametrize('fmt,token', [('x',b'0xab '),('X',b'0xAB '),('o',b'0o0253 '),('b',b'0b10101011 ')], ids=['hex-lower','hex-upper','octal','binary'])
def test_numeric_formats(fmt, token):
    p=ordinary(b'\xab', '-c1', '-f'+fmt)
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == b'0x000000: '+token+b'\xab\n   bytes: 1\n'


def test_prefixless_slots_and_preview():
    p=ordinary(bytes([0,32,65,126,127,255]), '-c6','-r0')
    assert p.stdout == b'0x000000: 00 20 41 7e 7f ff .....\n   bytes: 6\n'

@pytest.mark.parametrize('cols,data,expected', [
    ('2',b'ABC',b'0x000000: 0x41 0x42  ABC\n0x000002: 0x43          C\n   bytes: 3\n'),
    ('0',b'AB',b'0x000000: 0x41 A\n0x000001: 0x42 B\n0x000002: \n   bytes: 2\n'),
    ('3',b'',b'0x000000: '+b' '*15+b'\n   bytes: 0\n'),
    ('2',b'AB',b'0x000000: 0x41 0x42 AB\n0x000002: '+b' '*10+b'\n   bytes: 2\n'),
], ids=['wrap','zero-cols','empty','exact-multiple'])
def test_rows_and_empty_terminal_row(cols,data,expected):
    p=ordinary(data,'--cols='+cols)
    assert p.returncode == 0 and p.stdout == expected


def test_len_limits_before_rows():
    p=ordinary(b'ABCDE','-c2','-l3')
    assert p.stdout == b'0x000000: 0x41 0x42  AB\n0x000002: 0x43 '+b' '*5+b'C\n   bytes: 3\n'

@pytest.mark.parametrize('code,opening,closing,sep,lit', [
 ('r',b'let ARRAY: [u8; 2] = [\n',b'];\n',b', ',b'0x41, 0x42'),
 ('c',b'unsigned char ARRAY[2] = {\n',b'};\n',b', ',b'0x41, 0x42'),
 ('g',b'a := [2]byte{\n',b'}\n',b', ',b'0x41, 0x42, '),
 ('p',b'a = [\n',b']\n',b', ',b'0x41, 0x42'),
 ('k',b'val a = byteArrayOf(\n',b')\n',b', ',b'0x41, 0x42'),
 ('j',b'byte[] a = new byte[]{\n',b'};\n',b', ',b'0x41, 0x42'),
 ('s',b'let a: [UInt8] = [\n',b']\n',b', ',b'0x41, 0x42'),
 ('f',b'let a = [|\n',b'|]\n',b'; ',b'0x41uy; 0x42uy'),
], ids=['rust','c','go','python','kotlin','java','swift','fsharp'])
def test_array_templates(code,opening,closing,sep,lit):
    p=ordinary(b'AB','-a'+code,'-fX','-r0','-t1')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == opening+b'    '+lit+b'\n'+closing
    assert b'\x1b' not in p.stdout


def test_array_wrap_and_exact_multiple_empty_row():
    p=ordinary(b'ABC','-ar','-c2')
    assert p.stdout == b'let ARRAY: [u8; 3] = [\n    0x41, 0x42, \n    0x43\n];\n'
    p=ordinary(b'AB','-ac','-c2')
    assert p.stdout == b'unsigned char ARRAY[2] = {\n    0x41, 0x42\n    \n};\n'


def test_color_explicit_tokens_preview_and_zero_palette():
    p=ordinary(b'\x00A','-c2','-t1')
    assert p.returncode == 0
    assert p.stdout == (b'0x000000: \x1b[38;5;22m0x00\x1b[0m \x1b[38;5;65m0x41\x1b[0m '
                        b'\x1b[38;5;22m.\x1b[0m\x1b[38;5;65mA\x1b[0m\n   bytes: 2\n')

def test_invalid_choice_before_io():
    p=run('--format=e','/missing')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == b"error: invalid value 'e' for '--format <format>'\n  [possible values: o, x, X, b]\n\nFor more information, try '--help'.\n"

@pytest.mark.parametrize('args,first,second', [
 (('-c','-1'),b'-c, --cols <integer> expected. ParseIntError { kind: InvalidDigit }',b'error: invalid digit found in string'),
 (('-l','-1'),b'-l, --len <integer> expected. ParseIntError { kind: InvalidDigit }',b'error: invalid digit found in string'),
 (('-u','-1'),b'-u, --func <integer> expected. ParseIntError { kind: InvalidDigit }',b'error: invalid digit found in string'),
 (('-u','1','-p','x'),b'-p, --places <integer> expected. ParseIntError { kind: InvalidDigit }',b'error: invalid digit found in string'),
],ids=['cols','len','func','places'])
def test_numeric_conversion_errors(args,first,second):
    p=run(*args)
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == first+b'\n'+second+b'\n'


def test_missing_unknown_duplicate_arguments():
    p=run('--cols')
    assert p.returncode == 2 and p.stdout == b'' and b"a value is required for '--cols <columns>'" in p.stderr
    p=run('--wat')
    assert p.returncode == 2 and p.stdout == b'' and b"error: unexpected argument '--wat' found" in p.stderr
    p=run('-fX','--format','x')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == b"error: the argument '--format <format>' cannot be used multiple times\n\nUsage: executable [OPTIONS] [INPUTFILE]\n\nFor more information, try '--help'.\n"


def test_file_reading_stdin_precedence_and_dash_path(tmp_path):
    f=tmp_path/'file with spaces'
    f.write_bytes(b'Z')
    p=run(str(f),data=b'wrong')
    assert p.returncode == 0 and b'0x5a' in p.stdout and b'0x77' not in p.stdout
    p=run(str(tmp_path/'absent'))
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'error: No such file or directory (os error 2)\n'
    p=run('--','-leading',data=b'')
    assert p.returncode == 1 and p.stdout == b''


def test_function_output_precision_and_precedence():
    p=ordinary(b'ignored','-u5','-p2','-ar','-t1')
    assert (p.returncode,p.stdout,p.stderr)==(0,b'0.00,0.31,0.59,0.81,0.95,\n',b'')
    p=run('-u10','-p0')
    assert p.stdout == b'0,0,0,0,1,1,1,1,1,1,\n\n'
    p=run('-u0')
    assert p.stdout == b'\n'


def test_padding_limit_boundary():
    p=ordinary(b'Z','-c13108','-r0')
    assert p.returncode == 0 and p.stdout.startswith(b'0x000000: 5a '+b' '*65535)
    p=ordinary(b'Z','-c13109','-r0')
    assert p.returncode == 101 and p.stdout == b'0x000000: 5a '
    assert re.fullmatch(rb"\nthread 'main' \([0-9]+\) panicked at src/lib.rs:.*:\nFormatting argument out of range\nnote: run with `RUST_BACKTRACE=1` environment variable to display a backtrace\n",p.stderr)


def test_all_bytes_and_boundary_length():
    data=bytes(range(256))
    p=ordinary(data,'-c32','-r0')
    assert p.returncode == 0 and b'   bytes: 256\n' in p.stdout
    assert b'0x0000e0:' in p.stdout and b'0x000100:' in p.stdout
