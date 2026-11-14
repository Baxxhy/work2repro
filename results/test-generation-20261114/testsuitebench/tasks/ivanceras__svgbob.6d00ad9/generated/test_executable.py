import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable')
SVG = '{http://www.w3.org/2000/svg}'


def run(*args, data=None, cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd or EVAL)


def converted(text, *opts):
    p = run(*opts, '-s', text)
    assert p.returncode == 0, p.stderr
    assert p.stderr == ''
    assert p.stdout.endswith('\n')
    doc = p.stdout[:-1]
    root = ET.fromstring(doc)
    assert root.tag == SVG + 'svg'
    return doc, root


def texts(root):
    return [(e.attrib.get('x'), e.attrib.get('y'), e.text or '')
            for e in root.iter(SVG + 'text')]


def shapes(root, tag):
    return [e for e in root.iter(SVG + tag) if 'backdrop' not in e.attrib.get('class', '')]


def test_version_and_help():
    for arg in ('-V', '--version'):
        p = run(arg)
        assert (p.returncode, p.stdout, p.stderr) == (0, 'svgbob 0.7.6\n', '')
    for arg in ('-h', '--help'):
        p = run(arg)
        assert p.returncode == 0 and 'svgbob 0.7.6' in p.stdout and 'SUBCOMMANDS:' in p.stdout


def test_empty_is_exact_canonical_document():
    p = run(data='')
    assert p.returncode == 0 and p.stderr == ''
    root = ET.fromstring(p.stdout)
    assert root.attrib == {'width': '16', 'height': '32', 'class': 'svgbob'}
    assert p.stdout.endswith('</svg>\n')
    assert p.stdout.count('<svg ') == 1 and p.stdout.count('</svg>') == 1
    assert '<style>.svgbob line, .svgbob path' in p.stdout
    assert 'font-family: Iosevka Fixed, monospace;' in p.stdout
    assert '<defs>' in p.stdout and '<rect class="backdrop" x="0" y="0" width="16" height="32"></rect>' in p.stdout
    assert '/>' not in p.stdout


def test_stdin_file_and_inline_inputs_match(tmp_path):
    source = 'hello\nworld'
    f = tmp_path / 'in.bob'
    f.write_text(source)
    by_stdin = run(data=source)
    by_file = run(str(f))
    by_inline = run('-s', r'hello\nworld')
    assert by_stdin.returncode == by_file.returncode == by_inline.returncode == 0
    assert by_stdin.stdout == by_file.stdout == by_inline.stdout


@pytest.mark.parametrize('line_ending', ['lf', 'crlf', 'mixed'], ids=['lf', 'crlf', 'mixed'])
def test_newline_normalization_and_final_blank_lines(line_ending):
    variants = {'lf': 'A\nB', 'crlf': 'A\r\nB', 'mixed': 'A\rB'}
    doc, root = converted(variants[line_ending])
    assert texts(root) == [('2', '12', 'A'), ('2', '28', 'B')]
    assert '\r' not in doc
    d2, _ = converted('A\nB\n\n')
    d3, _ = converted('A\nB')
    assert d2 == d3


def test_missing_file_and_output_errors(tmp_path):
    missing = tmp_path / 'missing.bob'
    p = run(str(missing))
    assert p.returncode == 1 and str(missing) in p.stderr and 'No such file or directory' in p.stderr
    badout = tmp_path / 'absent' / 'x.svg'
    p = run('-s', 'A', '-o', str(badout))
    assert p.returncode == 2 and p.stdout == '' and 'Failed to write to output file' in p.stderr
    assert str(badout) in p.stderr


def test_output_file_has_no_trailing_newline_and_matches_stdout(tmp_path):
    target = tmp_path / 'out.svg'
    p = run('-s', 'A', '-o', target)
    q = run('-s', 'A')
    assert p.returncode == 0 and p.stdout == p.stderr == ''
    assert target.read_bytes() == q.stdout.encode()[:-1]
    target.write_text('old')
    assert run('-s', 'B', '--output', target).returncode == 0
    assert 'B</text>' in target.read_text()


@pytest.mark.parametrize('value,expected', [
    ('transparent', 'transparent'), ('#abc', '#abc'), ('#123456', '#123456'),
    ('rgb(1, 2, 3)', 'rgb(1, 2, 3)')], ids=['transparent', 'short-hex', 'long-hex', 'rgb'])
def test_colors_interpolated_verbatim(value, expected):
    doc, _ = converted('', '--background', value, '--fill-color', value, '--stroke-color', value)
    assert f'fill: {expected};' in doc and f'stroke: {expected};' in doc


def test_css_settings_font_family_numeric_and_scale():
    doc, root = converted('A', '--stroke-width', '1.5', '--font-size', '23',
                          '--font-family', 'My Font, monospace', '--scale', '2')
    assert 'stroke-width: 1.5;' in doc and 'font-size: 23px;' in doc
    assert 'font-family: My Font, monospace;' in doc
    assert root.attrib['width'] == '32' and root.attrib['height'] == '64'
    assert texts(root) == [('4', '24', 'A')]
    doc, root = converted('A', '--scale', '0.5')
    assert root.attrib['width'] == '8' and texts(root) == [('1', '6', 'A')]


@pytest.mark.parametrize('opt,value,detail', [
    ('--font-size', 'nope', 'invalid digit found in string'),
    ('--stroke-width', 'nope', ''), ('--scale', 'nope', '')], ids=['font-size', 'stroke-width', 'scale'])
def test_invalid_numeric_values(opt, value, detail):
    p = run('-s', 'x', opt, value)
    assert p.returncode == 1 and 'Illegal value for argument' in p.stderr
    assert opt.removeprefix('--') in p.stderr
    if detail:
        assert detail in p.stderr


def test_text_coordinates_whitespace_and_bounds():
    _, root = converted('  hello world\nagain')
    assert root.attrib['width'] == '112' and root.attrib['height'] == '64'
    assert texts(root) == [('18', '12', 'hello'), ('2', '28', 'again'), ('66', '12', 'world')]
    _, root = converted('A   \t')
    assert root.attrib['width'] == '16' and texts(root) == [('2', '12', 'A')]
    _, root = converted('\nA')
    assert texts(root) == [('2', '28', 'A')]


def test_text_escaping_quoted_runs_and_unicode_width():
    _, root = converted('&<>\'"')
    assert texts(root) == [('2', '12', '&<>\'"')]
    doc, root = converted('"-- hi"')
    assert 'width="16" height="32"' in doc
    assert texts(root) == [('2', '12', '-- hi')]
    _, root = converted('界A')
    assert texts(root) == [('2', '12', '界A')]


def test_line_merge_broken_and_geometry():
    _, root = converted('---')
    lines = shapes(root, 'line')
    assert len(lines) == 1 and lines[0].attrib == {'x1': '0', 'y1': '8', 'x2': '24', 'y2': '8', 'class': 'solid'}
    _, root = converted('~~-')
    assert any(e.attrib.get('class') == 'broken' for e in shapes(root, 'line'))
    _, root = converted('│')
    assert any(e.attrib.get('x1') == '4' and e.attrib.get('y1') == '0' and e.attrib.get('y2') == '16' for e in shapes(root, 'line'))


def test_rectangles_and_rounded_rectangles():
    _, root = converted('+-----+\n|     |\n+-----+')
    rects = shapes(root, 'rect')
    assert len(rects) == 1
    assert rects[0].attrib == {'x': '4', 'y': '8', 'width': '48', 'height': '32', 'class': 'solid nofill', 'rx': '0'}
    _, root = converted('.-----.\n|     |\n\'-----\'')
    assert any(e.attrib.get('rx') == '4' for e in shapes(root, 'rect'))


def test_circles_and_hash_fill():
    _, root = converted('()')
    assert any(e.attrib == {'cx': '8', 'cy': '8', 'r': '4', 'class': 'nofill'} for e in shapes(root, 'circle'))
    _, root = converted('##')
    rects = shapes(root, 'rect')
    assert any(e.attrib.get('class') == 'solid filled' for e in rects)
    _, root = converted('#\n#')
    assert not any(e.attrib.get('class') == 'solid filled' for e in shapes(root, 'rect'))
    assert len(texts(root)) == 2


def test_arrowheads_and_endpoint_markers():
    _, root = converted('--->')
    assert shapes(root, 'polygon')
    _, root = converted('---o')
    assert any('end_marked_open_circle' in e.attrib.get('class', '') for e in shapes(root, 'line'))
    _, root = converted('')
    assert all(not e.attrib.get('class', '').startswith(('end_marked', 'start_marked')) for e in shapes(root, 'line'))


def test_unicode_shapes_and_double_tracks():
    _, root = converted('┌─┐\n│ │\n└─┘')
    assert len(shapes(root, 'rect')) == 1
    _, root = converted('╔═╗\n║ ║\n╚═╝')
    assert len(shapes(root, 'rect')) == 2
    _, root = converted('▲')
    assert shapes(root, 'polygon')


def test_legend_and_shape_class_markers():
    doc, _ = converted('A\n# Legend:\nbox1={fill:red;}\nmy_2={stroke:blue;}')
    assert '.svgbob .box1{ fill:red; }' in doc
    assert '.svgbob .my_2{ stroke:blue; }' in doc
    assert 'Legend' not in doc
    _, root = converted('+---+\n|{foo}|\n+---+')
    assert any('foo' in e.attrib.get('class', '') for e in shapes(root, 'rect'))


def test_many_rows_columns_and_text_nodes():
    data = '\n'.join('x' for _ in range(35))
    _, root = converted(data)
    assert root.attrib['height'] == '592'
    assert len(texts(root)) == 35
    long_row = 'x' * 220
    _, root = converted(long_row)
    assert len(texts(root)) == 1 and root.attrib['width'] == '1768'


def test_build_help_version_and_no_input(tmp_path):
    h = run('build', '--help')
    assert h.returncode == 0 and 'Batch convert files to svg.' in h.stdout
    v = run('build', '--version')
    assert (v.returncode, v.stdout, v.stderr) == (0, 'executable-build 0.0.1\n', '')
    (tmp_path / 'x.bob').write_text('x')
    p = run('build', cwd=tmp_path)
    assert p.returncode == 1 and p.stdout == '[Error]: No such dir name is  !\n' and p.stderr == ''


def test_build_extension_selection_outdir_and_exit_contract(tmp_path):
    (tmp_path / 'one.bob').write_text('A')
    (tmp_path / 'my.file.v2.bob').write_text('B')
    (tmp_path / 'note.txt').write_text('C')
    (tmp_path / 'nested').mkdir()
    p = run('build', '-i', str(tmp_path / '*.bob'), '-o', str(tmp_path / 'new' / 'deep'), cwd=tmp_path)
    assert p.returncode == 1 and p.stderr == ''
    assert len([x for x in (tmp_path / 'new' / 'deep').glob('*.svg')]) == 2
    assert (tmp_path / 'new' / 'deep' / 'my.file.v2.svg').exists()
    assert '=>' in p.stdout
    q = run('build', '--input', str(tmp_path / '*.txt'), cwd=tmp_path)
    assert q.returncode == 1 and (tmp_path / 'note.svg').exists()


def test_build_explicit_file_selects_extension_and_does_not_recurse(tmp_path):
    (tmp_path / 'choose.bob').write_text('a')
    (tmp_path / 'other.bob').write_text('b')
    sub = tmp_path / 'sub'
    sub.mkdir()
    (sub / 'deep.bob').write_text('c')
    p = run('build', '-i', tmp_path / 'choose.bob', cwd=tmp_path)
    assert p.returncode == 1
    assert (tmp_path / 'choose.svg').exists() and (tmp_path / 'other.svg').exists()
    assert not (sub / 'deep.svg').exists()
