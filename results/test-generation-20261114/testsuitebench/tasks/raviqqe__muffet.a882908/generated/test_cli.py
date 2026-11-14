import json
import re
import xml.etree.ElementTree as ET

from conftest import html, run


def test_help_precedes_positional_validation():
    p = run('foo', '--help')
    assert p.returncode == 0 and p.stdout.startswith(b'Usage:\n') and p.stdout.endswith(b'\n')
    assert p.stderr == b''


def test_version_is_semver():
    p = run('--version')
    assert p.returncode == 0 and re.fullmatch(rb'\d+\.\d+\.\d+\n', p.stdout)
    assert p.stderr == b''


def test_positional_count_and_unknown_flag():
    for args in [(), ('a', 'b')]:
        p = run(*args)
        assert p.returncode == 1 and p.stdout == b'' and b'invalid number of arguments' in p.stderr
    p = run('--nonexistent-flag')
    assert p.returncode == 1 and b"unknown flag `nonexistent-flag'" in p.stderr


def test_bad_url_has_stable_diagnostic():
    p = run('not-a-url')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'failed to fetch root page: missing port in address\n'


def test_invalid_option_value_and_regex_fail_before_network(site_factory):
    s = site_factory({'/': html('<a href="/x">x</a>')})
    p = run('--format=invalidformat', s.base + '/')
    assert p.returncode == 1 and p.stdout == b'' and b'Invalid value `invalidformat`' in p.stderr
    p = run('--include=[invalid(regex', s.base + '/')
    assert p.returncode == 1 and p.stdout == b'' and b'error parsing regexp' in p.stderr
    assert s.requests == []


def test_network_status_and_html_root_requirements(site_factory):
    s = site_factory({'/missing': (404, 'text/html', 'no'), '/image': (200, 'image/png', b'png'), '/empty': html('<html></html>')})
    p = run(s.base + '/missing')
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'failed to fetch root page: 404\n'
    p = run(s.base + '/image')
    assert p.returncode == 1 and p.stdout == b'' and b'invalid content type' in p.stderr
    p = run('--verbose', s.base + '/empty')
    assert p.returncode == 0 and (s.base + '/empty').encode() in p.stdout


def test_html_link_discovery_filters_and_one_page(site_factory):
    body = '''<a href="/a">a</a><img src="/img"><img src="/ignored" srcset="/also-ignored 1x">
    <source srcset="/src 480w, /src2 2x"><script src="/js"></script>
    <link href="/css" rel="stylesheet"><link href="/no" rel="preconnect">
    <meta property="og:image" content="/og"><a href="mailto:x@y">mail</a>'''
    routes = {'/': html(body)}
    for path in ['/a', '/img', '/ignored', '/also-ignored', '/src', '/src2', '/js', '/css', '/no', '/og']:
        routes[path] = html('<a href="/child">child</a>')
    routes['/child'] = html('')
    s = site_factory(routes)
    p = run('--one-page-only', '--include', '/(a|img|src|js|css|og)$', '--verbose', s.base + '/')
    assert p.returncode == 0
    requested = {x[0] for x in s.requests}
    assert {'/a', '/img', '/src', '/js', '/css', '/og'} <= requested
    assert not ({'/ignored', '/also-ignored', '/no', '/child'} & requested)


def test_recursive_crawl_and_cycles_once(site_factory):
    s = site_factory({'/': html('<a href="/a">a</a>'), '/a': html('<a href="/">home</a><a href="/b">b</a>'), '/b': html('<a href="/a">a</a>')})
    p = run('--verbose', s.base + '/')
    assert p.returncode == 0
    assert p.stdout.count((s.base + '/a\n').encode()) == 1
    assert sum(1 for path, _ in s.requests if path == '/a') == 1
    assert sum(1 for path, _ in s.requests if path == '/b') == 1


def test_failures_reported_all_and_text_sorted(site_factory):
    s = site_factory({'/': html('<a href="/z">z</a><a href="/ok">ok</a><a href="/a">a</a>'), '/ok': html(''), '/z': (500, 'text/plain', 'bad'), '/a': (404, 'text/plain', 'bad')})
    p = run(s.base + '/')
    assert p.returncode == 1 and p.stderr == b''
    assert p.stdout.decode() == f'{s.base}/\n\t404\t{s.base}/a\n\t500\t{s.base}/z\n'
    v = run('--verbose', s.base + '/')
    assert v.returncode == 1
    assert v.stdout.index((f'\t200\t{s.base}/ok').encode()) < v.stdout.index((f'\t404\t{s.base}/a').encode())


def test_include_exclude_and_fragment_validation(site_factory):
    s = site_factory({'/': html('<a href="/page#yes">yes</a><a href="/page#no">no</a><a href="/skip">skip</a>'),
                      '/page': (200, 'text/html', '<div id="yes"></div>'), '/skip': html('')})
    p = run('--include', 'page', '--exclude', '#no', '--verbose', s.base + '/')
    assert p.returncode == 0
    assert (s.base + '/page#yes').encode() in p.stdout and b'#no' not in p.stdout and b'/skip' not in p.stdout
    assert sum(1 for path, _ in s.requests if path == '/page') == 1


def test_json_shape_and_junit_failures(site_factory):
    s = site_factory({'/': html('<a href="/bad">bad</a>'), '/bad': (404, 'text/plain', 'missing')})
    p = run('--format=json', s.base + '/')
    data = json.loads(p.stdout)
    assert p.returncode == 1 and data[0]['url'] == s.base + '/'
    assert data[0]['links'] == [{'url': s.base + '/bad', 'error': '404'}]
    j = run('--junit', s.base + '/')
    root = ET.fromstring(j.stdout)
    suite = root.find('testsuite')
    assert j.returncode == 1 and suite.attrib['tests'] == '1' and suite.attrib['failures'] == '1'
    assert suite.find('testcase/failure').attrib['message'] == '404'


def test_custom_headers_propagate_and_acceptance_option(site_factory):
    s = site_factory({'/': html('<a href="/ok">ok</a>'), '/ok': html('')})
    p = run('--header', 'X-Test: value with spaces', '--accepted-status-codes=200..300,404', '--verbose', s.base + '/')
    assert p.returncode == 0
    assert all(h.get('X-Test') == 'value with spaces' for _, h in s.requests)


def test_invalid_header_and_verbose_junit_rejected():
    p = run('--header', 'badheader', 'http://127.0.0.1:1/')
    assert p.returncode == 1 and p.stdout == b'' and p.stderr == b'invalid header format\n'
    p = run('-v', '--format=junit', 'http://127.0.0.1:1/')
    assert p.returncode == 1 and p.stdout == b'' and b'verbose option not supported for JUnit output' in p.stderr


def test_redirect_limit_and_redirect_success(site_factory):
    s = site_factory({'/': html('<a href="/go">go</a>'), '/go': (302, 'text/plain', '', {'Location': '/end'}), '/end': html('')})
    p = run('--max-redirections=0', s.base + '/')
    assert p.returncode == 1 and b'too many redirections' in p.stdout
    p = run(s.base + '/')
    assert p.returncode == 0


def test_robots_blocks_scrape_but_not_check(site_factory):
    s = site_factory({'/': html('<a href="/blocked">blocked</a><a href="/open">open</a>'),
                      '/robots.txt': (200, 'text/plain', 'User-agent: *\nDisallow: /blocked'),
                      '/blocked': html('<a href="/secret">secret</a>'), '/open': html(''), '/secret': html('')})
    p = run('--follow-robots-txt', '--verbose', s.base + '/')
    assert p.returncode == 0 and b'/blocked' in p.stdout and b'/secret' not in p.stdout
    assert '/secret' not in {path for path, _ in s.requests}
