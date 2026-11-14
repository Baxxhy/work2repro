import os
import re
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


def run(args=(), data=None, *, cwd=None, env=None):
    return subprocess.run([str(EXE), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=env, timeout=15)


def out(args=(), data=b'', **kw):
    p = run(args, data, **kw)
    assert p.returncode == 0, (p.returncode, p.stderr)
    return p.stdout.decode('utf-8', 'replace')


def test_version_exact():
    p = run(['--version'])
    assert (p.returncode, p.stdout, p.stderr) == (0, b'monolith 2.11.0\n', b'')


def test_help_exact_shape():
    p = run(['--help'])
    assert p.returncode == 0
    assert p.stdout.endswith(b'  -V, --version                          Print version\n')
    assert p.stderr == b''


def test_no_target_diagnostic():
    p = run([])
    assert p.returncode == 2 and p.stdout == b''
    assert b'<TARGET>' in p.stderr and p.stderr.endswith(b"For more information, try '--help'.\n")


def test_unknown_option_clap_diagnostic():
    p = run(['--nonexistent'])
    assert p.returncode == 2 and p.stdout == b''
    assert b"unexpected argument '--nonexistent' found" in p.stderr
    assert b"tip: to pass '--nonexistent' as a value, use '-- --nonexistent'" in p.stderr


def test_timeout_invalid_exact():
    p = run(['--timeout', 'invalid', '-'])
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr == b"error: invalid value 'invalid' for '--timeout <60>': invalid digit found in string\n\nFor more information, try '--help'.\n"


def test_empty_input_builds_document_and_robots():
    s = out(['-q', '-M', '-'], b'')
    assert s == '<html><head><meta name="robots" content="none"></meta></head><body></body></html>\n'


def test_stdin_omits_metadata_and_normalizes_markup():
    s = out(['-q'], b'<!doctype html><P title=\'a&b\'>x&amp;y')
    assert s.startswith('<!DOCTYPE html>\n<html>') or s.startswith('<!-- Saved')
    assert '<p title="a&amp;b">x&amp;y</p>' in s
    assert s.count('name="robots"') == 1
    assert s.endswith('\n')
    # stdin never has a source from which to construct metadata
    assert '<!-- Saved from' not in s


def test_existing_robots_is_updated_without_duplicate():
    s = out(['-q', '-M', '-'], b'<html><head><meta name="ROBOTS" content="index, follow"></head><body></body></html>')
    assert len(re.findall(r'<meta name="robots" content="none">', s, re.I)) == 1
    assert 'index, follow' not in s


def test_template_contents_discarded_and_malformed_html_repaired():
    s = out(['-q', '-M', '-'], b'<template><b>hidden</b></template><table><tr><td>x')
    assert '<template></template>' in s and 'hidden' not in s
    assert '<table>' in s and '<td>x</td>' in s


def test_entities_void_elements_and_line_endings():
    s = out(['-q', '-M', '-'], b'<p>&amp; &lt;\r\n<img src="data:,x"><br>')
    assert '&amp; &lt;\n' in s
    assert '<img src="data:,x">' in s and '<br>' in s
    assert '<img src="data:,x"/>' not in s


def test_no_js_removes_scripts_handlers_and_rewrites_javascript_links():
    s = out(['-q', '-M', '-j', '-'], b'<script src="data:text/javascript,alert(1)">inline</script><a onclick="x()" href="javascript:go()">x</a><area href="JAVASCRIPT:x">')
    assert '<script></script>' in s
    assert 'onclick=' not in s and 'inline' not in s and 'alert(1)' not in s
    assert 'href="javascript:;"' in s and 'href="JAVASCRIPT:x"' in s
    assert "script-src 'none';" in s


def test_no_css_preserves_style_nodes_but_clears_contents():
    s = out(['-q', '-M', '-c', '-'], b'<style>.x{color:red}</style><p style="color:blue">x</p><link rel="stylesheet" href="data:text/css,.x%7B%7D">')
    assert '<style></style>' in s and 'style="color:blue"' not in s
    assert 'rel="stylesheet"' in s and 'href=' not in s
    assert "style-src 'none';" in s


def test_isolate_adds_csp_but_keeps_inline_content():
    s = out(['-q', '-M', '-I', '-'], b'<style>.x{color:red}</style><script>ok()</script>')
    assert "default-src 'unsafe-eval' 'unsafe-inline' data:;" in s
    assert '<style>.x{color:red}</style>' in s and '<script>ok()</script>' in s


def test_filter_csp_directives_order():
    s = out(['-q', '-M', '-IcfFjiv', '-'], b'<p>x</p>')
    expected = "default-src 'unsafe-eval' 'unsafe-inline' data:; style-src 'none'; font-src 'none'; frame-src 'none'; child-src 'none'; script-src 'none'; img-src data:;"
    assert expected in s


def test_url_navigation_stdin_base_and_custom_base():
    s = out(['-q', '-M', '-'], b'<a href="next?q=1">n</a><a href="#part">p</a><a href="mailto:a@b">m</a>')
    assert 'href="data:,"' in s and 'href="#part"' in s and 'href="mailto:a@b"' in s
    t = out(['-q', '-M', '-b', 'http://example.test/dir/', '-'], b'<a href="next">n</a>')
    assert '<base href="http://example.test/dir/"></base>' in t
    assert 'href="http://example.test/dir/next"' in t


def test_empty_custom_base_keeps_stdin_data_resolution():
    s = out(['-q', '-M', '-b', '', '-'], b'<a href="next">n</a>')
    assert '<base href=""></base>' in s and 'href="data:,"' in s


def test_data_target_plain_text_is_raw():
    p = run(['-q', 'data:,Hello%2C%20World!'])
    assert p.returncode == 0 and p.stdout == b'Hello, World!'


def test_data_html_target_is_processed():
    s = out(['-q', '-M', 'data:text/html,%3Cp%3Ex%3C/p%3E'])
    assert '<p>x</p>' in s and 'name="robots"' in s


def test_data_image_is_canonicalized_and_preserves_fragment():
    s = out(['-q', '-M', '-'], b'<img src="data:text/plain,abc#frag">')
    assert 'src="data:text/plain;base64,YWJj#frag"' in s


def test_no_images_placeholder_and_layout_preserved():
    s = out(['-q', '-M', '-i', '-'], b'<picture><source srcset="a 1x, b 2x"><img src="" data-src="x" srcset="a 1x, b 2x"></picture><svg><path d="x"></path></svg>')
    placeholder = 'data:image/png,%89PNG%0D%0A%1A%0A'
    assert '<picture>' in s and '<img' in s and s.count(placeholder) >= 3
    assert '<svg></svg>' in s
    assert 'img-src data:;' in s


def test_no_audio_and_video_keep_elements():
    s = out(['-q', '-M', '-av', '-'], b'<audio src="data:,x"><source src="data:,y">fallback</audio><video src="data:,x"><source src="data:,y">v</video>')
    assert '<audio><source>fallback</audio>' in s
    assert '<video><source>v</video>' in s


def test_frames_flag_empties_sources_and_adds_both_directives():
    s = out(['-q', '-M', '-f', '-'], b'<iframe src="data:text/html,x">fallback</iframe><frame src="x">')
    assert '<iframe src="">fallback</iframe>' in s and '<frame src="">' in s
    assert "frame-src 'none'; child-src 'none';" in s


def test_noscript_unwrap_uses_comments():
    s = out(['-q', '-M', '-n', '-'], b'<noscript class="x">hello<noscript>deep</noscript></noscript>')
    assert '<!--noscript class="x"-->hello' in s
    assert '<!--noscript-->deep<!--/noscript-->' in s
    assert s.count('<!--/noscript-->') == 2


def test_quiet_suppresses_runtime_errors():
    p = run(['-q', '-M', '-'], b'<img src="file:///no/such/image.png">')
    assert p.returncode == 0 and p.stderr == b''


def test_local_file_target_and_relative_navigation(tmp_path):
    source = tmp_path / 'page.html'
    source.write_text('<a href="next.html">next</a>', encoding='utf8')
    s = out(['-q', '-M', source])
    assert 'href="file://' + str(tmp_path) + '/next.html"' in s


def test_output_file_overwrites_and_stdout_empty(tmp_path):
    dest = tmp_path / 'result.html'
    dest.write_text('old trailing data', encoding='utf8')
    p = run(['-q', '-M', '-o', dest, '-'], b'<p>new</p>')
    assert p.returncode == 0 and p.stdout == b''
    assert '<p>new</p>' in dest.read_text(encoding='utf8')
    assert 'old trailing data' not in dest.read_text(encoding='utf8')


def test_output_placeholders_and_title_colon(tmp_path):
    p = run(['-q', '-M', '-o', tmp_path / 'output-%title%-%ext%-%extension%.html', '-'], b'<title>Test: File &amp; Data</title>')
    assert p.returncode == 0
    assert (tmp_path / 'output-Test -  File & Data-htm-html.html').exists()


def test_invalid_encoding_is_runtime_error_without_document():
    p = run(['-q', '-E', 'no-such-encoding', '-'], b'<p>x</p>')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'Error: unknown encoding "no-such-encoding"\n'


def test_refresh_and_location_meta_are_sanitized():
    s = out(['-q', '-M', '-'], b'<meta http-equiv="Refresh" content="0;url=x"><meta http-equiv="content-type" content="text/html">')
    assert '<meta content="0;url=x">' in s
    assert 'http-equiv="Refresh"' not in s
    assert 'http-equiv="content-type"' in s


def test_preload_and_dns_prefetch_rel_removed():
    s = out(['-q', '-M', '-'], b'<link rel="alternate preload" as="image" href="data:,x"><link rel="dns-prefetch" href="//example.test">')
    assert '<link as="image" href="data:,x">' in s
    assert 'rel="alternate preload"' not in s and 'rel="dns-prefetch"' not in s


def test_no_fonts_removes_font_face_but_keeps_other_css():
    s = out(['-q', '-M', '-F', '-'], b'<style>@font-face{font-family:x;src:url(data:,font)} .x{color:red}</style>')
    assert '@font-face' not in s and '.x{color:red}' in s
    assert "font-src 'none';" in s


def test_failed_local_resource_is_removed_and_logged(tmp_path):
    page = tmp_path / 'p.html'
    page.write_text('<img src="missing.png">', encoding='utf8')
    p = run(['-M', page])
    assert p.returncode == 0 and '<img>' in p.stdout.decode('utf8')
    assert 'file://' + str(tmp_path / 'missing.png') in p.stderr.decode('utf8')
    assert 'file not found' in p.stderr.decode('utf8')


def test_stdin_file_fetch_denied_repeatedly_and_not_embedded(tmp_path):
    target = tmp_path / 'secret.png'
    target.write_bytes(b'\x89PNG\r\n\x1a\nsecret')
    html = f'<img src="{target.as_uri()}"><img src="{target.as_uri()}">'.encode()
    p = run(['-M', '-'], html)
    diagnostic = p.stderr.decode('utf8')
    assert p.returncode == 0 and p.stdout.count(b'<img>') == 2
    assert diagnostic.count(target.as_uri()) == 2 and diagnostic.count('security error') == 2
    assert b'secret' not in p.stdout


def test_stdin_javascript_disabled_still_keeps_denied_script_integrity(tmp_path):
    script = tmp_path / 'secret.js'
    script.write_text('alert(1)', encoding='utf8')
    s = out(['-q', '-M', '-j', '-'], f'<script src="{script.as_uri()}" integrity="sha256-x"></script>'.encode())
    assert '<script integrity="sha256-x"></script>' in s


def test_noscript_content_resources_are_processed():
    s = out(['-q', '-M', '-'], b'<noscript><img src="data:,x"><style>.x{color:red}</style></noscript>')
    assert '<noscript><img src="data:text/plain;base64,eA=="></noscript>' in s
    assert '<style>' not in s


def test_mhtml_envelope_and_implied_js_disable():
    p = run(['-q', '-M', '-m', '-'], b'<script>secret()</script><p>x</p>')
    assert p.returncode == 0
    assert p.stdout.startswith(b'MIME-Version: 1.0\r\nContent-Type: multipart/related; boundary="----=_NextPart_000_0000"\r\n\r\n')
    assert b'Content-Type: text/html; charset="utf-8"\r\nContent-Location: http://example.com/\r\n\r\n' in p.stdout
    assert b'<script></script>' in p.stdout and p.stdout.endswith(b'------=_NextPart_000_0000--\r\n')


def test_local_binary_image_embedded_completely(tmp_path):
    image = tmp_path / 'x.png'
    image.write_bytes(b'\x89PNG\r\n\x1a\nPAYLOAD')
    page = tmp_path / 'p.html'
    page.write_text('<img src="x.png">', encoding='utf8')
    s = out(['-q', '-M', page])
    import base64
    expected = base64.b64encode(image.read_bytes()).decode()
    assert 'data:image/png;base64,' + expected in s
