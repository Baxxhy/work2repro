import os
import struct
import subprocess
import zlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def chunk(kind, data):
    return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)


def png(path, pixels):
    h, w = len(pixels), len(pixels[0])
    raw = b''.join(b'\0' + b''.join(bytes(p) for p in row) for row in pixels)
    path.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


@pytest.fixture
def img(tmp_path):
    p = tmp_path / 'sample.png'
    png(p, [[(0,0,0),(85,85,85),(170,170,170),(255,255,255)] for _ in range(4)])
    return p


def run(*args, input=None, cwd=ROOT, env=None, timeout=8):
    e = os.environ.copy()
    e.pop('TERM', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd, env=e, timeout=timeout)


def test_help_exact():
    r=run('--help')
    assert r.returncode == 0 and r.stderr == b''
    assert r.stdout.startswith(b'This tool converts images into ascii art')
    assert b'Further configuration can be managed with flags' in r.stdout
    assert b'configuration files' not in r.stdout and r.stdout.endswith(b'Apache-2.0)\n')


@pytest.mark.parametrize('flag', ['-v','--version'], ids=['short','long'])
def test_version(flag):
    r=run(flag)
    assert r.returncode == 0 and r.stderr == b''
    assert len(r.stdout.splitlines()) == 1 and r.stdout.startswith(b'v')


def test_formats_without_input():
    r=run('--formats')
    assert r.returncode == 0
    assert r.stdout == b'Supported input formats:\n\nJPEG/JPG\nPNG\nWEBP\nBMP\nTIFF/TIF\nGIF\n\n'


def test_no_input_and_piped_bytes_are_not_implicit():
    r=run(input=b'not an image')
    assert r.returncode == 0 and r.stdout == b'Error: Need at least 1 input path/url or piped input\nUse the -h flag for more info\n\n'


def test_parser_errors_and_help_combination():
    r=run('--nonesuch')
    assert r.returncode == 1 and b'--nonesuch' in r.stderr and b'Usage:' in r.stderr
    r=run('--help','--nonesuch')
    assert r.returncode == 1 and b'unknown flag' in r.stderr and b'Flags:' in r.stderr


@pytest.mark.parametrize('args,needle', [
    (('--save-img',),'needs an argument'), (('--save-txt',),'needs an argument'),
    (('--save-gif',),'needs an argument'), (('--font',),'needs an argument'),
    (('-m',),'needs an argument'), (('--width','x'),'invalid argument "x"'),
    (('--height','x'),'invalid argument "x"'), (('--threshold','x'),'--threshold'),
    (('--font-color','1,x,3'),'strconv.Atoi: parsing'), (('--save-bg','1,2,x,4'),'strconv.Atoi: parsing')
], ids=['save-img-missing','save-txt-missing','save-gif-missing','font-missing','map-missing','width-parse','height-parse','threshold-parse','font-color-parse','save-bg-parse'])
def test_parser_value_diagnostics(args, needle):
    r=run(*args)
    assert r.returncode == 1 and needle.encode() in r.stderr


@pytest.mark.parametrize('args,message', [
    (('--map','x'),'Need at least 2 characters for --map flag'),
    (('--dimensions','1'),'requires 2 dimensions, got 1'),
    (('--dimensions','1,2,3'),'requires 2 dimensions, got 3'),
    (('--dimensions','0,2'),'invalid values for dimensions'),
    (('--width','-1'),'invalid value for width'),
    (('--height','-1'),'invalid value for height'),
    (('--width','2','--height','2'),"both --width and --height can't be set"),
    (('--font-color','1,2'),'--font-color requires 3 values for RGB, got 2'),
    (('--font-color','256,0,0'),'RBG values must be between 0 and 255'),
    (('--save-bg','1,2,3'),'--save-bg requires 4 values for RGBA, got 3'),
    (('--save-bg','-1,2,3,101'),'RBG values must be between 0 and 255'),
    (('--threshold','256'),'threshold must be between 0 and 255'),
    (('--dither',),'image dithering is only reserved for --braille'),
    (('--only-save',),'you need to supply one of --save-img'),
])
def test_semantic_validation_before_open(args,message):
    r=run('/no/such/input',*args)
    assert r.returncode == 0 and message.encode() in r.stdout and r.stdout.endswith(b'\n\n')


def test_file_errors_and_content_detection(img,tmp_path):
    renamed=tmp_path/'renamed.txt'; renamed.write_bytes(img.read_bytes())
    r=run(renamed,'-W','4','--map','AB')
    assert r.returncode == 0 and r.stdout.endswith(b'\n') and b"can't decode" not in r.stdout
    r=run(tmp_path/'missing.png','-W','4')
    assert b'unable to open file' in r.stdout and r.returncode == 0
    r=run(tmp_path,'-W','4')
    assert b'image: unknown format' in r.stdout and b'is a directory' not in r.stdout
    r=run('-',input=b'garbage','-W','4')
    assert b"can't decode piped input: image: unknown format" in r.stdout


def test_stdin_must_be_only_operand(img):
    r=run('-',img,'-W','4',input=img.read_bytes())
    assert r.returncode == 0 and b'cannot pass in piped input alongside other inputs' in r.stdout


def test_mapping_edges_flip_negative_and_rows(img):
    r=run(img,'-d','4,1','--map','ABCD')
    assert r.stdout == b'ABCD\n'
    assert run(img,'-d','4,1','--map','ABCD','-x').stdout == b'DCBA\n'
    assert run(img,'-d','4,1','--map','ABCD','-n').stdout == b'DCBA\n'
    assert run(img,'-d','4,1','--map','ABCD','-n','-x').stdout == b'ABCD\n'


def test_size_aliases_maps_and_flag_order(img):
    assert run(img,'-W','4','--map','XY').stdout.count(b'\n') >= 1
    assert run('--map','XY','-d','4,2',img).stdout.count(b'\n') == 2
    assert run(img,'--complex','--map','xy','-d','4,1').stdout == b'xyxy\n'
    assert run(img,'--map','','-d','4,1').stdout.endswith(b'\n')


def test_braille_blank_white_black_and_threshold(img,tmp_path):
    white=tmp_path/'white.png'; black=tmp_path/'black.png'
    png(white,[[(255,255,255)]*2 for _ in range(4)])
    png(black,[[(0,0,0)]*2 for _ in range(4)])
    assert run(white,'--braille','-d','1,1').stdout == '⣿\n'.encode()
    assert run(black,'--braille','-d','1,1').stdout == '⠀\n'.encode()
    assert run(white,'--braille','--negative','-d','1,1').stdout == '⠀\n'.encode()
    assert run(black,'--braille','--negative','-d','1,1').stdout == '⣿\n'.encode()


def test_alpha_image_and_tiny_dimensions(tmp_path):
    p=tmp_path/'alpha.png'
    # RGBA input, fully transparent red must behave as zero depth.
    raw=b'\0'+bytes([255,0,0,0])
    p.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(raw))+chunk(b'IEND',b''))
    r=run(p,'-d','1,1','--map','AB')
    assert r.stdout == b'A\n'


def test_multi_input_order_continues_after_error(img,tmp_path):
    r=run(img,tmp_path/'bad',img,'-d','4,1','--map','ABCD')
    assert r.returncode == 0 and r.stdout.count(b'ABCD\n') == 2
    assert r.stdout.index(b'ABCD\n') < r.stdout.index(b'unable to open file') < r.stdout.rindex(b'ABCD\n')


def test_txt_save_preserves_grid_and_only_save(img,tmp_path):
    out=tmp_path/'out'; out.mkdir()
    r=run(img,'-d','4,1','--map','ABCD','--save-txt',out,'--only-save')
    saved=out/'sample-ascii-art.txt'
    assert r.returncode == 0 and saved.read_bytes() == b'ABCD'
    assert b'Saved ' in r.stdout and b'ABCD' not in r.stdout
    r=run(img,'--save-txt',tmp_path/'absent','-W','4')
    assert b"save path" in r.stdout and not (tmp_path/'absent').exists()


def test_save_img_valid_png_and_combined_order(img,tmp_path):
    pngout=tmp_path/'png'; txtout=tmp_path/'txt'; pngout.mkdir(); txtout.mkdir()
    r=run(img,'-d','2,1','--save-img',pngout,'--save-txt',txtout,'--only-save')
    assert r.returncode == 0
    assert (pngout/'sample-ascii-art.png').read_bytes().startswith(b'\x89PNG')
    assert (txtout/'sample-ascii-art.txt').exists()
    assert r.stdout.index(b'sample-ascii-art.png') < r.stdout.index(b'sample-ascii-art.txt')


def test_color_headless_errors_and_txt_remains_uncolored(img,tmp_path):
    r=run(img,'--color','-W','4')
    assert r.returncode == 0 and b'terminal supports neither 24-bit nor 8-bit colors' in r.stdout
    out=tmp_path/'out'; out.mkdir()
    r=run(img,'--color','--save-txt',out,'--only-save','-W','4')
    assert b'terminal supports neither' in r.stdout
    assert not list(out.iterdir())


def test_font_validation_order(img,tmp_path):
    r=run(tmp_path/'missing.png','--font',tmp_path/'bad.ttf','-W','4')
    assert b'unable to open file' in r.stdout
    r=run(img,'--font',tmp_path/'missing.ttf','-W','4')
    assert b'unable to open font file' in r.stdout
    bad=tmp_path/'bad.ttf'; bad.write_text('not a font')
    r=run(img,'--font',bad,'-W','4')
    assert b'unable to parse font file' in r.stdout


def test_after_double_dash_treats_help_as_path():
    r=run('--','--help','-W','4')
    assert r.returncode == 0 and b'unable to open file' in r.stdout and b'This tool converts' not in r.stdout
