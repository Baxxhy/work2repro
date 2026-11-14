import os
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, input_data='', cwd=None):
    return subprocess.run([str(EXE), *map(str, args)], input=input_data.encode('utf-8'),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          cwd=cwd or '/workspace', timeout=20)


def test_version_exact():
    p = run('--version')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'htmlq 0.4.0', b'')


def test_help_shape_and_priority():
    p = run('--help')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'htmlq 0.4.0\nMichael Maclean <michael@mgdm.net>\nRuns CSS selectors on HTML\n\nUSAGE:')
    assert p.stdout.endswith(b'<selector>...    The CSS expression to select [default: html]\n')
    assert run('--help', '--unknown').returncode == 0
    bad = run('--unknown', '--help')
    assert bad.returncode == 1 and bad.stdout == b'' and b"Found argument '--unknown'" in bad.stderr and b'USAGE:' in bad.stderr


def test_default_and_html5_empty_and_fragment():
    assert run(input_data='').stdout == b'<html><head></head><body></body></html>\n'
    assert run(input_data='just plain text').stdout == b'<html><head></head><body>just plain text</body></html>\n'
    assert run('div', input_data='<div>x</div>').stdout == b'<div>x</div>\n'


def test_selector_tokens_join_and_selector_lists_dedupe_order():
    src = '<p class="a">P</p><span class="b">S</span><p><span>X</span></p>'
    assert run('p', 'span', input_data=src).stdout == b'<span>X</span>\n'
    assert run('span, p', input_data=src).stdout == b'<p class="a">P</p>\n<span class="b">S</span>\n<p><span>X</span></p>\n<span>X</span>\n'
    assert run('.a', '.b', input_data='<i class="a"></i><b class="b"></b>').stdout == b''


def test_types_classes_ids_and_attribute_operators():
    src = '<x-card id="main" class="item featured" data-x="alpha beta" lang="en-US" title="A.B/c_d" FLAG=""/><x-card title="TEST"/>'
    assert run('x-card.item#main.featured[data-x][data-x~="alpha"][lang|="en"][title*="B/c_d"][flag]', input_data=src).stdout == b'<x-card class="item featured" data-x="alpha beta" id="main" lang="en-US" title="A.B/c_d" flag=""></x-card>\n'
    assert run('x-card[title="test" i]', input_data=src).stdout.endswith(b'title="TEST"></x-card>\n')
    for selector, expected in [('[data-x^="alpha"]', 1), ('[data-x$="beta"]', 1), ('[title="A.B/c_d"]', 1), ('[lang|="en"]', 1)]:
        assert run(selector, input_data=src).stdout.count(b'\n') == expected


def test_combinators_and_structure_pseudos():
    src = '<main><h1>H</h1><p id="a">A</p><p class="skip">B</p><section><p id="deep">D</p></section></main>'
    assert run('main > h1 + p', input_data=src).stdout == b'<p id="a">A</p>\n'
    assert run('h1 ~ p', input_data=src).stdout.count(b'<p') == 2
    assert run('section p#deep', input_data=src).stdout == b'<p id="deep">D</p>\n'
    assert run('p:first-child', input_data='<div><p>x</p><p>y</p></div>').stdout == b'<p>x</p>\n'
    assert run('p:nth-child(2n+1)', input_data='<div><p>1</p><p>2</p><p>3</p></div>').stdout.count(b'<p>') == 2
    assert run('p:not(.skip)', input_data=src).stdout == b'<p id="a">A</p>\n<p id="deep">D</p>\n'
    assert run('input:disabled', input_data='<input disabled>').stdout == b''


def test_html5_recovery_serialization_and_ordered_attributes():
    assert run(input_data='<input id="email" type="email" name="email" required>').stdout == b'<html><head></head><body><input id="email" name="email" required="" type="email"></body></html>\n'
    assert run('p', input_data='<p>one<p>two').stdout == b'<p>one</p>\n<p>two</p>\n'
    assert run('div', input_data='<div><p>Text &amp; more</p><!--c--></div>').stdout == b'<div><p>Text &amp; more</p><!--c--></div>\n'
    assert run('br', input_data='<br/>').stdout == b'<br>\n'


def test_attribute_mode_empty_decoding_and_precedence():
    src = '<a href="/one">1</a><a>2</a><a href="">3</a><i title="Test &quot;quotes&quot;" class="a b"></i>'
    assert run('-a', 'href', 'a', input_data=src).stdout == b'/one\n\n'
    assert run('--attribute=title', 'i', input_data=src).stdout == b'Test "quotes"\n'
    assert run('--attribute=', 'i', input_data=src).stdout == b''
    assert run('-a', 'href', '-t', 'a', input_data=src).stdout == b'/one\n\n'


def test_text_mode_descendant_whitespace_and_modes():
    src = '<div>  <p>Text &lt; <b>World&amp;</b></p>  </div><div><br><!--x--></div>'
    assert run('-t', 'div', input_data=src).stdout == b'  Text < World&  \n\n'
    assert run('-tw', 'div', input_data=src).stdout == b'Text < \nWorld&\n\n\n'
    assert run('-t', '-p', 'p', input_data='<p>A<b>B</b></p>').stdout == b'AB\n'
    assert run('-w', 'p', input_data='<p>A</p>').stdout == b'<p>A</p>\n'
    assert run('-t', 'p', input_data='<p></p>').stdout == b'\n'


def test_pretty_mode_exact_streaming_example():
    expected = b'\n<div>\n  <p>Hello\n  </p>\n  <p>\n    World\n  </p>\n</div>\n'
    assert run('-p', 'div', input_data='<div><p>Hello</p><p>World</p></div>').stdout == expected
    assert run('-a', 'id', '-p', 'p', input_data='<p id="x">X</p>').stdout == b'x\n'


def test_removal_prefix_stop_and_repeat_invalid():
    src = '<div class="item"><p>1</p></div><div class="item ad"><p>2</p></div><div class="item"><p>3</p></div>'
    assert run('.item', '--remove-nodes', '.ad', input_data=src).stdout == b'<div class="item"><p>1</p></div>\n'
    assert run('.item', '-r', '.none', '-r', '.ad', input_data=src).stdout == b'<div class="item"><p>1</p></div>\n'
    assert run('.item', '-r', '[', input_data=src).stdout.count(b'<div') == 3
    assert run('.item', '-r', '.item', input_data=src).stdout == b''


def test_base_url_resolution_and_rewrite_scope():
    src = '<base href="https://example.test/a/b"><div><a href="../x">x</a><img src="p"><span href="q">s</span></div><a href="////example.com/path">z</a>'
    assert run('--detect-base', 'a', input_data=src).stdout == b'<a href="https://example.test/x">x</a>\n<a href="example.com/path">z</a>\n'
    assert run('--base', 'https://h.test/a/', '-a', 'href', 'a', input_data='<a href="x">x</a><a href="/y">y</a>').stdout == b'https://h.test/a/x\nhttps://h.test/y\n'
    assert run('--base', 'https://h.test/', 'div', input_data=src).stdout.startswith(b'<div><a href="../x">')
    assert run('--base', 'https://h.test/', '-t', 'a', input_data='<a href="x">T</a>').stdout == b'T\n'


def test_file_input_output_and_stdin_dash(tmp_path):
    inp = tmp_path / 'input unicode.html'
    out = tmp_path / 'output unicode.txt'
    inp.write_text('<p>file</p>', encoding='utf-8')
    p = run('-f', inp, 'p', input_data='stdin')
    assert p.stdout == b'<p>file</p>\n'
    p = run('--filename=-', 'p', input_data='<p>dash</p>')
    assert p.stdout == b'<p>dash</p>\n'
    p = run('-f', inp, '-o', out, '-t', 'p', input_data='ignored')
    assert p.returncode == 0 and p.stdout == b'' and out.read_bytes() == b'file\n'
    assert run('-o', '-', '-t', 'p', input_data='<p>stdout</p>').stdout == b'stdout\n'


def test_utf8_replacement_and_large_match_set():
    p = subprocess.run([str(EXE), '-t', 'p'], input=b'<p>\xff</p>', stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    assert p.returncode == 0 and p.stdout == '�\n'.encode()
    html = '<p>x</p>' * 10000
    p = run('p', input_data=html)
    assert p.returncode == 0 and p.stdout.count(b'<p>x</p>\n') == 10000


def test_cli_errors_and_fatal_errors(tmp_path):
    for option in ('-a', '-b', '-f', '-o', '-r'):
        p = run(option)
        assert p.returncode == 1 and p.stdout == b'' and b'requires a value' in p.stderr and b'USAGE:' in p.stderr
    repeated = run('--attribute', 'id', '--attribute', 'class')
    assert repeated.returncode == 1 and b"provided more than once" in repeated.stderr
    missing = run('-f', tmp_path / 'absent')
    assert missing.returncode == 101 and missing.stdout == b'' and b'panicked' in missing.stderr and b'No such file or directory' in missing.stderr
    invalid = run('[', input_data='<p>x</p>')
    assert invalid.returncode == 101 and invalid.stdout == b'' and b'panicked at src/main.rs' in invalid.stderr and b'Failed to parse CSS selector' in invalid.stderr
    out = run('-o', tmp_path / 'missing' / 'out', input_data='<p>x</p>')
    assert out.returncode != 0 and out.stdout == b'' and b'panicked' in out.stderr


def test_option_placement_combined_short_flags_and_end_of_options():
    src = '<p id="x">  A <b>B</b>  </p>'
    assert run('p', '-t', input_data=src).stdout == b'  A B  \n'
    assert run('-wt', 'p', input_data=src).stdout == b'  A \nB\n\n'
    assert run('--', '-x', input_data='<div class="-x">ok</div>').returncode == 0
    assert run('-f-', 'p', input_data='<p>short attached</p>').stdout == b'<p>short attached</p>\n'
