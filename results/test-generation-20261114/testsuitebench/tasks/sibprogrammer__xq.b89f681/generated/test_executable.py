import json
import os
import re
import subprocess
from pathlib import Path

import pytest

EXE = Path('/workspace/executable')


def run(*args, data=None, home=None):
    env = os.environ.copy()
    if home is not None:
        env['HOME'] = str(home)
        env.pop('XDG_CONFIG_HOME', None)
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=env, timeout=10)


def txt(p):
    return p.stdout.decode('utf-8', 'replace')


def test_help_exact_and_precedence():
    p = run('--help', '--json')
    expected = '''Command-line XML and HTML beautifier and content extractor

Usage:
  xq [flags]

Flags:
  -a, --attr string      Extract an attribute value instead of node content for provided CSS query
  -c, --color            Force colorful output
      --compact          Compact JSON output (no indentation)
  -d, --depth int        Maximum nesting depth for JSON output (-1 for unlimited) (default -1)
  -e, --extract string   Extract a single node from XML
  -h, --help             Print this help message
  -m, --html             Use HTML formatter
  -i, --in-place         Format file in place
      --indent int       Use the given number of spaces for indentation (default 2)
  -j, --json             Output the result as JSON
      --no-color         Disable colorful output
  -n, --node             Return the node content instead of text
  -q, --query string     Extract the node(s) using CSS selector
      --tab              Use tabs for indentation
  -v, --version          Print version information
  -x, --xpath string     Extract the node(s) from XML
'''
    assert p.returncode == 0 and p.stdout.decode() == expected and p.stderr == b''


def test_version_exact():
    p = run('-v')
    assert (p.returncode, p.stdout, p.stderr) == (0, b'xq version 1.4.0\n', b'')


@pytest.mark.parametrize('args,needle', [(['--bogus'], 'unknown flag'), (['--indent'], 'flag needs an argument'),
    (['--indent', 'wat'], 'Error:'), (['--compact=maybe'], 'Error:'), (['--indent', '9'], 'indent should be between 0-8 spaces')],
    ids=['unknown-flag','missing-value','bad-indent','bool-value','indent-range'])
def test_argument_errors(args, needle):
    p = run(*args, data=b'<r/>')
    assert p.returncode != 0 and 'Error:' in txt(p) + p.stderr.decode('utf8','replace')
    assert needle in (txt(p) + p.stderr.decode('utf8','replace'))


def test_xml_pretty_compact_indent_tab():
    data = b'<root>\n <child>text</child>\n</root>'
    assert run(data=data).stdout == b'<root>\n  <child>text</child>\n</root>\n'
    assert run('--indent', '0', data=data).stdout == b'<root><child>text</child></root>\n'
    assert run('--indent=4', data=b'<r><x/></r>').stdout == b'<r>\n    <x/>\n</r>\n'
    assert run('--indent', '4', '--tab', data=b'<r><x/></r>').stdout == b'<r>\n\t<x/>\n</r>\n'


def test_xml_empty_attributes_unicode_and_entities():
    data = '<r a="x&amp;y\nz"><e></e><x/> <v>世界 مرحبا Привет é 😀 &amp; &lt;</v></r>'.encode()
    p = run(data=data)
    assert p.returncode == 0
    out = txt(p)
    assert '<r a="x&amp;y&#xA;z">' in out
    assert '<e/>' in out and '<x/>' in out
    assert '世界 مرحبا Привет é 😀 &' in out and '&lt;' in out


def test_xml_misc_nodes_and_doctype_detection():
    data = b'<!-- Top --><?xml version="1.0"?><!DOCTYPE html><root><!-- inner --><x>t</x></root><!-- Bottom -->'
    p = run(data=data)
    assert p.returncode == 0
    o = txt(p)
    assert '<!-- Top -->' in o and '<?xml version="1.0"?>' in o
    assert '<!doctype html>' in o and '<!-- inner -->' in o and '<!-- Bottom -->' in o


def test_xml_cdata_declaration_exception():
    p = run(data=b'<r><![CDATA[plain text]]></r>')
    assert p.returncode == 1 and p.stdout == b"Error: invalid character '<' looking for beginning of value\n" and p.stderr == b''
    p = run(data=b'<?xml version="1.0"?><r><![CDATA[a < b & c]]></r>')
    assert p.returncode == 0 and b'<![CDATA[a < b & c]]>' in p.stdout


def test_input_detection_json_xml_and_html():
    assert run(data=b'{"a":1}').stdout == b'{\n  "a": 1\n}\n'
    assert run(data=b'<html><body><br></body></html>').returncode == 0
    assert run('--html', data=b'<DIV><p>Hello').stdout == b'<div>\n  <p>Hello\n'
    assert run('--json', data=b'<r><x>v</x></r>').stdout == b'{\n  "r": {\n    "x": "v"\n  }\n}\n'


def test_json_types_order_and_indentation_compact():
    src = b'{"z":[true,null,-2,1.5e2],"a":"\u4e2d"}'
    assert run(data=src).stdout == '{\n  "z": [\n    true,\n    null,\n    -2,\n    1.5e2\n  ],\n  "a": "中"\n}\n'.encode()
    assert run('--indent', '4', data=b'{"a":{"b":1}}').stdout == b'{\n    "a": {\n        "b": 1\n    }\n}\n'
    assert run('--json', '--compact', data=b'{ "a": [1, 2], "b": true }').stdout == b'{"a": [1,2],"b": true}\n'
    assert run('--compact', data=b'{"a":1}').stdout == b'{\n  "a": 1\n}\n'


def test_html_semantics_and_entities():
    p = run('--html', data=b'<DIV><meta charset="UTF-8"><p>Text &lt;x&gt; &amp; &copy;</p><p></p><video controls><source src="a"></video></DIV>')
    o = txt(p)
    assert p.returncode == 0 and '<div>' in o and '<meta charset="UTF-8"/>' in o
    assert 'Text <x> & ©' in o and '<p></p>' in o and '<video controls="">' in o
    assert '<source src="a"/></video>' in o
    p = run('--html', data=b'<pre>line 1\n    line 2\n<not-a-tag></pre>')
    assert p.stdout == b'<pre>line 1\n    line 2\n\n  <not-a-tag></pre>\n'


def test_xpath_selection_scalar_and_functions():
    xml = b'<root><team><member role="dev"><name>A</name></member><member><name>B</name></member></team><team><member role="dev"><name>C</name></member></team><n>24.99</n><n>50</n></root>'
    assert run('-x', '//team/member[1]/name', data=xml).stdout == b'A\nC\n'
    assert run('--xpath', '//member[@role="dev"]/name', data=xml).stdout == b'A\nC\n'
    assert run('-x', 'count(//member)', data=xml).stdout == b'3\n'
    assert run('-x', 'sum(//n)', data=xml).stdout == b'75\n'
    assert run('-x', 'string(//name)', data=xml).stdout == b'A\n'
    assert run('-x', '//missing', data=xml).stdout == b''


def test_xpath_errors_and_scalar_boolean_quirk():
    p = run('-x', '//*[', data=b'<r/>')
    assert p.returncode == 1 and p.stdout == b'Error: unable to parse the XPath query\n'
    for expr in ["contains('alphabet', 'pha')", "starts-with('alphabet', 'alpha')"]:
        p = run('-x', expr, data=b'<r/>')
        assert p.returncode == 1 and p.stdout == b'Error: unknown type error: true\n' and p.stderr == b''


def test_css_queries_attrs_node_and_precedence():
    xml = b'<root><a class="nav-link active" data-id="102" id="x">One</a><a class="nav-link">Two</a><b>Three</b></root>'
    assert run('-q', 'a.nav-link.active[data-id="102"]', data=xml).stdout == b'One\n'
    assert run('-q', 'root > a:first-of-type', data=xml).stdout == b'One\n'
    assert run('-q', 'a:not([missing])', '-a', 'class', data=xml).stdout == b'nav-link active\nnav-link\n'
    assert run('-a', 'data-id', '-q', 'a', data=xml).stdout == b'102\n\n'
    assert run('-n', '-q', '#x', data=xml).stdout == b'<a class="nav-link active" data-id="102" id="x">One</a>\n'
    assert run('-x', '//a', '-q', 'b', data=xml).stdout == b'One\nTwo\n'
    assert run('--json', '-x', '//a', data=xml).stdout == b'One\nTwo\n'


def test_attribute_requires_css_query():
    p = run('-a', 'id', data=b'<r/>')
    assert p.returncode == 1 and p.stderr == b'Error: query option (-q) is missed for attribute selection\n'


def test_json_conversion_attributes_repetition_depth_compact():
    xml = b'<book id="123"><title lang="en">Sample</title><author>Jane</author><author>John</author></book>'
    obj = json.loads(run('--json', data=xml).stdout)
    assert obj == {'book': {'@id': '123', 'author': ['Jane', 'John'], 'title': {'#text': 'Sample', '@lang': 'en'}}}
    nested = b'<root><level1><level2><level3>Deep</level3></level2></level1></root>'
    assert json.loads(run('--json', '--depth', '0', data=nested).stdout) == {'root': 'Deep'}
    assert json.loads(run('--json', '--depth=1', data=nested).stdout) == {'root': {'level1': 'Deep'}}
    assert run('--json', '--indent', '4', data=b'<r><x>1</x></r>').stdout == b'{\n  "r": {\n    "x": "1"\n  }\n}\n'
    assert run('--json', '--compact', data=b'<r><x>1</x><x>2</x></r>').stdout == b'{"r": {"x": ["1","2"]}}\n'


def test_color_and_no_color_precedence():
    plain = run('--no-color', data=b'<root a="x"><child>v</child></root>')
    assert b'\x1b[' not in plain.stdout
    colored = run('--color', '--no-color', data=b'<root a="x"><child>v</child></root>')
    assert b'\x1b[33m<root' in colored.stdout and b'\x1b[32m="x"' in colored.stdout
    j = run('--color', data=b'{"a":1}')
    stripped = re.sub(rb'\x1b\[[0-9;]*m', b'', j.stdout)
    json.loads(stripped)


def test_config_precedence_and_xdg_ignored(tmp_path):
    (tmp_path / '.xq').write_text('tab=true\nindent=3\ncolor=false\n')
    assert run('--indent', '3', '--no-color', data=b'<r><x/></r>', home=tmp_path).stdout == b'<r>\n\t<x/>\n</r>\n'
    (tmp_path / '.xq').write_text('color=true\n')
    assert b'\x1b[' not in run('--no-color', data=b'<r/>', home=tmp_path).stdout
    (tmp_path / '.xq').write_text('no-color=true\n')
    assert b'\x1b[' in run('--color', data=b'<r/>', home=tmp_path).stdout
    cfg = tmp_path / 'xdg'; (cfg / 'xq').mkdir(parents=True)
    (cfg / 'xq' / 'config').write_text('tab=True\n')
    envhome = tmp_path / 'elsewhere'; envhome.mkdir()
    env = os.environ.copy(); env['HOME'] = str(envhome); env['XDG_CONFIG_HOME'] = str(cfg)
    p = subprocess.run([str(EXE)], input=b'<r><x>v</x></r>', stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    assert p.stdout == b'<r>\n  <x>v</x>\n</r>\n'


def test_files_order_open_preflight_and_in_place(tmp_path):
    good = tmp_path / 'good.xml'; good.write_bytes(b'<r/>')
    p = run(str(good), 'extra')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'Error: open extra: no such file or directory\n'
    second = tmp_path / 'second.json'; second.write_text('{"x":1}')
    p = run(str(good), str(second))
    assert p.stdout == b'<r/>\n{\n  "x": 1\n}\n'
    p = run('--in-place', str(good))
    assert (p.returncode, p.stdout, p.stderr, good.read_bytes()) == (0, b'', b'', b'<r/>\n')
    link = tmp_path / 'link'; link.symlink_to(good)
    run('-i', str(link))
    assert link.is_symlink()
    a = tmp_path / 'a'; b = tmp_path / 'b'; a.write_bytes(b'<a/>'); b.write_bytes(b'<b/>')
    p = run('-i', str(a), str(b))
    assert p.returncode == 1 and p.stdout == b'' and b'only one file path' in p.stderr
    assert a.read_bytes() == b'<a/>' and b.read_bytes() == b'<b/>'


def test_in_place_arity_and_file_errors(tmp_path):
    p = run('-i', data=b'<r/>')
    assert p.returncode == 1 and p.stderr == b'Error: in-place formatting requires a file path (and only one file path)\n'
    p = run('missing/path')
    assert p.returncode == 1 and p.stderr == b'Error: open missing/path: no such file or directory\n'
    p = run(str(tmp_path))
    assert p.returncode == 1 and p.stdout == b'Error: unknown content type: 3\n'


def test_empty_pipe_invalid_input_and_malformed_xml():
    p = run(data=b'')
    assert p.returncode == 1 and txt(p).startswith('Error: unknown content type:')
    p = run(data=b'\xff<r/>')
    assert p.returncode == 1 and b'Error: XML syntax error' in p.stdout and b'invalid UTF-8' in p.stdout
    p = run(data=b'<root><unclosed>')
    assert p.returncode == 1 and p.stdout.endswith(b'<root>\n  <unclosedError: XML syntax error on line 1: unexpected EOF\n')
    p = run('--html', data=b'<p>unclosed')
    assert p.returncode == 0 and p.stdout == b'<p>unclosed\n'


def test_json_errors_and_partial_object():
    p = run(data=b'{"key": invalid}')
    assert p.returncode != 0 and b"invalid character 'i' looking for beginning of value" in p.stdout
    p = run('--json', data=b'<r><x>')
    assert p.returncode == 1 and b'Error: error while parsing XML: XML syntax error' in p.stdout
    p = run(data=b'{"key": "value"')
    assert p.returncode == 0 and p.stdout == b'{\n  "key": "value"\n'


def test_bom_and_xml_encoding():
    p = run(data=b'\xef\xbb\xbf<r>ok</r>')
    assert p.returncode == 0 and p.stdout.startswith(b'\xef\xbb\xbf')
    p = run(data=b'\xef\xbb\xbf{"x":1}')
    assert p.returncode == 1 and b'Error:' in p.stdout


def test_large_document_and_siblings():
    data = ('<r>' + ''.join('<x>%d</x>' % i for i in range(1000)) + '</r>').encode()
    p = run(data=data)
    assert p.returncode == 0 and p.stdout.count(b'<x>') == 1000 and b'<x>999</x>' in p.stdout
    longtext = 'a' * 100000
    p = run(data=('<r>' + longtext + '</r>').encode())
    assert p.returncode == 0 and longtext.encode() in p.stdout
