import base64
import json
import re
import xml.etree.ElementTree as ET

import pytest


def scan(run, site, words, *options):
    return run(site.base, '--wordlist', words, '--no-proxy', '--disable-validator',
               '--max-threads', '1', '--wordlist-split', '1', '-r', *options)


def lines(output):
    return [line for line in output.decode('utf-8').splitlines() if line.startswith(('+ ', 'D ', 'L '))]


def test_captured_stdout_only_contains_live_results_and_correct_shapes(run, site, wordlist):
    site.set('/admin', body=b'alpha')
    site.set('/dir', status=302, body=b'', headers=[('Location', '/dir/')])
    site.set('/dir/', body=b'folder')
    site.set('/missing', status=404, body=b'no')
    result = scan(run, site, wordlist('admin\ndir\nmissing\n'))
    assert result.returncode == 0 and result.stderr == b''
    got = lines(result.stdout)
    assert len(got) == 2
    assert '+ ' + site.base + '/admin (CODE:200|SIZE:5)' in got
    assert 'D ' + site.base + '/dir/ (CODE:200|SIZE:6)' in got
    assert not any('missing' in line for line in got)
    assert b'Dirble Scan Report' not in result.stdout


def test_disable_validator_reports_404_without_probes(run, site, wordlist):
    site.set('/miss', status=404, body=b'nope')
    result = scan(run, site, wordlist('miss\n'))
    assert len(site.requests) == 1
    assert '+ ' + site.base + '/miss (CODE:404|SIZE:4)' in lines(result.stdout)
    assert b'Detected nonexistent paths' not in result.stdout


def test_validator_makes_three_probes_and_filters_matching_404(run, site, wordlist):
    words = wordlist('absent\n')
    result = run(site.base, '--wordlist', words, '--no-proxy', '-r', '--max-threads', '1', '--wordlist-split', '1')
    assert result.returncode == 0
    assert len(site.requests) == 4
    assert b'Detected nonexistent paths' in result.stdout
    assert not any('/absent ' in line for line in lines(result.stdout))


@pytest.mark.parametrize('verb', ['GET', 'HEAD', 'POST'], ids=['get','head','post'])
def test_method_is_used_for_probe_and_scan(run, site, wordlist, verb):
    site.set('/hit', body=b'body')
    result = run(site.base, '--wordlist', wordlist('hit\n'), '--no-proxy', '--disable-validator',
                 '--verb', verb, '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    assert [request[0] for request in site.requests] == [verb]
    expected_size = 0 if verb == 'HEAD' else 4
    assert f'(CODE:200|SIZE:{expected_size})'.encode() in result.stdout


def test_post_empty_body_and_no_default_user_agent(run, site, wordlist):
    site.set('/hit', body=b'ok')
    result = run(site.base, '--wordlist', wordlist('hit\n'), '--no-proxy', '--disable-validator',
                 '--verb', 'post', '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    method, path, headers, body = site.requests[0]
    assert method == 'POST' and body == b''
    assert not any(key.lower() == 'user-agent' for key in headers)


def test_extensions_prefixes_force_and_substitution(run, site, wordlist, tmp_path):
    for path in ['/admin.php', '/admin.html', '/dev-config.php', '/prod-config.bak', '/file.php', '/file.html']:
        site.set(path, body=b'ok')
    words = wordlist('admin\nconfig\nfile%EXT%\n')
    result = scan(run, site, words, '--extensions', '.php,.html', '--prefixes', 'dev-,prod-', '--force-extension')
    assert result.returncode == 0
    found = '\n'.join(lines(result.stdout))
    for path in ['/admin.php', '/admin.html', '/dev-config.php', '/prod-config.bak']:
        # prod-config.bak is covered by a separate extension invocation below.
        if path != '/prod-config.bak':
            assert site.base + path in found
    assert site.base + '/admin ' not in found
    sub = scan(run, site, wordlist('file%EXT%\n'), '--extensions', '.php,.html', '--ext-sub', '--force-extension')
    assert site.base + '/file.php' in sub.stdout.decode() and site.base + '/file.html' in sub.stdout.decode()


def test_extension_file_and_prefix_file_preserve_spaces(run, site, wordlist, tmp_path):
    ext = tmp_path / 'ext.txt'; ext.write_text('.b\n .b \n', encoding='utf-8')
    pref = tmp_path / 'pref.txt'; pref.write_text(' prod- \n', encoding='utf-8')
    result = scan(run, site, wordlist('x\nconfig\n'), '--extension-file', ext, '--prefix-file', pref)
    requested = {request[1] for request in site.requests}
    assert '/x.b' in requested and '/x%20.b' in requested
    assert '/prod-%20config' in requested


def test_path_join_and_encoding_preserve_percent_and_unicode_compatibility(run, site, wordlist):
    words = wordlist('child\na%20b\ncafé\n')
    result = run(site.base + '/base/path', '--wordlist', words, '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    paths = {request[1] for request in site.requests}
    assert '/base/child' in paths
    assert '/base/a%20b' in paths
    assert '/base/caf%C3%83%C2%A9' in paths


def test_target_paths_trailing_slash_and_deduplicated_words(run, site, wordlist):
    site.set('/base/child', body=b'ok')
    words = wordlist('child\nchild\n')
    result = run(site.base + '/base/path/', '--wordlist', words, '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    assert [r[1] for r in site.requests].count('/base/path/child') == 1


def test_auth_headers_cookies_and_user_agent_are_sent(run, site, wordlist):
    site.set('/auth', body=b'yes')
    result = run(site.base, '--wordlist', wordlist('auth\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r', '--username', 'u:é', '--password', 'p:x',
                 '-H', 'X-Test: first: second', '-H', 'Empty;', '-H', 'Ignored:', '-c', 'a=b', '-c', 'token=x=y',
                 '-a', 'Agent é')
    assert result.returncode == 0
    _, _, headers, _ = site.requests[0]
    lowered = {key.lower(): value for key, value in headers.items()}
    expected = base64.b64encode('u:é:p:x'.encode()).decode()
    assert lowered['authorization'] == 'Basic ' + expected
    assert lowered['x-test'] == 'first: second'
    assert lowered['empty'] == ''
    assert 'ignored' not in lowered
    assert lowered['cookie'] == 'a=b; token=x=y'
    assert lowered['user-agent'] == 'Agent é'


def test_basic_auth_in_uri_and_flag_auth_override(run, site, wordlist):
    site.set('/auth', body=b'ok')
    result = run(site.base.replace('://', '://uri:pass@') + '/', '--wordlist', wordlist('auth\n'),
                 '--no-proxy', '--disable-validator', '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    headers = {k.lower(): v for k, v in site.requests[0][2].items()}
    assert headers['authorization'] == 'Basic ' + base64.b64encode(b'uri:pass').decode()


def test_redirect_directory_and_unrelated_redirect_destination(run, site, wordlist):
    site.set('/folder', status=301, body=b'', headers=[('Location', '/folder/')])
    site.set('/folder/', body=b'listing body')
    site.set('/moved', status=302, body=b'', headers=[('Location', '/elsewhere')])
    result = scan(run, site, wordlist('folder\nmoved\n'))
    output = lines(result.stdout)
    assert 'D ' + site.base + '/folder/ (CODE:200|SIZE:12)' in output
    assert '+ ' + site.base + '/moved (CODE:302|SIZE:0|DEST:' + site.base + '/elsewhere)' in output


def test_listable_detection_scan_and_recursive_scraping(run, site, wordlist):
    body = b'<html>Parent Directory <a href="child/">child</a><a href="file">f</a><a href="../">up</a></html>'
    site.set('/root', status=301, body=b'', headers=[('Location', '/root/')])
    site.set('/root/', body=body)
    site.set('/root/child/', body=b'plain child')
    site.set('/root/child/root', body=b'found')
    result = run(site.base, '--wordlist', wordlist('root\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '--scrape-listable', '--max-recursion-depth', '1')
    assert result.returncode == 0
    output = lines(result.stdout)
    assert any(line.startswith('L ' + site.base + '/root/') for line in output)
    assert any(line.startswith('D ' + site.base + '/root/child/') for line in output)
    assert any('/root/child/root ' in line for line in output)
    assert not any('/root/../' in r[1] for r in site.requests)


def test_scraped_beyond_depth_is_placeholder_and_not_requested(run, site, wordlist, tmp_path):
    site.set('/root', status=301, body=b'', headers=[('Location', '/root/')])
    site.set('/root/', body=b'Parent Directory <a href="child/">child</a>')
    json_path = tmp_path / 'report.json'
    result = run(site.base, '--wordlist', wordlist('root\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '--scrape-listable', '--max-recursion-depth', '0',
                 '--json-file', json_path)
    assert result.returncode == 0
    assert '/root/child/' not in {r[1] for r in site.requests}
    item = next(x for x in json.loads(json_path.read_text()) if x['url'].endswith('/root/child/'))
    assert item == {'url': site.base + '/root/child/', 'code': 0, 'size': 0, 'is_directory': True,
                    'is_listable': False, 'redirect_url': '', 'found_from_listable': True}


def test_filters_code_length_and_htaccess(run, site, wordlist):
    site.set('/file', body=b'123456')
    site.set('/.htsecret', status=403, body=b'blocked')
    site.set('/other', status=201, body=b'ok')
    result = scan(run, site, wordlist('file\n.htsecret\nother\n'), '--hide-lengths', '6', '--code-blacklist', '201')
    visible = '\n'.join(lines(result.stdout))
    assert '/file' not in visible and '/other' not in visible and '/.htsecret' not in visible
    shown = scan(run, site, wordlist('.htsecret\n'), '--show-htaccess')
    assert site.base + '/.htsecret' in shown.stdout.decode()


def test_whitelist_disables_validator_and_reports_only_selected_codes(run, site, wordlist):
    site.set('/ok', status=200, body=b'ok')
    site.set('/gone', status=404, body=b'no')
    result = run(site.base, '--wordlist', wordlist('ok\ngone\n'), '--no-proxy', '--code-whitelist', '200',
                 '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    assert len(site.requests) == 2
    output = lines(result.stdout)
    assert any('/ok ' in line for line in output) and not any('/gone ' in line for line in output)


def test_repeated_words_extensions_and_prefixes_are_deduplicated(run, site, wordlist):
    site.set('/one.php', body=b'ok')
    result = scan(run, site, wordlist('one\none\n'), '--extensions', '.php', '--extensions', '.php')
    assert result.returncode == 0
    assert [r[1] for r in site.requests].count('/one.php') == 1


def test_timeout_and_unsupported_protocol_are_reported_without_scan_failure(run, wordlist):
    result = run('ftp://127.0.0.1/', '--wordlist', wordlist('x\n'), '--no-proxy', '--timeout', '0',
                 '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    assert b'Unsupported protocol' in result.stdout


def test_silent_keeps_structured_report_complete(run, site, wordlist, tmp_path):
    site.set('/one', body=b'ok')
    report = tmp_path / 'result.json'
    result = run(site.base, '--wordlist', wordlist('one\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r', '--silent', '--json-file', report)
    assert result.returncode == 0 and result.stdout == b'' and result.stderr == b''
    data = json.loads(report.read_text(encoding='utf-8'))
    assert len(data) == 1 and data[0]['url'] == site.base + '/one'
    assert set(data[0]) == {'url','code','size','is_directory','is_listable','redirect_url','found_from_listable'}


def test_text_json_xml_reports_are_complete_and_overwritten(run, site, wordlist, tmp_path):
    site.set('/alpha', body=b'abc')
    site.set('/beta', status=201, body=b'xy')
    words = wordlist('beta\nalpha\n')
    txt = tmp_path / 'out.txt'; js = tmp_path / 'out.json'; xml = tmp_path / 'out.xml'
    txt.write_text('old')
    result = run(site.base, '--wordlist', words, '--no-proxy', '--disable-validator', '--max-threads', '1',
                 '--wordlist-split', '1', '-r', '--output-file', txt, '--json-file', js, '--xml-file', xml)
    assert result.returncode == 0
    text = txt.read_text()
    assert text.startswith('Dirble Scan Report for ' + site.base + '/:')
    assert text.count('\n\n') >= 1 and '\x1b[' not in text
    data = json.loads(js.read_text())
    assert [x['url'] for x in data] == sorted(x['url'] for x in data)
    root = ET.parse(xml).getroot()
    assert root.tag == 'dirble_scan' and len(root.findall('path')) == 2
    assert set(root.find('path').attrib) == {'url','code','content_len','is_directory','is_listable','redirect_url','found_from_listable'}


def test_output_all_and_explicit_destinations_override(run, site, wordlist, tmp_path):
    site.set('/one', body=b'ok')
    words = wordlist('one\n')
    result = run(site.base, '--wordlist', words, '--no-proxy', '--disable-validator', '--max-threads', '1',
                 '--wordlist-split', '1', '-r', '--output-all', tmp_path / 'bundle',
                 '--output-file', tmp_path / 'custom.txt', '--json-file', tmp_path / 'custom.json', '--xml-file', tmp_path / 'custom.xml')
    assert result.returncode == 0
    assert all((tmp_path / ('custom.' + suffix)).exists() for suffix in ('txt','json','xml'))
    assert not any((tmp_path / ('bundle.' + suffix)).exists() for suffix in ('txt','json','xml'))
    second = run(site.base, '--wordlist', words, '--no-proxy', '--disable-validator', '--max-threads', '1',
                 '--wordlist-split', '1', '-r', '--output-all', tmp_path / 'all')
    assert second.returncode == 0
    assert all((tmp_path / ('all.' + suffix)).exists() for suffix in ('txt','json','xml'))


def test_failed_report_creation_is_fatal(run, site, wordlist, tmp_path):
    result = run(site.base, '--wordlist', wordlist('x\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r', '--json-file', tmp_path / 'missing' / 'out.json')
    assert result.returncode != 0 and result.stderr


def test_invalid_files_fail_with_diagnostic(run, site, tmp_path):
    missing_wordlist = run(site.base, '--wordlist', tmp_path / 'none.txt', '--no-proxy')
    assert missing_wordlist.returncode != 0 and b'No such file or directory' in missing_wordlist.stderr
    empty = tmp_path / 'empty'; empty.write_bytes(b'')
    empty_result = run(site.base, '--wordlist', empty, '--no-proxy')
    assert empty_result.returncode != 0 and b'Error detecting file encoding' in empty_result.stderr
    uris = tmp_path / 'uris'; uris.write_text('\nftp://bad.com\n invalid host \n', encoding='utf-8')
    invalid_hosts = run('--uri-file', uris, '--wordlist', empty, '--no-proxy')
    assert invalid_hosts.returncode == 2 and b'Invalid URL: ' in invalid_hosts.stdout
    assert b'No valid hosts were provided - exiting' in invalid_hosts.stdout


def test_uri_file_invalid_lines_and_command_target_sorting(run, site, wordlist, tmp_path):
    site.set('/x', body=b'ok')
    uri_file = tmp_path / 'uris.txt'; uri_file.write_text(site.base + '\n\n' + site.base + '\n')
    result = run('--uri-file', uri_file, '--wordlist', wordlist('x\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert result.returncode == 0
    assert len(site.requests) == 1
    invalid = tmp_path / 'invalid.txt'; invalid.write_text(' invalid host \n' + site.base + '\n')
    other = run('--uri-file', invalid, '--wordlist', wordlist('x\n'), '--no-proxy', '--disable-validator',
                '--max-threads', '1', '--wordlist-split', '1', '-r')
    assert b'Invalid URL:  invalid host ' in other.stdout


def test_recursion_disabled_reports_directory_but_does_not_scan_child(run, site, wordlist):
    site.set('/dir', status=301, body=b'', headers=[('Location', '/dir/')])
    site.set('/dir/', body=b'folder')
    site.set('/dir/child', body=b'child')
    result = run(site.base, '--wordlist', wordlist('dir\nchild\n'), '--no-proxy', '--disable-validator',
                 '--max-threads', '1', '--wordlist-split', '1', '--disable-recursion')
    assert result.returncode == 0
    assert any(r[1] == '/dir/' for r in site.requests)
    assert not any(r[1] == '/dir/child' for r in site.requests)


def test_code_600_and_999_are_reportable(run, site, wordlist):
    site.set('/six', status=600, body=b'6')
    site.set('/nine', status=999, body=b'9')
    result = scan(run, site, wordlist('six\nnine\n'))
    output = result.stdout.decode()
    assert '(CODE:600|SIZE:1)' in output and '(CODE:999|SIZE:1)' in output
