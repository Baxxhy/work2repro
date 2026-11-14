import os
import subprocess
import zipfile
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')
USAGE = ("Usage: executable [ -cklnoprstvxDELNRSWX ] [ -d fontdirectory ]\n"
         "              [ -f fontfile ] [ -m smushmode ] [ -w outputwidth ]\n"
         "              [ -C controlfile ] [ -I infocode ] [ message ]\n")


def make_font(path, *, magic='flf2', hard='@', height=1, layout=-1,
              direction=0, glyphs=None, extra=''):
    """Create a small standards-shaped font; glyph rows use a safe # endmark."""
    glyphs = glyphs or {}
    path.parent.mkdir(parents=True, exist_ok=True)
    header = f'{magic}$ {hard} {height} 1 100 {layout} 0 {direction} 0\n'
    rows = []
    codes = list(range(32, 127)) + [196, 214, 220, 228, 246, 252, 223]
    for code in codes:
        body = glyphs.get(code, ' ' if code == 32 else '[' + (chr(code) if 32 <= code < 127 else '?') + ']')
        for _ in range(height):
            rows.append(body + '#')
    path.write_text(header + '\n'.join(rows) + '\n' + extra, encoding='utf-8')
    return path


@pytest.fixture
def envfont(tmp_path):
    directory = tmp_path / 'fonts'
    make_font(directory / 'standard.flf')
    make_font(directory / 'banner.flf', glyphs={ord(c): c * 2 for c in 'ABC'})
    env = os.environ.copy()
    env['FIGLET_FONTDIR'] = str(directory)
    return directory, env


def run(args=(), *, env=None, data=b'', executable=EXE):
    return subprocess.run([str(executable), *map(str, args)], input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=env, timeout=5)


def test_info_zero_exact_usage_and_version(envfont):
    _, env = envfont
    p = run(['-I', '0'], env=env)
    assert p.returncode == 0
    assert p.stderr == b''
    expected = ("FIGlet Copyright (C) 1991-2012 Glenn Chappell, Ian Chai, John Cowan,\n"
                "Christiaan Keet and Claudio Matsuoka\n"
                "Internet: <info@figlet.org> Version: 2.2.5, date: 31 May 2012\n\n"
                "FIGlet, along with the various FIGlet fonts and documentation, may be\n"
                "freely copied and distributed.\n\n"
                "If you use FIGlet, please send an e-mail message to <info@figlet.org>.\n\n"
                "The latest version of FIGlet is available from the web site,\n"
                "\thttp://www.figlet.org/\n\n" + USAGE)
    assert p.stdout == expected.encode()


@pytest.mark.parametrize(('args', 'expected'), [
    (['-I', '1'], b'20205\n'),
    (['-I', '5xyz'], b'flf2 tlf2\n'),
    (['-I', 'abc'], None),
], ids=['build-number', 'formats', 'atoi-zero'])
def test_information_codes(envfont, args, expected):
    directory, env = envfont
    p = run(args, env=env)
    assert p.returncode == 0
    if expected is None:
        assert p.stdout == (str(directory) + '\n').encode()
    else:
        assert p.stdout == expected


def test_info_respects_final_font_and_ignores_missing_files(tmp_path):
    env = os.environ.copy()
    env['FIGLET_FONTDIR'] = str(tmp_path / 'absent')
    p = run(['-I3', '-f', 'Banner.flf', '-C', 'missing', 'ignored'], env=env)
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout == b'Banner\n'


@pytest.mark.parametrize('option', ['--help', '--version', '-h', '-?'])
def test_invalid_options_have_usage(option, envfont):
    _, env = envfont
    p = run([option], env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(b'/workspace/executable: ')
    assert p.stderr.endswith(USAGE.encode())


def test_missing_option_operand(envfont):
    _, env = envfont
    p = run(['-w'], env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert b'option requires an argument --' in p.stderr
    assert p.stderr.endswith(USAGE.encode())


def test_removed_F_option_has_legacy_diagnostic(envfont):
    _, env = envfont
    p = run(['-F'], env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr.startswith(b'executable: illegal option -- F\n' + USAGE.encode())
    assert b'"-F" option has been\nremoved' in p.stderr


def test_grouped_short_options_and_interspersed_options(envfont):
    _, env = envfont
    assert run(['-W', '-L', 'A', '-R', 'B'], env=env).stdout == b'[B][A]\n'
    assert run(['-klR', 'AB'], env=env).returncode == 0
    assert run(['-w6', 'A'], env=env).stdout == b'[A]\n'


def test_missing_default_font_fails_even_on_empty_stdin(tmp_path):
    env = os.environ.copy(); env['FIGLET_FONTDIR'] = str(tmp_path)
    p = run([], env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert b'Unable to open font file' in p.stderr


def test_lookup_is_case_sensitive_and_suffix_is_stripped(envfont):
    directory, env = envfont
    p = run(['-f', 'Banner.flf', 'A'], env=env)
    assert p.returncode == 1 and b'Banner: Unable to open font file' in p.stderr
    p = run(['-I3', '-f', 'banner.FLF'], env=env)
    assert p.stdout == b'banner\n'
    p = run(['-f', 'banner.flf', 'A'], env=env)
    assert p.returncode == 0 and p.stdout == b'AA\n'


@pytest.mark.parametrize(('header', 'diagnostic'), [
    ('bad!', b'Not a FIGlet 2 font file'),
    ('flf2$ @ 1 1 256 -1 0\n', b'character is too wide'),
])
def test_invalid_font_headers(envfont, header, diagnostic):
    directory, env = envfont
    (directory / 'bad.flf').write_text(header)
    p = run(['-f', 'bad', 'A'], env=env)
    assert p.returncode == 1 and p.stdout == b''
    assert diagnostic in p.stderr


def test_cli_arguments_spacing_empty_arguments_and_stdin_ignored(envfont):
    _, env = envfont
    p = run(['One', 'Two', 'Three'], env=env, data=b'ignored')
    assert p.returncode == 0
    assert p.stdout == b'[O][n][e] [T][w][o] [T][h][r][e][e]\n'
    p = run(['hello', '', 'world'], env=env)
    assert p.stdout == b'[h][e][l][l][o] \n[w][o][r][l][d]\n'
    assert run([''], env=env).stdout == b''
    assert run(['', 'A'], env=env).stdout == b'\n[A]\n'


def test_stdin_render_and_explicit_blank_newlines(envfont):
    _, env = envfont
    assert run([], env=env, data=b'AB').stdout == b'[A][B]\n'
    assert run([], env=env, data=b'\n\n\n').stdout == b'\n\n\n'
    assert run([], env=env, data=b'').stdout == b''


def test_width_atoi_and_information(envfont):
    _, env = envfont
    assert run(['-w', '  +6tail', '-I4'], env=env).stdout == b'6\n'
    assert run(['-w0', '-I4'], env=env).stdout == b'80\n'
    assert run(['-w-9', '-I4'], env=env).stdout == b'80\n'


def test_font_and_directory_information(envfont, tmp_path):
    directory, env = envfont
    assert run(['-d', str(tmp_path), '-I2'], env=env).stdout == (str(tmp_path)+'\n').encode()
    assert run(['-f', 'banner.TLF', '-I3'], env=env).stdout == b'banner\n'


def test_direction_layout_and_justification_options(envfont):
    _, env = envfont
    assert run(['-W', 'AB'], env=env).stdout == b'[A][B]\n'
    assert run(['-R', '-W', 'AB'], env=env).stdout == b'[B][A]\n'
    assert run(['-R', '-W', '-l', 'AB'], env=env).stdout == b'[B][A]\n'
    assert run(['-R', '-W', '-x', 'AB'], env=env).stdout == b' '*73 + b'[B][A]\n'
    assert run(['-R', '-X', '-W', 'AB'], env=env).stdout == b'[A][B]\n'


def test_control_file_lookup_and_missing_control_precedes_font(envfont):
    directory, env = envfont
    p = run(['-C', 'absent', '-f', 'missing'], env=env)
    assert p.returncode == 1 and b'absent: Unable to open control file' in p.stderr
    control = directory / 'empty.flc'; control.write_text('')
    p = run(['-C', 'empty.flc', '-f', 'missing'], env=env)
    assert p.returncode == 1 and b'missing: Unable to open font file' in p.stderr


def test_control_translation_and_stages(envfont):
    directory, env = envfont
    (directory / 'swap.flc').write_text('t A B\nt B A\n')
    assert run(['-C', 'swap', 'AB'], env=env).stdout == b'[B][A]\n'
    (directory / 'stage1.flc').write_text('t A Q\nf\n')
    (directory / 'stage2.flc').write_text('t Q Z\n')
    assert run(['-C', 'stage1', '-C', 'stage2', 'A'], env=env).stdout == b'[Z]\n'
    assert run(['-C', 'stage1', '-N', 'A'], env=env).stdout == b'[A]\n'


def test_german_mode_mapping_order_and_disable(envfont):
    _, env = envfont
    assert run(['-D', '[]{}|~'], env=env).returncode == 0
    # Missing translated characters use the empty code-zero glyph.
    assert run(['-D', '-f', 'standard', '['], env=env).stdout == b''
    assert run(['-D', '-E', '['], env=env).stdout == b'[[]\n'


def test_compressed_font_and_tlf_are_read(envfont, tmp_path):
    directory, env = envfont
    raw = (directory / 'standard.flf').read_bytes()
    with zipfile.ZipFile(directory / 'packed.flf', 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr('irrelevant-name', raw)
    assert run(['-f', 'packed', 'AB'], env=env).stdout == b'[A][B]\n'
    make_font(directory / 'unicode.tlf', magic='tlf2')
    assert run(['-f', 'unicode', 'A'], env=env).stdout == b'[A]\n'
    make_font(directory / 'wrong.tlf', magic='flf2')
    p = run(['-f', 'wrong', 'A'], env=env)
    assert p.returncode == 1 and b'Not a FIGlet 2 font file' in p.stderr


def test_paragraph_mode_and_last_option_wins(envfont):
    _, env = envfont
    assert run(['-p'], env=env, data=b'A\nB').stdout == b'[A] [B]\n'
    assert run(['-p'], env=env, data=b'A\n\nB').stdout == b'[A]\n\n[B]\n'
    assert run(['-p', '-n'], env=env, data=b'A\nB').stdout == b'[A]\n[B]\n'


def test_wraps_at_width_and_width_one_keeps_whole_glyph(envfont):
    _, env = envfont
    p = run(['-W', '-w', '5', 'AB'], env=env)
    assert p.returncode == 0
    assert all(len(row) <= 4 for row in p.stdout.splitlines())
    p = run(['-w', '1', 'A'], env=env)
    assert p.stdout == b'[A]\n'


def test_utf8_control_mode_and_arbitrary_input_do_not_crash(envfont):
    directory, env = envfont
    (directory / 'utf.flc').write_text('u\n')
    for data in (b'\xff\xfe\x00', b'\xf0\x9f\x98\x80', b'\x1b$', b'\xc0'):
        p = run(['-C', 'utf'], env=env, data=data)
        assert p.returncode == 0
    p = run([], env=env, data='é'.encode())
    assert p.returncode == 0
