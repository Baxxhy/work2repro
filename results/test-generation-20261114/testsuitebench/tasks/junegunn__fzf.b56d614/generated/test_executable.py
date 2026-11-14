import os
import pathlib
import subprocess
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')
if not EXE.exists():
    EXE = ROOT.parent / 'executable'


def run(args=(), data=b'', env=None, timeout=8):
    e = os.environ.copy()
    e.pop('FZF_DEFAULT_OPTS', None)
    e.pop('FZF_DEFAULT_OPTS_FILE', None)
    e.pop('FZF_DEFAULT_COMMAND', None)
    if env:
        e.update(env)
    return subprocess.run([str(EXE), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, env=e, timeout=timeout)


CORPUS = (b'/usr/bin/fzf\n/usr/local/bin/fuzzy-finder\n/home/user/projects/fuzzy/finder.go\n'
          b'/home/user/projects/foo/zap/bar.go\n/opt/fuzzy-filter-tool/bin/fzf\n/var/log/fuzzy.log\n'
          b'/etc/config/fzf.conf\nsrc/foo/zebra/filter.c\nsrc/fuzzy/algorithm/finder.c\n'
          b'lib/fuzzy-matching/fzf-core.so\n')


def test_version_exact():
    r = run(['--version'])
    assert (r.returncode, r.stdout, r.stderr) == (0, b'0.68.0 (5676da4a)\n', b'')


@pytest.mark.parametrize('arg,name', [('--help', 'help'), ('-h', 'help-short'),
                                      ('--bash', 'bash'), ('--zsh', 'zsh'), ('--fish', 'fish')], ids=lambda x: x)
def test_fixed_payloads(arg, name):
    r = run([arg])
    expected = (ROOT / 'reference' / (('help.txt' if name.startswith('help') else name + '.txt'))).read_bytes()
    assert (r.returncode, r.stdout, r.stderr) == (0, expected, b'')


def test_man_has_required_sections():
    r = run(['--man'])
    assert r.returncode == 0 and not r.stderr and len(r.stdout) > 300
    low = r.stdout.lower()
    for word in (b'fzf', b'name', b'synopsis', b'description', b'options', b'fuzzy finder'):
        assert word in low


@pytest.mark.parametrize('args,diagnostic', [
    (['--unknown'], b'unknown option: --unknown\n'),
    (['--help', '--unknown'], b'unknown option: --unknown\n'),
    (['--unknown', '--help'], b'unknown option: --unknown\n'),
    (['word'], b''),
], ids=['unknown', 'unknown-after-help', 'unknown-before-help', 'positional'])
def test_option_parse_errors(args, diagnostic):
    r = run(args)
    assert r.returncode == 2 and r.stdout == b''
    if diagnostic:
        assert r.stderr == diagnostic
    else:
        assert r.stderr


def test_filter_basics_and_status():
    data = b'apple\nbanana\napricot\ncherry'
    r = run(['--filter=ap'], data)
    assert (r.returncode, r.stdout, r.stderr) == (0, b'apple\napricot\n', b'')
    r = run(['--filter=xyz'], data)
    assert (r.returncode, r.stdout) == (1, b'')
    r = run(['--filter='], b'')
    assert (r.returncode, r.stdout) == (1, b'')


def test_filter_explicit_modes_and_display_only_options():
    r = run(['--disabled', '--raw', '--multi', '--height=10', '--border', '--filter=a'],
            b'apple\nbanana\n')
    assert r.returncode == 0 and r.stdout == b'apple\nbanana\n'


def test_newline_record_rules_and_crlf():
    r = run(['--filter=', '--no-sort'], b'one\r\ntwo\nthree\r\nfour')
    assert r.stdout == b'one\r\ntwo\nthree\r\nfour\n'
    cases = [(b'a\n', b'a\n'), (b'\na', b'\na\n'),
             (b'a\n\nb', b'a\n\n b\n'.replace(b' ', b'')),
             (b'\n\n', b'\n\n')]
    for data, expected in cases:
        assert run(['--filter=', '--no-sort'], data).stdout == expected


def test_read0_print0_round_trip_and_negations():
    data = b'one\nline\0\0two\r\n'
    r = run(['--read0', '--print0', '--filter=', '--no-sort'], data)
    assert (r.returncode, r.stdout) == (0, data)
    r = run(['--read0', '--no-read0', '--print0', '--no-print0', '--filter=', '--no-sort'], b'a\nb\n')
    assert r.stdout == b'a\nb\n'


def test_read0_default_scoring_example():
    r = run(['--read0', '--filter=txt'], b'normal.txt\0file with spaces.txt\0file\twith\ttabs.txt\0')
    assert r.stdout == b'normal.txt\nfile\twith\ttabs.txt\nfile with spaces.txt\n'


def test_sync_example_and_tail():
    data = b'apple\nbanana\ncherry\ndate\neggplant\nfig\ngrape\n'
    assert run(['--sync', '--filter=a'], data).stdout == b'apple\ndate\ngrape\nbanana\neggplant\n'
    assert run(['--sync', '--tail=3', '--no-sort', '--filter='], b'one\ntwo\nthree\nfour\n').stdout == b'two\nthree\nfour\n'
    assert run(['--filter=line', '--tail=10'], b''.join(f'line{i}\n'.encode() for i in range(100))).stdout == b''.join(f'line{i}\n'.encode() for i in range(90, 100))


def test_filter_unsynced_no_sort_tail_exception():
    assert run(['--tail=2', '--no-sort', '--filter='], b'one\ntwo\nthree\nfour\n').stdout == b'one\ntwo\nthree\nfour\n'


def test_sorting_score_examples():
    assert run(['--filter=oBZ'], b'foo bar baz\nfooBarbaz1\n').stdout.startswith(b'fooBarbaz1\n')
    assert run(['--filter=fzf'], b'fuzzy-finder\nfind fuzzy filter\n').stdout == b'find fuzzy filter\nfuzzy-finder\n'
    assert run(['--filter=a'], b'zebra\nyak\nxray\nsnake\nrabbit\nquail\n').stdout == b'yak\nxray\nzebra\nsnake\nquail\nrabbit\n'


def test_exact_and_algorithms():
    assert run(['-e', '--filter=abc'], b'a---b---c\nabc\n').stdout == b'abc\n'
    assert run(['+e', '--filter=abc'], b'a---b---c\nabc\n').stdout == b'abc\na---b---c\n'
    for algo in ('v1', 'v2'):
        assert run([f'--algo={algo}', '--filter=abc'], b'a---b---c\n').returncode == 0
    r = run(['--algo=bad', '--filter=x'])
    assert r.returncode == 2 and b'invalid algorithm (expected: v1 or v2)' in r.stderr


def test_extended_search_and_operators():
    assert run(["--filter='app'"], b'app\napple\nthe app\n').stdout == b'app\nthe app\n'
    assert run(['--filter=^/usr'], CORPUS).stdout.startswith(b'/usr/bin/fzf\n/usr/local/bin/')
    assert run(['--filter=!.go$'], CORPUS).stdout == (b'/usr/bin/fzf\n/usr/local/bin/fuzzy-finder\n/opt/fuzzy-filter-tool/bin/fzf\n'
         b'/var/log/fuzzy.log\n/etc/config/fzf.conf\nsrc/foo/zebra/filter.c\nsrc/fuzzy/algorithm/finder.c\nlib/fuzzy-matching/fzf-core.so\n')
    assert run(["--filter=fzf | 'fuzzy 'finder"], CORPUS).stdout == b'/home/user/projects/fuzzy/finder.go\n/usr/local/bin/fuzzy-finder\nsrc/fuzzy/algorithm/finder.c\n'
    assert run(['--filter=ap | ch'], b'apple\ncherry\nbanana\n').stdout == b'apple\ncherry\n'
    assert run(['--filter=ap !apple'], b'apple\napricot\n').stdout == b'apricot\n'
    assert run(['+x', '--filter=^abc'], b'^abc\nabc\n').stdout == b'^abc\n'


def test_case_and_accent_handling():
    rows = b'FooBar\nfoobar\nFOOBAR\nFoObAr\nfoo_bar\nFOO_BAR\n'
    assert run(['--filter=foo'], rows).stdout == rows
    assert run(['--ignore-case', '--filter=FOO'], rows).stdout == rows
    assert run(['--filter=a'], 'a\ná\nA\nÁ\n'.encode()).stdout == 'a\ná\nA\nÁ\n'.encode()
    assert run(['--filter=á'], 'a\ná\nA\nÁ\n'.encode()).stdout == 'á\nÁ\n'.encode()
    assert run(['--literal', '--filter=cafe'], 'café\n'.encode()).returncode == 1


def test_no_sort_tac_and_empty_query():
    data = b'one\ntwo\nthree\n'
    assert run(['--no-sort', '--filter=o'], data).stdout == b'one\ntwo\n'
    assert run(['--tac', '--no-sort', '--filter='], data).stdout == b'three\ntwo\none\n'


def test_field_scopes_and_output_transform():
    assert run(['-d:', '--nth=2..3,1,-1', '--filter=bbcc'], b'aa:bb:cc:dd\n').stdout == b'aa:bb:cc:dd\n'
    assert run(['-d:', '--nth=2..3,1,-1', '--filter=bbccaa'], b'aa:bb:cc:dd\n').returncode == 1
    assert run(['--accept-nth=1,3', '--filter=a'], b'a b c\n').stdout == b'a c\n'
    assert run(['--accept-nth=2,1', '--filter=a'], b'a b\n').stdout == b'ba\n'
    assert run(['--accept-nth={1}:{2}', '--filter=foo'], b'foo bar\n').stdout == b'foo:bar\n'
    r = run(['--with-nth=invalid', '--filter=test'])
    assert r.returncode == 2 and r.stderr == b'template should include at least 1 placeholder: invalid\n'


def test_ansi_cleaning_and_preservation():
    esc = b'\x1b'
    colored = esc + b'[31mfoo' + esc + b'[m\n'
    assert run(['--ansi', '--filter=foo'], colored).stdout == b'foo\n'
    assert run(['--filter=foo'], colored).stdout == colored
    data = b'a\x1b[2Kb\x1b(0c\x0fd\x08e\n'
    assert run(['--ansi', '--filter='], data).stdout == b'abe\n'
    assert run(['--ansi', '--filter=abcde'], data).returncode == 1


def test_print_query_and_expect():
    r = run(['--print-query', '--filter=ap'], b'apple\nbanana\n')
    assert r.stdout == b'ap\napple\n'
    r = run(['--print-query', '--filter=none'], b'apple\n')
    assert r.returncode == 1 and r.stdout == b'none\n'
    r = run(['--expect='], b'x\n')
    assert r.returncode == 2 and r.stdout == b'' and r.stderr == b'key names required\n'
    assert run(['--select-1', '--filter=a'], b'apple\nbanana\n').stdout == b'apple\nbanana\n'


@pytest.mark.parametrize('args,stderr', [
    (['--scheme=invalid', '--filter=test'], b'invalid scoring scheme: invalid (expected: default|path|history)\n'),
    (['--tiebreak=length,length', '--filter=test'], b'duplicate sort criteria: length\n'),
    (['--tiebreak=index,begin', '--filter=test'], b'index should be the last criterion\n'),
    (['--tiebreak=length,chunk,begin,end', '--filter=test'], b'at most 3 tiebreaks are allowed\n'),
    (['--info=invalid', '--filter=test'], b'invalid info style (expected: default|right|hidden|inline[-right][:PREFIX])\n'),
    (['--tail=0', '--filter=test'], b'number of items to keep must be a positive integer\n'),
    (['--tabstop=0', '--filter=test'], b'tab stop must be a positive integer\n'),
    (['--header-lines=-1', '--filter=test'], b'header lines must be a non-negative integer\n'),
    (['--hscroll-off=-1', '--filter=test'], b'hscroll offset must be a non-negative integer\n'),
    (['--scroll-off=-1', '--filter=test'], b'scroll offset must be a non-negative integer\n'),
    (['--freeze-left=-1', '--filter=test'], b'number of fields to freeze must be a non-negative integer\n'),
    (['--jump-labels=', '--filter=test'], b'empty jump labels\n'),
    (['--min-height=-1', '--filter=test'], b'minimum height must be a non-negative integer\n'),
    (['--marker-multi-line=xxxx', '--filter=test'], b'invalid total marker width: 4\n'),
    (['--preview-window=100%', '--filter=test'], b'window size too large (max: 99%)\n'),
    (['--walker=hidden', '--filter=test'], b"at least one of 'file' or 'dir' should be specified\n"),
], ids=['bad-scheme', 'duplicate-tiebreak', 'index-not-last', 'too-many-tiebreaks', 'bad-info',
        'tail-zero', 'tabstop-zero', 'negative-header-lines', 'negative-hscroll', 'negative-scroll',
        'negative-freeze', 'empty-jump-labels', 'negative-min-height', 'bad-marker-width',
        'preview-too-large', 'walker-without-kind'])
def test_documented_validation_errors(args, stderr):
    r = run(args)
    assert r.returncode == 2 and r.stdout == b'' and r.stderr == stderr


@pytest.mark.parametrize('value', ['999', '256', '-2', '-5', '#gggggg', '#12345', '#1234567', 'ff0000', 'red:invalid-attr', 'invalid-component:red'],
                         ids=['high', 'too-high', 'negative2', 'negative5', 'bad-hex', 'short-hex', 'long-hex', 'missing-hash', 'bad-attr', 'bad-component'])
def test_invalid_color_members(value):
    r = run([f'--color=fg:{value}', '--filter=test'])
    assert r.returncode == 2 and r.stdout == b''
    assert r.stderr == f'invalid color specification: fg:{value}\n'.encode()


def test_color_valid_and_invalid_nth():
    assert run(['--color=query:9,disabled:10', '--filter=test'], b'test\nother\n').stdout == b'test\n'
    assert run(['--color=fg:red:blink', '--filter=test'], b'test\n').stdout == b'test\n'
    r = run(['--color=nth:red', '--filter=test'])
    assert r.returncode == 2 and r.stderr == b"only ANSI attributes are allowed for 'nth' (regular, bold, underline, reverse, dim, italic, strikethrough)\n"


def test_config_precedence_and_shellword_query():
    r = run(['--filter=banana'], b'apple\nbanana\n', env={'FZF_DEFAULT_OPTS': '--filter=apple'})
    assert r.stdout == b'banana\n'
    r = run([], b'two words\ntwo-other-words\n', env={'FZF_DEFAULT_OPTS': '--exact --filter=two\\ words'})
    assert r.stdout == b'two words\ntwo-other-words\n'
    r = run(['--help'], b'', env={'FZF_DEFAULT_OPTS': "'unterminated"})
    assert r.returncode == 2 and r.stdout == b'' and r.stderr.startswith(b'$FZF_DEFAULT_OPTS:')


def test_history_file_created_before_size_validation(tmp_path):
    p = tmp_path / 'history'
    r = run([f'--history={p}', '--history-size=0', '--filter=test'])
    assert r.returncode == 2 and r.stdout == b'' and r.stderr == b'history max must be a positive integer\n'
    assert p.exists() and p.read_bytes() == b'' and (p.stat().st_mode & 0o777) == 0o600


def test_history_invalid_path_message():
    r = run(['--history=/dev/null/invalid', "--filter=''"])
    assert r.returncode == 2 and r.stderr == b'invalid history file: open /dev/null/invalid: not a directory\n'


def test_tmux_filter_valid_and_invalid():
    assert run(['--tmux=center,1,2,3', '--filter='], b'x\n').stdout == b'x\n'
    r = run(['--tmux=invalid', '--filter=test'])
    assert r.returncode == 2 and r.stdout == b''
    assert r.stderr == b'invalid tmux option: invalid (expected: [center|top|bottom|left|right][,SIZE[%]][,SIZE[%][,border-native]])\n'
    r = run(['--tmux=center,1,2,3,4', '--filter='])
    assert r.returncode == 2 and b'invalid tmux option' in r.stderr


def test_bind_validation_and_transform_colon_forms():
    errors = [('ctrl-a', b'bind action not specified: ctrl-a\n'),
              (':accept', b'key name required\n'), ('invalid-key:abort', b'unsupported key: invalid-key\n'),
              ('ctrl-a:unbind()', b'unbind target required\n'), ('ctrl-a:rebind()', b'rebind target required\n'),
              ('ctrl-a:toggle-bind()', b'toggle-bind target required\n'), ('ctrl-a:put', b'unable to put non-printable character\n')]
    for binding, expected in errors:
        r = run(['--filter=test', '--bind=' + binding])
        assert r.returncode == 2 and r.stdout == b'' and r.stderr == expected
    for binding in ('ctrl-a:transform:echo', 'ctrl-a:bg-transform:echo', 'ctrl-a:bg-transform-list-label:echo'):
        r = run(['--filter=', '--bind', binding], b'line1\nline2\nline3\n')
        assert r.returncode == 0 and r.stdout == b'line1\nline2\nline3\n' and r.stderr == b''


def test_info_command_filter_empty():
    r = run(['--filter', '', '--info-command', 'echo custom'], b'')
    assert (r.returncode, r.stdout, r.stderr) == (1, b'', b'')


def test_large_binary_unicode_and_long_records():
    data = b'good\ninvalid-' + b'\xff\xfe' + b'-byte'
    expected = b'good\ninvalid-' + '��'.encode() + b'-byte\n'
    r = run(['--filter=', '--no-sort'], data)
    assert r.stdout == expected
    long = b'a' * 50000 + b'\n'
    assert run(['--filter=', '--no-sort'], long, timeout=5).stdout == long
    many = b''.join(f'item{i}\n'.encode() for i in range(100000))
    r = run(['--sync', '--no-sort', '--filter='], many, timeout=5)
    assert r.returncode == 0 and r.stdout == many


def test_nul_input_bytes_remain_data_in_newline_mode():
    assert run(['--filter=', '--no-sort'], b'a\0b\n').stdout == b'a\0b\n'


def test_output_accepts_print0_query_delimiter():
    r = run(['--print-query', '--print0', '--filter=x'], b'x\ny\n')
    assert r.stdout == b'x\0x\0'
