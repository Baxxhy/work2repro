import os
import pathlib
import re
import subprocess
import time
import pytest

BIN = pathlib.Path('/workspace/executable')


def invoke(args=(), *, cwd, env=None, timeout=15):
    e = os.environ.copy()
    e['TERM'] = 'xterm'
    e.update({'NO_COLOR': '1'})
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def write(path, data):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode())
    return path


def replace(tmp_path, keyword, replacement, paths=None, flags=(), *, env=None):
    args = [*flags, keyword, replacement]
    if paths is not None:
        args.extend(map(str, paths if isinstance(paths, (list, tuple)) else [paths]))
    return invoke(args, cwd=tmp_path, env=env)


def test_version_and_alias(tmp_path):
    for flag in ('--version', '-V'):
        p = invoke([flag], cwd=tmp_path)
        assert p.returncode == 0 and p.stdout == b'ambr 0.6.0\n' and p.stderr == b''


def test_help_precedes_missing_operands_and_has_documented_sections(tmp_path):
    for flag in ('--help', '-h'):
        p = invoke([flag], cwd=tmp_path)
        assert p.returncode == 0 and not p.stderr
        s = p.stdout.decode()
        assert s.startswith('ambr 0.6.0\n\nUSAGE:') and s.endswith('\n')
        assert all(x in s for x in ('FLAGS:', 'OPTIONS:', 'ARGS:', '--max-threads <NUM>', '--mmap-bytes <BYTES>'))
        assert 'SUBCOMMANDS:' not in s and 'COMMANDS:' not in s and '\x1b' not in s
        assert re.search(r'--max-threads <NUM>\s+Number of max threads \[default: [0-9]+\]', s)


def test_missing_operands_are_parse_errors(tmp_path):
    p = invoke([], cwd=tmp_path)
    err = p.stderr.decode(errors='replace')
    assert p.returncode == 1 and '<KEYWORD>' in err and '<REPLACEMENT>' in err and 'USAGE:' in err
    p = invoke(['only-key'], cwd=tmp_path)
    assert p.returncode == 1 and '<REPLACEMENT>' in p.stderr.decode()


def test_two_words_are_operands_not_subcommands(tmp_path):
    f = write(tmp_path / 'f', 'add help list remove')
    p = replace(tmp_path, 'add', 'X', f)
    assert p.returncode == 0 and f.read_text() == 'X help list remove'


@pytest.mark.parametrize('option', ['--VERBOSE', '--Verbose', '-verbose', '-z', '-rv'], ids=['upper', 'mixed', 'single_dash_long', 'unknown_short', 'bundled_short'])
def test_invalid_option_spellings(tmp_path, option):
    p = invoke([option, 'k', 'r'], cwd=tmp_path)
    err = p.stderr.decode(errors='replace')
    assert p.returncode != 0 and option.lstrip('-')[-1:] in err and 'USAGE:' in err


def test_triple_dash_verbose_is_accepted(tmp_path):
    write(tmp_path / 'bin', b'\x00abc')
    p = replace(tmp_path, 'a', 'x', tmp_path, flags=['---verbose', '--no-interactive'])
    assert p.returncode == 0 and b'Skip (binary)' in p.stderr


@pytest.mark.parametrize('option', ['--max-threads', '--size-per-thread', '--bin-check-bytes', '--mmap-bytes'], ids=['threads', 'size', 'binary_probe', 'mmap'])
def test_numeric_options_accept_equals_and_space_forms(tmp_path, option):
    f = write(tmp_path / 'f', 'aa')
    for form in ([option, '2'], [option + '=2']):
        f.write_text('aa')
        p = replace(tmp_path, 'a', 'x', f, flags=['--no-interactive', *form])
        assert p.returncode == 0 and f.read_text() == 'xx'


@pytest.mark.parametrize('value', ['', 'nope'], ids=['empty', 'nonnumeric'])
def test_invalid_numeric_values(tmp_path, value):
    p = invoke(['--max-threads=' + value, 'k', 'r'], cwd=tmp_path)
    assert p.returncode != 0 and b'--max-threads' in p.stderr and b'USAGE:' in p.stderr
    if value:
        assert b'invalid digit found in string' in p.stderr


def test_negative_and_overflow_numeric_values_rejected(tmp_path):
    p = invoke(['--max-threads', '-1', 'k', 'r'], cwd=tmp_path)
    assert p.returncode != 0
    p = invoke(['--max-threads', '999999999999999999999999999999999999', 'k', 'r'], cwd=tmp_path)
    assert p.returncode != 0 and b'too large' in p.stderr.lower()


def test_duplicate_options_and_regex_alias_are_rejected(tmp_path):
    for args in (['--verbose', '--verbose', 'k', 'r'], ['-r', '--regex', 'k', 'r']):
        p = invoke(args, cwd=tmp_path)
        assert p.returncode != 0 and b'provided more than once' in p.stderr


def test_literal_nonoverlap_adjacent_and_replacement_not_rescanned(tmp_path):
    f = write(tmp_path / 'f', 'aaaa a')
    p = replace(tmp_path, 'aa', 'aaa', f, flags=['--no-interactive'])
    assert p.returncode == 0 and f.read_text() == 'aaaaa a'


def test_literal_is_case_sensitive_and_regex_metacharacters_are_literal(tmp_path):
    f = write(tmp_path / 'f', 'a.* A.* aXX')
    replace(tmp_path, 'a.*', 'Q', f, flags=['--no-interactive'])
    assert f.read_text() == 'Q A.* aXX'


def test_direct_escape_sequences_and_overlapping_backslash_processing(tmp_path):
    f = write(tmp_path / 'f', 'line1\nline2 \\\\n')
    replace(tmp_path, r'line1\nline2', 'X', f, flags=['--no-interactive'])
    assert f.read_text().startswith('X ')
    f.write_bytes(b'\\n')
    replace(tmp_path, r'\\n', 'Y', f, flags=['--no-interactive'])
    assert f.read_bytes() == b'Y'


def test_literal_preserves_line_endings_and_final_newline_state(tmp_path):
    f = write(tmp_path / 'f', b'a\r\na\n\r\na')
    replace(tmp_path, 'a', 'b', f, flags=['--no-interactive'])
    assert f.read_bytes() == b'b\r\nb\n\r\nb'


@pytest.mark.parametrize('pattern,repl,source,expected', [
    (r'\d+', 'N', 'a12 b3', 'aN bN'),
    ('(cat)(s?)', '$2-$1', 'cats cat', 's-cat -cat'),
    ('(?<word>hi)', '${word}!', 'hi hi', 'hi! hi!'),
    ('(?P<x>a)(b)', '$2$1', 'ab', 'ba'),
    ('(a)(b)(c)(d)(e)(f)(g)(h)(i)(j)(k)', '$10-${11}', 'abcdefghijk', 'j-k'),
    ('(word)', '$$1', 'word', '$1'),
    ('a', r'\n\t', 'a', '\n\t'),
])
def test_regex_replacement_and_capture_expansion(tmp_path, pattern, repl, source, expected):
    f = write(tmp_path / 'f', source)
    p = replace(tmp_path, pattern, repl, f, flags=['--no-interactive', '--regex'])
    assert p.returncode == 0 and f.read_text() == expected


def test_regex_unicode_multiline_and_zero_length_examples(tmp_path):
    f = write(tmp_path / 'f', 'café\nHELLO')
    replace(tmp_path, r'(?i)^hello$', 'X', f, flags=['--no-interactive', '-r'])
    assert f.read_text() == 'café\nX'
    f.write_text('hello world')
    replace(tmp_path, '', 'X', f, flags=['--no-interactive', '--regex'])
    assert f.read_text() == 'XhXeXlXlXoX XwXoXrXlXdX'


def test_regex_invalid_pattern_is_no_match_and_backrefs_unsupported(tmp_path):
    for pattern in ('(', '[', r'\q', '(?=x)', r'(word)\1'):
        f = write(tmp_path / 'f', 'word word')
        p = replace(tmp_path, pattern, 'X', f, flags=['--no-interactive', '--regex'])
        assert p.returncode == 0 and f.read_text() == 'word word'


def test_empty_regex_also_handles_alternation_zero_length(tmp_path):
    f = write(tmp_path / 'f', 'hello world')
    replace(tmp_path, 'hello|', 'X', f, flags=['--no-interactive', '--regex'])
    assert f.read_text() == 'X XwXoXrXlXdX'


def test_binary_detection_and_probe_length(tmp_path):
    f = write(tmp_path / 'f', b'a' * 256 + b'\x00abc')
    replace(tmp_path, 'a', 'x', f, flags=['--no-interactive'])
    assert f.read_bytes() == b'a' * 256 + b'\x00abc'
    replace(tmp_path, 'a', 'x', f, flags=['--no-interactive', '--bin-check-bytes', '257'])
    assert f.read_bytes().startswith(b'x' * 256)


def test_binary_mode_preserves_unrelated_arbitrary_bytes(tmp_path):
    f = write(tmp_path / 'f', bytes(range(256)) + b'\x00\x01')
    key = write(tmp_path / 'key', b'\x00\x01')
    p = invoke(['--no-interactive', '--binary', '--key-from-file', str(key), 'Z', str(f)], cwd=tmp_path)
    assert p.returncode == 0 and f.read_bytes() == bytes(range(256)) + b'Z'


def test_regex_binary_target_requires_valid_utf8(tmp_path):
    f = write(tmp_path / 'f', b'\xff\x00ab12cd\xfe')
    replace(tmp_path, r'\d+', 'X', f, flags=['--no-interactive', '--regex', '--binary'])
    assert f.read_bytes() == b'\xff\x00ab12cd\xfe'


def test_binary_tab_only_is_text(tmp_path):
    f = write(tmp_path / 'f', b'a\tb')
    replace(tmp_path, 'a', 'X', f, flags=['--no-interactive'])
    assert f.read_bytes() == b'X\tb'


def test_key_and_replacement_file_sources_are_verbatim(tmp_path):
    k = write(tmp_path / 'key', 'cat\n')
    r = write(tmp_path / 'rep', 'DOG\n')
    f = write(tmp_path / 'target', b'cat\n cat\n')
    p = replace(tmp_path, str(k), str(r), f, flags=['--no-interactive', '--key-from-file', '--rep-from-file'])
    assert p.returncode == 0 and f.read_bytes() == b'DOG\n cat\n'


def test_empty_replacement_and_directory_or_invalid_utf8_replacement_source(tmp_path):
    f = write(tmp_path / 'target', 'abab')
    empty = write(tmp_path / 'empty', b'')
    replace(tmp_path, 'ab', str(empty), f, flags=['--no-interactive', '--rep-from-file'])
    assert f.read_text() == ''
    f.write_bytes(b'\x00\x01x\x00\x01')
    invalid = write(tmp_path / 'invalid', b'\xff\x00')
    replace(tmp_path, '\x00\x01', str(invalid), f, flags=['--no-interactive', '--binary', '--rep-from-file'])
    assert f.read_bytes() == b'x'
    f.write_text('abab')
    d = tmp_path / 'directory'; d.mkdir()
    replace(tmp_path, 'ab', str(d), f, flags=['--no-interactive', '--rep-from-file'])
    assert f.read_text() == ''


def test_source_errors_precede_target_changes(tmp_path):
    target = write(tmp_path / 'target', 'abc')
    for args, message in [(['--key-from-file', str(tmp_path / 'absent'), 'r', str(target)], b'file not found'),
                          (['--key-from-file', '/dev/null', 'r', str(target)], b'file is empty'),
                          (['--key-from-file', str(write(tmp_path / 'bad', b'\x00\xff')), 'r', str(target), '--binary'], b'file is empty')]:
        p = invoke(['--no-interactive', *args], cwd=tmp_path)
        assert p.returncode == 1 and message in p.stderr and target.read_text() == 'abc'


def test_invalid_utf8_keyword_source_is_empty_but_nul_is_valid(tmp_path):
    k = write(tmp_path / 'key', b'\x00\xff')
    target = write(tmp_path / 'target', b'a\x00b')
    p = invoke(['--no-interactive', '--binary', '--key-from-file', str(k), 'x', str(target)], cwd=tmp_path)
    assert p.returncode == 1 and b'file is empty' in p.stderr and target.read_bytes() == b'a\x00b'
    k.write_bytes(b'\x00')
    p = invoke(['--no-interactive', '--binary', '--key-from-file', str(k), 'x', str(target)], cwd=tmp_path)
    assert p.returncode == 0 and target.read_bytes() == b'axb'


def test_hidden_files_recursive_and_no_recursive(tmp_path):
    write(tmp_path / '.hidden' / 'f', 'foo')
    write(tmp_path / 'top', 'foo')
    p = replace(tmp_path, 'foo', 'X', tmp_path, flags=['--no-interactive', '--no-recursive'])
    assert p.returncode == 0 and (tmp_path / 'top').read_text() == 'X' and (tmp_path / '.hidden/f').read_text() == 'foo'
    replace(tmp_path, 'foo', 'Y', tmp_path, flags=['--no-interactive'])
    assert (tmp_path / '.hidden/f').read_text() == 'Y'


def test_explicit_paths_all_processed_in_fixed_sorted_order_with_statistics(tmp_path):
    paths = [write(tmp_path / n, 'foo') for n in ('zeta', 'alpha', 'middle')]
    p = replace(tmp_path, 'foo', 'X', paths, flags=['--no-interactive', '--statistics', '--no-color'])
    assert p.returncode == 0 and all(x.read_text() == 'X' for x in paths)
    s = p.stderr.decode(errors='replace')
    assert 'Statistics' in s and s.index('alpha') < s.index('middle') < s.index('zeta') if all(x.name in s for x in paths) else 'Statistics' in s


def test_gitignore_globs_negation_and_directory_only(tmp_path):
    write(tmp_path / '.gitignore', '*.log\n!keep.log\ncache/\n')
    write(tmp_path / 'a.log', 'foo'); write(tmp_path / 'keep.log', 'foo')
    write(tmp_path / 'cache' / 'inside', 'foo'); write(tmp_path / 'sub' / 'x.log', 'foo')
    replace(tmp_path, 'foo', 'X', tmp_path, flags=['--no-interactive'])
    assert (tmp_path / 'a.log').read_text() == 'foo'
    assert (tmp_path / 'keep.log').read_text() == 'X'
    assert (tmp_path / 'cache/inside').read_text() == 'foo'
    assert (tmp_path / 'sub/x.log').read_text() == 'foo'


def test_gitignore_anchoring_nested_rules_and_parent_ignore(tmp_path):
    root = tmp_path / 'root'; root.mkdir()
    write(tmp_path / '.gitignore', '*.ban\n')
    write(root / '.gitignore', '/only.txt\ndir1/file\n')
    write(root / 'only.txt', 'foo'); write(root / 'deep/only.txt', 'foo')
    write(root / 'dir1/file', 'foo'); write(root / 'x/dir1/file', 'foo')
    write(root / 'x.ban', 'foo')
    replace(tmp_path, 'foo', 'X', root, flags=['--no-interactive'])
    assert (root / 'only.txt').read_text() == 'foo' and (root / 'deep/only.txt').read_text() == 'X'
    assert (root / 'dir1/file').read_text() == 'foo' and (root / 'x/dir1/file').read_text() == 'X'
    assert (root / 'x.ban').read_text() == 'X'


def test_gitignore_can_be_disabled_and_vcs_filter_is_independent(tmp_path):
    write(tmp_path / '.gitignore', '*.txt\n')
    write(tmp_path / 'a.txt', 'foo'); write(tmp_path / '.git/inside', 'foo'); write(tmp_path / '.bzr/inside', 'foo')
    replace(tmp_path, 'foo', 'X', tmp_path, flags=['--no-interactive', '--no-skip-gitignore'])
    assert (tmp_path / 'a.txt').read_text() == 'X' and (tmp_path / '.git/inside').read_text() == 'foo'
    replace(tmp_path, 'foo', 'Y', tmp_path, flags=['--no-interactive', '--no-skip-vcs'])
    assert (tmp_path / '.git/inside').read_text() == 'Y' and (tmp_path / '.bzr/inside').read_text() == 'Y'


def test_skipped_binary_reporting_and_no_reporting_default(tmp_path):
    f = write(tmp_path / 'bin', b'\x00foo')
    p = replace(tmp_path, 'foo', 'X', f, flags=['--no-interactive'])
    assert b'Skip (binary)' not in p.stderr and f.read_bytes() == b'\x00foo'
    p = replace(tmp_path, 'foo', 'X', f, flags=['--no-interactive', '--skipped', '--no-color'])
    assert b'Skip (binary)    :' in p.stderr and b'"' in p.stderr


def test_statistics_format_thread_count_zero_match_and_no_color(tmp_path):
    f = write(tmp_path / 'f', 'nothing')
    p = replace(tmp_path, 'missing', 'X', f, flags=['--no-interactive', '--statistics', '--max-threads', '4', '--no-color'])
    s = p.stderr.decode(errors='replace')
    assert p.returncode == 0 and 'Statistics' in s and 'Max threads: 4' in s
    assert [f'Match{i:02d}' for i in range(4)] == re.findall(r'Match\d{2}', s)
    assert '\x1b' not in s and re.search(r'Find\s+: \d+s / [0-9.]+s', s)


def test_thread_tuning_does_not_change_results(tmp_path):
    for n in ('1', '2', '4', '8', '10000'):
        f = write(tmp_path / ('f' + n), 'ababab')
        p = replace(tmp_path, 'ab', 'X', f, flags=['--no-interactive', '--max-threads', n])
        assert p.returncode == 0 and f.read_text() == 'XXX'


def test_timestamp_default_and_preserve_time(tmp_path):
    f = write(tmp_path / 'f', 'foo')
    old = 1_600_000_000_000_000_000
    os.utime(f, ns=(old, old))
    replace(tmp_path, 'foo', 'X', f, flags=['--no-interactive', '--no-preserve-time'])
    assert f.stat().st_mtime_ns > old
    f.write_text('foo'); os.utime(f, ns=(old, old))
    replace(tmp_path, 'foo', 'Y', f, flags=['--no-interactive', '--preserve-time'])
    assert f.read_text() == 'Y' and abs(f.stat().st_mtime_ns - old) < 2_000_000_000


def test_symlink_files_directories_and_deduplication(tmp_path):
    real = write(tmp_path / 'real', 'foo')
    (tmp_path / 'alias').symlink_to(real)
    p = replace(tmp_path, 'foo', 'X', [real, tmp_path / 'alias'], flags=['--no-interactive'])
    assert p.returncode == 0 and real.read_text() == 'X'
    real.write_text('foo')
    p = replace(tmp_path, 'foo', 'Y', tmp_path, flags=['--no-interactive', '--no-symlink'])
    assert real.read_text() == 'Y'


def test_malformed_config_is_ignored(tmp_path):
    home = tmp_path / 'home'; home.mkdir(); write(home / '.ambr.toml', 'not = [valid')
    f = write(tmp_path / 'f', 'foo')
    p = replace(tmp_path, 'foo', 'X', f, flags=['--no-interactive'], env={'HOME': str(home)})
    assert p.returncode == 0 and f.read_text() == 'X' and b'not = [valid' not in p.stdout + p.stderr


def test_no_match_is_silent_and_unchanged(tmp_path):
    f = write(tmp_path / 'f', 'unchanged')
    p = replace(tmp_path, 'absent', 'X', f, flags=['--no-interactive'])
    assert p.returncode == 0 and f.read_text() == 'unchanged'
    # Backend cleanup sequences are permitted by the contract; no ordinary message is expected.
    assert b'Statistics' not in p.stderr and b'Skip (' not in p.stderr
