import os
import re
import struct
import subprocess
import zlib
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def png(path, rgb=(255, 0, 0), alpha=255):
    def chunk(kind, data):
        return struct.pack('!I', len(data)) + kind + data + struct.pack('!I', zlib.crc32(kind + data) & 0xffffffff)
    raw = bytes((0, *rgb, alpha))
    data = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 1, 1, 8, 6, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))
    path.write_bytes(data)
    return path


@pytest.fixture
def image(tmp_path):
    return png(tmp_path / 'image with spaces.png')


def run(*args, env=None):
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(EXE), *map(str, args)], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=merged, timeout=15)


HELP = ("   ___  _____  ____\n  / _ \\/  _/ |/_/ /____ ______ _      Made with love by Eliuk Blau\n"
" / ___// /_>  </ __/ -_) __/  ' \\ https://github.com/eliukblau/pixterm\n"
"/_/  /___/_/|_|\\__\\__/_/ /_/_/_/                1.3.2\n\nUSAGE:\n\n"
"  executable [options] image/url\n\n  Supported image formats: JPEG, PNG, GIF, BMP, TIFF, WebP.\n"
"  Supported URL protocols: HTTP, HTTPS.\n\nOPTIONS:\n\n  -credits\n\tshow some love to contributors <3\n"
"  -d mode\n\tdithering mode:\n\t   0 - no dithering (default)\n\t   1 - with blocks\n\t   2 - with chars\n"
"  -go\n\toutput Go code to 'fmt.Print()' the image\n  -m color\n\tmatte color for transparency or background\n"
"\t(optional, hex format, default: 000000)\n  -nobg\n\tdisable background color\n\t(optional, only in dithering mode, ignores matte color)\n"
"  -s method\n\tscale method:\n\t   0 - resize (default)\n\t   1 - fill\n\t   2 - fit\n"
"  -tc columns\n\tterminal columns (optional, >=2; when piping, default: 80)\n  -tr rows\n"
"\tterminal rows (optional, >=2; when piping, default: 24)\n  -version\n\tshow PIXterm version\n"
"  -help\n\tprints this message :D LOL\n\n")


@pytest.mark.parametrize('flag', ['-h', '-help', '--help'], ids=['short', 'single-long', 'double-long'])
def test_help_is_exact(flag):
    p = run(flag)
    assert (p.returncode, p.stdout, p.stderr) == (0, HELP.encode(), b'')


@pytest.mark.parametrize('flag', ['-version', '--version'], ids=['single-hyphen', 'double-hyphen'])
def test_version_stands_alone(flag):
    p = run(flag, '/does/not/exist')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'1.3.2\n', b'')


def test_info_flags_precedence():
    p = run('-credits', '-version', '/missing')
    assert p.returncode == 0 and p.stdout == b'1.3.2\n' and p.stderr == b''
    c = run('-credits')
    assert c.returncode == 0 and b'CONTRIBUTORS:' in c.stdout and b'@disq' in c.stdout and not c.stderr


@pytest.mark.parametrize('args', [[], ['-d'], ['-d='], ['-d', '-1'], ['-d', '3'],
                                   ['-s', '3'], ['-tc', '1'], ['-tr=1'], ['-unknown'],
                                   ['-d', '080'], ['-d', '18446744073709551616']],
                         ids=['missing-image','missing-value','empty-equals','negative',
                              'd-range','s-range','columns-too-small','rows-too-small','unknown-option',
                              'bad-octal','uint-overflow'])
def test_usage_errors(args):
    p = run(*args)
    assert p.returncode == 2 and p.stdout == HELP.encode() and p.stderr == b''


@pytest.mark.parametrize('value', ['0', '1', '2', '0x1', '024'], ids=['zero','one','two','hex','octal'])
def test_uint_forms_and_equals(image, value):
    p = run('-d=' + value, '-tc=2', '-tr=2', image)
    assert p.returncode == 0 and p.stderr == b''


def test_stops_option_parsing_at_image(image):
    p = run(image, '-d', 'invalid')
    assert p.returncode == 0 and p.stderr == b''


@pytest.mark.parametrize('value,valid', [('bad', True), ('12345', True), ('1234567', True),
                                         ('', True), ('1234', False), ('gg0000', False), ('#ffffff', False)],
                         ids=['shorthand','five-digits','trailing-ignored','empty-default','four-digits','nonhex','hash-prefix'])
def test_matte_validation(image, value, valid):
    p = run('-m', value, '-tc', '2', '-tr', '2', image)
    assert p.returncode == (0 if valid else 2)
    if valid:
        assert not p.stderr
    else:
        assert p.stdout == HELP.encode()
        assert re.search(rb'\[PIXTERM ERROR\] \d{4}/\d\d/\d\d \d\d:\d\d:\d\d matte color : .* is not a hex-color\n$', p.stderr)


def test_missing_and_invalid_image_errors(tmp_path):
    absent = run(tmp_path / 'missing')
    assert absent.returncode == 1 and absent.stdout.startswith(HELP[:100].encode())
    assert b'open ' in absent.stderr and b'no such file or directory' in absent.stderr
    badfile = tmp_path / 'data'; badfile.write_bytes(b'not an image')
    bad = run(badfile)
    assert bad.returncode == 1 and b'image: unknown format' in bad.stderr


def test_classic_solid_color_dimensions_and_reset(image):
    p = run('-tc', '3', '-tr', '2', image)
    assert p.returncode == 0 and p.stderr == b''
    rows = p.stdout.splitlines()
    assert len(rows) == 2
    cell = b'\x1b[48;2;255;0;0m\x1b[38;2;255;0;0m' + '▄'.encode()
    assert all(row == cell * 3 + b'\x1b[0m' for row in rows)


@pytest.mark.parametrize('mode,glyph', [(1, '░'), (2, ';')], ids=['block','character'])
def test_dither_threshold_top_and_nobg(image, mode, glyph):
    p = run('-d', str(mode), '-tc', '2', '-tr', '2', image)
    assert p.returncode == 0 and len(p.stdout.splitlines()) == 2
    assert p.stdout.count(glyph.encode()) == 4
    assert b'\x1b[48;2;0;0;0m' in p.stdout and b'\x1b[38;2;255;0;0m' in p.stdout
    q = run('-d', str(mode), '-nobg', '-tc', '2', '-tr', '2', image)
    assert b'\x1b[48;2;' not in q.stdout and b'\x1b[38;2;255;0;0m' in q.stdout


def test_go_mode_escapes_rows(image):
    p = run('-go', '-tc', '2', '-tr', '2', image)
    assert p.returncode == 0 and b'\x1b' not in p.stdout
    lines = p.stdout.splitlines()
    assert len(lines) == 2
    assert all(line.startswith(b'fmt.Print("\\033[48;2;255;0;0m') and line.endswith(b'\\033[0m\\n")') for line in lines)


def test_options_environment_do_not_change_help():
    p = run('--help', env={'HOME': '/nonexistent', 'XDG_CONFIG_HOME': '/nonexistent', 'NO_COLOR': '1', 'TERM': 'dumb'})
    assert p.returncode == 0 and p.stdout == HELP.encode() and not p.stderr
