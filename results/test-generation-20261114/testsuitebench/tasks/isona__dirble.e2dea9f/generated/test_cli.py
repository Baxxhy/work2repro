import pytest


HELP = '''Fast directory scanning and scraping tool

Usage: executable [OPTIONS] <uri|--uri-file <uri-file>|--uri <uri>>

Arguments:
  [uri]
          The URI of the host to scan, optionally supports basic auth with
          http://user:pass@host:port

Options:
  -u, --uri <uri>
          Additional hosts to scan [aliases: url]
  -U, --uri-file <uri-file>
          The filename of a file containing a list of URIs to scan - cookies and
          headers set will be applied to all URIs [aliases: url-file]
      --verb <http_verb>
          Specify which HTTP verb to use
           [default: get] [possible values: get, head, post]
  -w, --wordlist <wordlist>
          Sets which wordlist to use, defaults to dirble_wordlist.txt in the same
          folder as the executable
  -p, --prefixes <prefixes>...
          Provides comma separated prefixes to extend queries with
  -P, --prefix-file <prefix-file>
          The name of a file containing extensions to extend queries with, one
          per line
  -x, --extensions <extensions>...
          Provides comma separated extensions to extend queries with
  -X, --extension-file <extension-file>
          The name of a file containing extensions to extend queries with, one
          per line
      --ext-sub
          Indicates whether the string "%EXT%" in a wordlist file should be 
          substituted with the current extension
  -f, --force-extension
          Only scan with provided extensions
  -k, --ignore-cert
          Ignore the certificate validity for HTTPS
      --show-htaccess
          Enable display of items containing .ht when they return 403 responses
      --timeout <timeout>
          Maximum time to wait for a response before giving up, given in seconds
           [default: 5]
      --max-errors <max_errors>
          The number of consecutive errors a thread can have before it exits,
          set to 0 to disable [default: 5]
      --json-file <json_file>
          Sets a file to write JSON output to [aliases: oJ]
      --no-color
          Disable coloring of terminal output
  -o, --output-file <output_file>
          Sets the file to write the report to [aliases: oN]
      --xml-file <xml_file>
          Sets a file to write XML output to [aliases: oX]
      --hide-lengths <length_blacklist>...
          Specify length ranges to hide, e.g. --hide-lengths 348,500-700
      --output-all <output_all>
          Stores all output types respectively as .txt, .json and .xml [aliases: oA]
      --burp
          Sets the proxy to use the default burp proxy values
          (http://localhost:8080)
      --no-proxy
          Disables proxy use even if there is a system proxy
      --proxy <proxy>
          The proxy address to use, including type and port, can also include a
          username and password in the form 
          "http://username:password@proxy_url:proxy_port"
  -t, --max-threads <max-threads>
          Sets the maximum number of request threads that will be spawned [default: 10]
  -T, --wordlist-split <wordlist_split>
          The number of threads to run for each folder/extension combo [default: 3]
  -z, --throttle <milliseconds>
          Time each thread will wait between requests, in milliseconds
      --username <username>
          Sets the username to authenticate with
      --password <password>
          Sets the password to authenticate with
  -l, --scan-listable
          Scan listable directories
      --max-recursion-depth <max_recursion_depth>
          Sets the maximum directory depth to recurse to, 0 will disable
          recursion
  -r, --disable-recursion
          Disable discovered subdirectory scanning
      --scrape-listable
          Enable scraping of listable directories for urls, often produces large
          amounts of output
  -a, --user-agent <user_agent>
          Set the user-agent provided with requests, by default it isn't set
  -c, --cookie <cookie>
          Provide a cookie in the form "name=value", can be used multiple times
  -H, --header <header>
          Provide an arbitrary header in the form "header:value" - headers with
          no value must end in a semicolon
  -S, --silent
          Don't output information during the scan, only output the report at
          the end.
  -v, --verbose...
          Increase the verbosity level. Use twice for full verbosity.
  -B, --code-blacklist <code_blacklist>...
          Provide a comma separated list of response codes to not show in output
      --disable-validator
          Disable automatic detection of not found codes
  -W, --code-whitelist <code_whitelist>...
          Provide a comma separated list of response codes to show in output,
          also disables detection of not found codes
      --scan-401
          Scan folders even if they return 401 - Unauthorized frequently
      --scan-403
          Scan folders if they return 403 - Forbidden frequently
  -h, --help
          Print help
  -V, --version
          Print version

OUTPUT FORMAT:
    + [url] - File
    D [url] - Directory
    L [url] - Listable Directory

EXAMPLE USE:
    - Run against a website using the default dirble_wordlist.txt from the
      current directory:
        dirble [address]

    - Run with a different wordlist and including .php and .html extensions:
        dirble [address] -w example_wordlist.txt -x .php,.html

    - With listable directory scraping enabled:
        dirble [address] --scrape-listable

    - Providing a list of extensions and a list of URIs:
        dirble [address] -X wordlists/web.lst -U uri-list.txt

    - Providing multiple hosts to scan via command line:
        dirble [address] -u [address]
'''


def test_help_is_exact_and_version_is_exact(run):
    help_result = run('--help')
    assert help_result.returncode == 0
    assert help_result.stderr == b''
    assert help_result.stdout.decode() == HELP
    version = run('--version')
    assert version.returncode == 0
    assert version.stdout == b'Dirble 1.4.2 (commit d520c82, build 2026-04-17)\n'
    assert version.stderr == b''


def test_no_arguments_returns_help_to_stderr(run):
    result = run()
    assert result.returncode == 2
    assert result.stdout == b''
    assert result.stderr.decode() == HELP


@pytest.mark.parametrize('word', ['scan', 'add', 'list', 'config', 'help'], ids=['scan', 'add', 'list', 'config', 'help'])
def test_bare_command_words_are_not_subcommands(run, word):
    result = run(word)
    assert result.returncode == 2
    assert b'invalid value' in result.stderr or b'relative URL' in result.stderr


def test_help_short_circuits_later_unknown_option_but_not_earlier(run):
    later = run('--help', '--unknown')
    assert later.returncode == 0 and later.stdout.decode() == HELP and later.stderr == b''
    earlier = run('--unknown', '--help')
    assert earlier.returncode == 2 and earlier.stdout == b''
    assert b"unexpected argument '--unknown' found" in earlier.stderr
    assert b"tip: to pass '--unknown' as a value, use '-- --unknown'" in earlier.stderr


def test_delimiter_help_is_validated_as_uri(run):
    result = run('--', '--help')
    assert result.returncode == 2
    assert b"invalid value '--help'" in result.stderr


def test_invalid_positional_url_diagnostic(run):
    result = run('invalid-url')
    assert result.returncode == 2 and result.stdout == b''
    assert result.stderr.decode() == "error: invalid value 'invalid-url' for '[uri]': relative URL without a base\n\nFor more information, try '--help'.\n"


def test_required_target_and_variadic_consumption(run):
    no_target = run('--wordlist', 'words.txt')
    assert no_target.returncode == 2 and no_target.stdout == b''
    assert no_target.stderr.decode() == "error: the following required arguments were not provided:\n  <uri|--uri-file <uri-file>|--uri <uri>>\n\nUsage: executable --wordlist <wordlist> <uri|--uri-file <uri-file>|--uri <uri>>\n\nFor more information, try '--help'.\n"
    consumed = run('-x', '.php', 'http://example.com')
    assert consumed.returncode == 2
    assert b'<uri|--uri-file <uri-file>|--uri <uri>>' in consumed.stderr


@pytest.mark.parametrize('option,value,needle', [
    ('--timeout', 'notanumber', b"invalid value 'notanumber' for '--timeout <timeout>'"),
    ('--max-errors', 'abc', b"invalid value 'abc' for '--max-errors <max_errors>'"),
    ('--max-threads', 'abc', b"invalid value 'abc' for '--max-threads <max-threads>'"),
    ('--max-threads', '0', b'0 is not in 1..=4294967295'),
    ('--max-threads', '4294967296', b'4294967296 is not in 1..=4294967295'),
    ('--max-threads', '999999999999999999999', b'number too large to fit in target type'),
], ids=['timeout-nonnumeric','errors-nonnumeric','threads-nonnumeric','threads-zero','threads-upper-bound','threads-overflow'])
def test_numeric_constraints(run, option, value, needle):
    result = run(option, value, 'http://example.com')
    assert result.returncode == 2 and result.stdout == b''
    assert needle in result.stderr
    assert b"For more information, try '--help'." in result.stderr


@pytest.mark.parametrize('verb', ['get','GET','HEAD','HeAd','post','POST'], ids=['get-lower','get-upper','head-upper','head-mixed','post-lower','post-upper'])
def test_verb_values_are_case_insensitive(run, site, wordlist, verb):
    words = wordlist('probe\n')
    site.set('/probe', body=b'ok')
    result = run(site.base, '--verb', verb, '--wordlist', words, '--no-proxy', '--disable-validator', '-r')
    assert result.returncode == 0


def test_invalid_verb_and_missing_values(run):
    invalid = run('http://example.com', '--verb', 'INVALID')
    assert invalid.returncode == 2 and b'[possible values: get, head, post]' in invalid.stderr
    missing = run('http://example.com', '--proxy')
    assert missing.returncode == 2 and b'--proxy' in missing.stderr


@pytest.mark.parametrize('args,first,usage', [
    (('--password','p'), b"--username <username>", b'Usage: executable --password <password> --username <username>'),
    (('--username','u'), b"--password <password>", b'Usage: executable --username <username> --password <password>'),
    (('--ext-sub',), b'<--extensions <extensions>...|--extension-file <extension-file>>', b'Usage: executable --ext-sub'),
    (('--force-extension',), b'<--extensions <extensions>...|--extension-file <extension-file>>', b'Usage: executable --force-extension'),
], ids=['password-needs-user','user-needs-password','ext-sub-needs-extensions','force-needs-extensions'])
def test_required_option_dependencies(run, args, first, usage):
    result = run('http://example.com', *args)
    assert result.returncode == 2
    assert first in result.stderr and usage in result.stderr


@pytest.mark.parametrize('args,expected', [
    (('--code-whitelist','200','--code-blacklist','404'), b"cannot be used with"),
    (('--silent','-v'), b"'--verbose...'"),
    (('--proxy','http://localhost:9','--no-proxy'), b"cannot be used with"),
    (('--burp','--proxy','http://localhost:9'), b"cannot be used with"),
], ids=['code-lists-conflict','silent-verbose-conflict','proxy-conflict','burp-proxy-conflict'])
def test_conflicting_options(run, args, expected):
    result = run('http://example.com', *args)
    assert result.returncode == 2
    assert expected in result.stderr


@pytest.mark.parametrize('arg', ['-1','-5'], ids=['negative-one','negative-five'])
def test_negative_numeric_looks_like_unknown_option(run, arg):
    result = run('http://example.com', '--timeout', arg)
    assert result.returncode == 2
    assert f"unexpected argument '{arg}'".encode() in result.stderr
    assert f"to pass '{arg}' as a value, use '-- {arg}'".encode() in result.stderr


def test_unknown_option_and_missing_value(run):
    unknown = run('http://example.com', '--not-real')
    assert unknown.returncode == 2 and b"unexpected argument '--not-real'" in unknown.stderr
    missing = run('http://example.com', '--timeout')
    assert missing.returncode == 2 and b'--timeout' in missing.stderr


def test_long_equals_syntax_and_invalid_length_specifier(run, site, wordlist):
    path = wordlist('here\n')
    valid = run(site.base, f'--wordlist={path}', '--timeout=0', '--max-threads=1', '--max-recursion-depth=0', '--no-proxy', '--disable-validator')
    assert valid.returncode == 0
    for invalid in ['5-2', 'abc']:
        result = run(site.base, '--wordlist', path, '--hide-lengths', invalid, '--no-proxy')
        assert result.returncode != 0 and result.stderr
