import os
import re
import struct
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')


def run(tmp_path, *args, data=None, cwd=None, timeout=30):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd or tmp_path, timeout=timeout)


def put(tmp_path, name, data):
    p = tmp_path / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data.encode('utf-8') if isinstance(data, str) else data)
    return p


def png_info(data):
    assert data.startswith(b'\x89PNG\r\n\x1a\n')
    assert data[-8:] == b'\x00\x00\x00\x00IEND\xaeB`\x82'
    assert data[12:16] == b'IHDR'
    return struct.unpack('>II', data[16:24])


def test_help_exact_and_no_args(tmp_path):
    a = run(tmp_path)
    b = run(tmp_path, '--help')
    assert a.returncode == b.returncode == 0
    assert a.stdout == b.stdout and a.stderr == b.stderr == b''
    assert a.stdout.startswith(b'usage: java -jar ditaa.jar')
    assert b'--svg-font-url' in a.stdout


def test_unknown_option_and_missing_value_show_usage(tmp_path):
    for args, needle in [(['--not-an-option'], b'Unrecognized option'), (['-s'], b'')]:
        r = run(tmp_path, *args)
        assert r.returncode == 2
        assert b'usage: java -jar ditaa.jar' in r.stdout
        if needle:
            assert needle in r.stderr


@pytest.mark.parametrize('args,value', [(['--scale', 'oops'], b'oops'), (['--tabs', 'x'], b'x')], ids=['bad-scale','bad-tabs'])
def test_bad_numeric_option(tmp_path, args, value):
    r = run(tmp_path, *args)
    assert r.returncode == 2
    assert b'Error: For input string: "' + value + b'"' in r.stderr
    assert b'usage:' in r.stdout


def test_background_and_encoding_validation(tmp_path):
    for value in ['12345', '1234567']:
        r = run(tmp_path, '-b', value)
        assert r.returncode == 2
        assert f'Cannot interpret "{value}" as background colour'.encode() in r.stderr
        assert b'usage:' in r.stdout
    r = run(tmp_path, '-b', 'GGGGGG')
    assert r.returncode == 2 and b'Error: For input string: "GGGGGG"' in r.stderr
    r = run(tmp_path, '--encoding', 'not-an-encoding')
    assert r.returncode == 2 and r.stdout == b''
    assert r.stderr == b'Error: not-an-encoding\n'


def test_default_output_png_banner_and_auto_name(tmp_path):
    src = put(tmp_path, 'a.b diagram.TXT', 'hello\n')
    r = run(tmp_path, src)
    assert r.returncode == 0
    out = tmp_path / 'a.b diagram.png'
    assert png_info(out.read_bytes()) == (90, 70)
    assert b'\nditaa version 0.11' in r.stdout
    assert b'Reading file: ' + str(src).encode() in r.stdout
    assert b'Rendering to file: ' + str(out).encode() in r.stdout
    assert b'Done in ' in r.stdout


def test_png_bytes_independent_of_destination_extension(tmp_path):
    src = put(tmp_path, 'in', 'hello')
    one, two = tmp_path/'one.jpg', tmp_path/'two.png'
    assert run(tmp_path, src, one).returncode == 0
    assert run(tmp_path, src, two).returncode == 0
    assert png_info(one.read_bytes()) == png_info(two.read_bytes())
    assert one.read_bytes() == two.read_bytes()


def test_stdout_png_and_debug_prefix(tmp_path):
    r = run(tmp_path, '-', '-', data=b'hello')
    assert r.returncode == 0 and r.stderr == b''
    assert png_info(r.stdout) == (90, 70)
    assert b'ditaa version' not in r.stdout
    d = run(tmp_path, '-', '-', '-S', '--debug', data=b'hello')
    prefix = b'    0123456789\n 0 (         )\n 1 (         )\n 2 (  hello  )\n 3 (         )\n 4 (         )\n'
    assert d.returncode == 0 and d.stdout.startswith(prefix + b'\x89PNG')


def test_empty_whitespace_and_separator_only_inputs(tmp_path):
    for name, data in [('empty', b''), ('spaces', b'   \n')]:
        src = put(tmp_path, name, data)
        r = run(tmp_path, src, tmp_path/(name+'.png'))
        assert r.returncode == 0
        assert png_info((tmp_path/(name+'.png')).read_bytes())[0] > 0
    src = put(tmp_path, 'seps', '\n\r\n')
    r = run(tmp_path, src, tmp_path/'bad.png')
    assert r.returncode != 0 and r.stdout == b''
    assert b'IndexOutOfBoundsException: toIndex = 1' in r.stderr
    assert b'TextGrid.initialiseWithLines' in r.stderr
    assert not (tmp_path/'bad.png').exists()


def test_auto_collision_numbering_and_overwrite(tmp_path):
    src = put(tmp_path, 'name.txt', 'hello')
    base = tmp_path/'name.png'
    base.write_bytes(b'keep')
    r = run(tmp_path, src)
    assert r.returncode == 0 and (tmp_path/'name_2.png').exists()
    before = base.stat().st_mtime_ns
    r = run(tmp_path, src, '--overwrite')
    assert r.returncode == 0 and png_info(base.read_bytes()) == (90, 70)
    assert base.stat().st_mtime_ns >= before


def test_missing_input_and_write_error(tmp_path):
    missing = tmp_path/'missing'
    r = run(tmp_path, missing)
    assert r.returncode == 1 and f'Error: File {missing} does not exist'.encode() in r.stderr
    src = put(tmp_path, 'input', 'x')
    r = run(tmp_path, src, '/dev/null/output.png')
    assert r.returncode == 1 and b'Cannot write to file /dev/null/output.png' in r.stderr


def test_scale_dimensions_and_fractional_options(tmp_path):
    src = put(tmp_path, 'box', '+----+\n|    |\n+----+')
    for scale, dims in [('1', (100,98)), ('2', (200,196)), ('0.5', (50,49)), ('10', (1000,980))]:
        out = tmp_path/('s'+scale+'.png')
        r = run(tmp_path, src, out, '--scale', scale, '-S')
        assert r.returncode == 0 and png_info(out.read_bytes()) == dims


def test_tiny_scale_and_nonpositive_scale_fail(tmp_path):
    src = put(tmp_path, 'text', 'hello')
    for scale in ['0.1', '0', '-1']:
        r = run(tmp_path, src, tmp_path/(scale.replace('-', 'm')+'.png'), '--scale', scale)
        assert r.returncode != 0 and b'FontMeasurer.getWidthFor' in r.stderr


def test_options_order_independent_transparency_and_verbose(tmp_path):
    src = put(tmp_path, 'input', 'x')
    outputs=[]
    for args in [('--background','FF000080','--transparent'),('--transparent','--background','FF000080')]:
        out=tmp_path/('out'+str(len(outputs))+'.png')
        r=run(tmp_path,src,out,*args,'--verbose')
        assert r.returncode==0 and b'verbose' in r.stdout
        outputs.append(out.read_bytes())
    assert outputs[0]==outputs[1]
    assert outputs[0][25] == 6  # color type RGBA
    assert outputs[0][24] == 8


def test_background_rgb_and_alpha_png_modes(tmp_path):
    src=put(tmp_path,'i','x')
    for color, ctype in [('FF0000',2),('FF000080',6)]:
        out=tmp_path/(color+'.png')
        assert run(tmp_path,src,out,'-b',color,'-S').returncode==0
        dat=out.read_bytes()
        assert dat[25]==ctype


def test_svg_well_formed_skeleton_and_scaling(tmp_path):
    src=put(tmp_path,'input','hello')
    out=tmp_path/'x.svg'
    r=run(tmp_path,src,out,'--svg','--no-shadows')
    assert r.returncode==0
    dat=out.read_bytes()
    assert dat.endswith(b'</svg>') and not dat.endswith(b'\n')
    root=ET.fromstring(dat)
    assert root.tag.endswith('svg') and root.attrib['width']=='90' and root.attrib['height']=='70'
    assert 'viewBox' not in root.attrib
    assert b'<![CDATA[hello]]>' in dat


def test_svg_option_independent_of_no_shadows_and_font_url(tmp_path):
    src=put(tmp_path,'input','A')
    out=tmp_path/'x.svg'
    r=run(tmp_path,'--svg-font-url','https://font/x',src,out,'--svg','-S')
    assert r.returncode==0
    dat=out.read_bytes()
    assert b'@font-face' in dat and b"src: url('https://font/x')" in dat
    assert b"font-family='Custom'" in dat
    fast=tmp_path/'fast.svg'
    assert run(tmp_path,src,fast,'--svg','-A').returncode==0
    assert b"shape-rendering='optimizeSpeed'" in fast.read_bytes()


def test_debug_file_grid_and_option_order_lines(tmp_path):
    src=put(tmp_path,'input','x')
    out=tmp_path/'out.png'
    r=run(tmp_path,'--scale','2.0',src,'-v',out,'--debug')
    assert r.returncode==0
    assert b'scale = 2.0' in r.stdout and b'verbose' in r.stdout
    assert b'Using grid:\n    0123456789' in r.stdout


def test_tabs_and_negative_tabs(tmp_path):
    src=put(tmp_path,'tab','a\tb')
    for width in ['2','4','8','16','100','-2']:
        out=tmp_path/(width.replace('-','m')+'.png')
        r=run(tmp_path,src,out,'--tabs',width)
        assert r.returncode==0


def test_unicode_and_utf8_encoding(tmp_path):
    src=put(tmp_path,'unicode','café 漢字 😀')
    out=tmp_path/'u.svg'
    r=run(tmp_path,src,out,'--svg','--encoding','UTF-8')
    assert r.returncode==0
    assert 'café 漢字 😀'.encode() in out.read_bytes()


def test_round_corners_no_separation_flags_are_accepted(tmp_path):
    src=put(tmp_path,'box','+--+\n|  |\n+--+')
    for flag in ['-r','-E','-W','-A','-S','-T']:
        out=tmp_path/(flag[1:]+'.png')
        r=run(tmp_path,src,out,flag)
        assert r.returncode==0 and png_info(out.read_bytes())[0] > 0


def test_isolated_arrow_svg_triangle_and_lone_tilde_text(tmp_path):
    src=put(tmp_path,'arrow','>')
    out=tmp_path/'arrow.svg'
    assert run(tmp_path,src,out,'--svg').returncode==0
    assert b"M20.0 28.0 L30.0 35.0 L20.0 42.0 z" in out.read_bytes()
    src=put(tmp_path,'tilde','~')
    out=tmp_path/'tilde.svg'
    assert run(tmp_path,src,out,'--svg').returncode==0
    assert b'<![CDATA[~ ]]>' in out.read_bytes()


def test_html_conversion_selected_pre_and_default_names(tmp_path):
    src=put(tmp_path,'page.html','<!doctype html><html><head><meta charset="UTF-8"></head><body><h1>Hi</h1><pre>keep</pre><pre class="other">x</pre><pre class="textdiagram">+--+\n|hi|\n+--+</pre><pre class="textdiagram">x</pre></body></html>')
    r=run(tmp_path,src,'--html')
    out=tmp_path/'page_processed.html'
    assert r.returncode==0 and out.exists()
    text=out.read_text()
    assert '<pre>keep</pre>' in text and '<pre class="other">x</pre>' in text
    assert 'images/ditaa_diagram_1.png' in text and 'images/ditaa_diagram_2.png' in text
    assert (tmp_path/'images/ditaa_diagram_1.png').exists()
    assert b'Converting HTML file' in r.stdout and b'...done' in r.stdout


def test_html_ids_svg_extension_and_empty_selected_pre(tmp_path):
    src=put(tmp_path,'p.html','<pre class="textdiagram" id="a b"> </pre><pre class="textdiagram" id="">x</pre><pre class="textdiagram"> </pre>')
    r=run(tmp_path,src,tmp_path/'out.html','--html','--svg')
    assert r.returncode==0
    h=(tmp_path/'out.html').read_text()
    assert 'images/a_b.svg' in h and 'images/.svg' in h and 'images/ditaa_diagram_1.svg' in h
    assert (tmp_path/'images/a_b.svg').exists() and (tmp_path/'images/.svg').exists()


def test_html_no_diagrams_and_empty_document(tmp_path):
    for name,content in [('none.html','<p>nothing</p>'),('empty.html','')]:
        src=put(tmp_path,name,content)
        r=run(tmp_path,src,'--html')
        assert r.returncode==0
        assert b'does not contain any <pre> tags' in r.stdout
        assert not (tmp_path/(Path(name).stem+'_processed.html')).exists()
    assert not (tmp_path/'images').exists()


def test_html_missing_input_exit_zero_and_existing_output_protected(tmp_path):
    missing=tmp_path/'missing.html'
    r=run(tmp_path,missing,'--html')
    assert r.returncode==0 and b'cannot read file' in r.stderr
    src=put(tmp_path,'source.html','<pre class="textdiagram">x</pre>')
    out=put(tmp_path,'already.html','old')
    r=run(tmp_path,src,out,'--html')
    assert r.returncode==0 and out.read_text()=='old'
    assert b'--overwrite' in r.stdout or b'--overwrite' in r.stderr


def test_html_image_collision_continues_and_overwrite(tmp_path):
    src=put(tmp_path,'in.html','<pre class="textdiagram" id="same">one</pre><pre class="textdiagram">two</pre>')
    images=tmp_path/'images'; images.mkdir(); (images/'same.png').write_bytes(b'old')
    r=run(tmp_path,src,tmp_path/'out.html','--html')
    assert r.returncode==0 and b'Cannot overwrite file images/same.png' in r.stdout+r.stderr
    assert (images/'ditaa_diagram_1.png').exists() and (images/'same.png').read_bytes()==b'old'
    r=run(tmp_path,src,tmp_path/'out2.html','--html','--overwrite')
    assert r.returncode==0 and png_info((images/'same.png').read_bytes())[0]>0


def test_html_whitespace_id_name_and_malformed_recovery(tmp_path):
    src=put(tmp_path,'in.html','<pre class="textdiagram" id="   ">x<pre class="textdiagram">')
    r=run(tmp_path,src,tmp_path/'o.html','--html')
    assert r.returncode==0
    assert (tmp_path/'images'/'___.png').exists()
    assert (tmp_path/'images'/'ditaa_diagram_1.png').exists()


def test_java_stringutils_entrypoint(tmp_path):
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.text.StringUtils'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    expected=('1 Testing\n2  testing\n3 _testing\n4 Testing\n5 Ttesting\nC:\\Files\\test.txt\nC:\\Files\ntest\ntxt\ntest.txt\n\ntest.txt\ntxt\ntest\npath: \nbase: test\n ext: \n').encode()
    assert r.returncode==0 and r.stderr==b'' and r.stdout==expected


def test_java_configuration_parser_valid_and_missing(tmp_path):
    p=tmp_path/'asset.svg'; p.write_text('<svg/>')
    (tmp_path/'config.xml').write_text('<shapes dir="."><shape tag="cust" filename="asset.svg" stretch="yes" border="1" shadow="false"/></shapes>')
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.core.ConfigurationParser'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert r.returncode==0 and r.stdout==r.stderr==b''
    (tmp_path/'config.xml').unlink()
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.core.ConfigurationParser'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert r.returncode!=0 and b'FileNotFoundException' in r.stderr and b'config.xml (No such file or directory)' in r.stderr


def test_java_missing_crimson_driver(tmp_path):
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.core.DocBookConverter'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert r.returncode!=0 and b'ClassNotFoundException' in r.stderr
    assert b'SAX2 driver class org.apache.crimson.parser.XMLReaderImpl not found' in r.stderr


def test_java_image_handler_echoes_svg_then_missing_driver(tmp_path):
    svg='<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg"><circle cx="50" cy="50" r="40" fill="blue"/></svg>'
    (tmp_path/'sphere.svg').write_text(svg)
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.graphics.ImageHandler'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert r.returncode!=0 and b'ClassNotFoundException' in r.stderr
    assert b'SAX2 driver class org.apache.xerces.parsers.SAXParser not found' in r.stderr
    assert b'<?xml' in r.stdout and b'<svg xmlns="http://www.w3.org/2000/svg"' in r.stdout and b'<circle cx="50"' in r.stdout


def test_performance_tester_runtime_and_output(tmp_path):
    p=tmp_path/'tests/text'; p.mkdir(parents=True)
    (p/'ditaa_bug.txt').write_text('+--+\n|x |\n+--+')
    r=subprocess.run(['java','-cp',str(EXE),'org.stathissideris.ascii2image.core.PerformanceTester'],cwd=tmp_path,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=10)
    assert r.returncode==0
    for i in range(30): assert f'iteration {i}'.encode() in r.stdout
    assert re.search(rb'\d+msec for 30 iterations on tests/text/ditaa_bug\.txt',r.stdout)
    assert r.stdout.rstrip().endswith(b'Tests completed')
