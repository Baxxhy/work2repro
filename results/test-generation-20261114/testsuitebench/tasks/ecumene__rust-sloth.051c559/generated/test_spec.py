import os
import pathlib
import struct
import subprocess
import pytest

E = pathlib.Path('/workspace/executable')
ROOT = pathlib.Path(__file__).parent

def run(*args):
    return subprocess.run([str(E), *map(str, args)], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

@pytest.fixture
def obj(tmp_path):
    p = tmp_path / 'empty.obj'; p.write_text('# empty\n'); return p

def tri_obj(path, verts='v 0 0 0\nv 1 0 0\nv 0 1 0\n'):
    path.write_text(verts + 'f 1 2 3\n'); return path

def test_root_help_exact():
    r=run('--help'); assert r.returncode == 0 and r.stderr == b''
    assert r.stdout.startswith(b'Sloth 0.1\nMitchell Hynes. <mshynes@mun.ca>\n') and r.stdout.endswith(b'\n')
    assert b'SUBCOMMANDS:' in r.stdout and b'image    Generates' in r.stdout

def test_short_root_help():
    r=run('-h'); assert r.returncode == 0 and r.stdout.startswith(b'Sloth 0.1\n') and not r.stderr

def test_help_precedes_unknown():
    r=run('--help','nonsense'); assert r.returncode == 0 and r.stdout.startswith(b'Sloth 0.1\n') and not r.stderr

def test_version_forms():
    for flag in ('--version','-V'):
        r=run(flag); assert (r.returncode,r.stdout,r.stderr)==(0,b'Sloth 0.1\n',b'')

def test_help_route():
    r=run('help'); assert r.returncode == 0 and r.stdout.startswith(b'Sloth 0.1\n')

def test_image_help_content():
    r=run('image','--help'); assert r.returncode == 0 and not r.stderr
    assert r.stdout.startswith(b'executable-image \nMitchell Hynes <mitchell.hynes@ecumene.xyz>\n')
    assert b'-j, --webify <frame count>' in r.stdout and b'-w <width>' in r.stdout and b'-h <height>' in r.stdout

def test_help_image_route():
    r=run('help','image'); assert r.returncode == 0 and b'executable-image ' in r.stdout and b'--webify' in r.stdout

def test_no_args_diagnostic():
    r=run(); assert r.returncode != 0 and not r.stdout and b'<input filename(s)>...' in r.stderr and r.stderr.startswith(b'error:')

def test_image_missing_width_usage(obj):
    r=run(obj,'image'); assert r.returncode != 0 and not r.stdout
    assert b'The following required arguments were not provided:' in r.stderr and b'executable image [FLAGS] [OPTIONS] -w <width>' in r.stderr

def test_image_missing_root_input_width(obj):
    r=run('image'); assert r.returncode == 1 and not r.stdout and b'<input filename(s)>... image [FLAGS] [OPTIONS] -w <width>' in r.stderr

def test_missing_webify_value(obj):
    r=run(obj,'image','-w','3','-j'); assert r.returncode == 1 and not r.stdout
    assert b"--webify <frame count>' requires a value" in r.stderr and b'executable image --webify <frame count> -w <width>' in r.stderr

@pytest.mark.parametrize('value', ['abc','1.5','1e2'], ids=['alpha','decimal','exponent'])
def test_bad_dimension_is_parseint(obj,value):
    r=run(obj,'image','-w',value); assert r.returncode == 1 and r.stderr == b'Error: ParseIntError { kind: InvalidDigit }\n'

def test_empty_dimension_value(obj):
    r=run(obj,'image','-w',''); assert r.returncode == 1 and r.stderr == b'Error: ParseIntError { kind: Empty }\n'

def test_bad_rotation_is_parsefloat(obj):
    r=run(obj,'image','-w','2','-x','bad'); assert r.returncode == 1 and r.stderr == b'Error: ParseFloatError { kind: Invalid }\n'

def test_negative_separate_dimension_rejected(obj):
    r=run(obj,'image','-w','-1'); assert r.returncode != 0 and b"Found argument '-1'" in r.stderr

def test_negative_attached_rotation_accepted(obj):
    r=run(obj,'image','-w','0','--yaw=-1.57'); assert r.returncode == 0 and not r.stdout and not r.stderr

def test_zero_dimensions_no_output(obj):
    r=run(obj,'image','-w','0'); assert (r.returncode,r.stdout,r.stderr)==(0,b'',b'')

def test_dimensions_and_default_height(obj):
    for args in [('1',),('100',),('100','80'),('1','100'),('100','1')]:
        w=args[0]; extra=('-h',args[1]) if len(args)>1 else ()
        r=run(obj,'image','-w',w,*extra); assert r.returncode==0 and not r.stderr and r.stdout

def test_empty_obj_colored_linear_cells(obj):
    r=run(obj,'image','-w','2','-h','1'); cell=b'\x1b[48;2;25;25;25m\x1b[38;2;0;0;0m \x1b[49m\x1b[39m'
    assert r.returncode==0 and r.stdout==cell*3 and not r.stderr

def test_empty_obj_plain_keeps_extra_cells(obj):
    r=run('-b',obj,'image','-w','2','-h','1'); assert (r.returncode,r.stdout,r.stderr)==(0,b'   \n',b'')

def test_image_black_flag_is_ignored(obj):
    r=run(obj,'image','-b','-w','1'); assert r.returncode==0 and r.stdout.startswith(b'\x1b[48;2;25;25;25m')

def test_triangle_renders_shader_character(tmp_path):
    p=tri_obj(tmp_path/'t.obj'); r=run(p,'image','-w','20','-h','20')
    assert r.returncode==0 and not r.stderr and any(c in r.stdout for c in b'.:-=+*#%@')

def test_obj_default_color_is_white(tmp_path):
    p=tri_obj(tmp_path/'t.obj'); r=run(p,'image','-w','20','-h','20')
    assert b'\x1b[38;2;255;255;255m' in r.stdout

def test_multiple_argv_only_first_loaded(tmp_path):
    first=tmp_path/'a.obj'; first.write_text('# empty\n'); second=tri_obj(tmp_path/'b.obj')
    a=run(first,'image','-w','2','-h','1'); b=run(first,second,'image','-w','2','-h','1')
    assert a.returncode==b.returncode==0 and a.stdout==b.stdout

def test_space_delimited_single_filename_loads_each(tmp_path):
    a=tri_obj(tmp_path/'a.obj'); b=tmp_path/'b.obj'; b.write_text('# empty\n')
    r=run(str(a)+' '+str(b),'image','-w','20'); assert r.returncode==0 and b'255;255;255' in r.stdout

def test_unrecognized_word_is_input_not_subcommand(obj):
    r=run(obj,'fakesubcommand'); assert r.returncode != 0 and b'Inappropriate ioctl for device' in r.stderr

def test_extensionless_load_panics(tmp_path):
    p=tmp_path/'plain'; p.write_text(''); r=run(p,'image','-w','1')
    assert r.returncode==101 and r.stderr.startswith(b'\nthread \'main\'') and b"couldn't determine filename extension" in r.stderr

def test_unknown_extension_panics(tmp_path):
    p=tmp_path/'x.ply'; p.write_text(''); r=run(p,'image','-w','1')
    assert r.returncode==101 and b'unknown filename extension' in r.stderr

def test_obj_invalid_vertex_panics(tmp_path):
    p=tmp_path/'bad.obj'; p.write_text('v nope 0 0\nf 1 1 1\n'); r=run(p,'image','-w','1')
    assert r.returncode==101 and b'position parse error' in r.stderr

def test_mtl_diffuse_truncates(tmp_path):
    (tmp_path/'m.mtl').write_text('newmtl red\nKd 0.5 0.999 0\n')
    p=tmp_path/'m.obj'; p.write_text('mtllib m.mtl\nv 0 0 0\nv 1 0 0\nv 0 1 0\nusemtl red\nf 1 2 3\n')
    r=run(p,'image','-w','20'); assert r.returncode==0 and b'\x1b[38;2;127;254;0m' in r.stdout

def test_missing_mtl_has_distinct_panic(tmp_path):
    p=tmp_path/'m.obj'; p.write_text('mtllib absent.mtl\n')
    r=run(p,'image','-w','1'); assert r.returncode==101 and b'Expected to have materials.: OpenFileFailed' in r.stderr
    assert b"couldn't load" not in r.stderr and not r.stdout

def test_ascii_stl_color(tmp_path):
    p=tmp_path/'t.stl'; p.write_text('solid x\n facet normal 0 0 1\n outer loop\n vertex 0 0 0\n vertex 1 0 0\n vertex 0 1 0\n endloop\n endfacet\nendsolid x\n')
    r=run(p,'image','-w','20'); assert r.returncode==0 and b'\x1b[38;2;255;255;0m' in r.stdout

def test_truncated_binary_stl_panics(tmp_path):
    p=tmp_path/'bad.stl'; p.write_bytes(b'bad'); r=run(p,'image','-w','2')
    assert r.returncode==101 and b'failed to fill whole buffer' in r.stderr

def test_webify_frames_and_format(obj):
    r=run(obj,'image','-w','2','-h','1','-j','2'); assert r.returncode==0 and r.stdout.startswith(b'let frames = [\n`\n')
    assert r.stdout.count(b'`\n')==2 and r.stdout.endswith(b'`];\n') and b'<span style="color:rgb(0,0,0)"> ' in r.stdout

def test_webify_zero_frames_is_one(obj):
    r=run(obj,'image','-w','1','-j','0'); assert r.returncode==0 and r.stdout.count(b'`\n')==1 and r.stdout.endswith(b'`];\n')

def test_webify_plain_mode(obj):
    r=run('-b',obj,'image','-w','1','-j','1'); assert r.returncode==0 and b'<span' not in r.stdout and r.stdout.endswith(b' \n`];\n')

def test_webify_invalid_frame_count(obj):
    r=run(obj,'image','-w','1','-j','1.5'); assert r.returncode==1 and r.stderr==b'Error: ParseIntError { kind: InvalidDigit }\n'

def test_root_rotation_reset_in_image_mode(obj):
    base=run(obj,'image','-w','20','-h','20'); rootrot=run('-x=1.2',obj,'image','-w','20','-h','20')
    assert base.returncode==rootrot.returncode==0 and base.stdout==rootrot.stdout

def test_attached_image_rotation_is_accepted(obj):
    r=run(obj,'image','-w','0','-x=-1.5708'); assert r.returncode==0 and not r.stderr
