import json
import os
import pathlib
import re
import subprocess
import tempfile

BIN = pathlib.Path('/workspace/executable')


def run(*args, cwd=None, env=None, data=None, timeout=8):
    e = os.environ.copy()
    e['NO_COLOR'] = '1'
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd, env=e,
                          input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def decoded(p):
    return p.stdout.decode('utf-8', 'replace'), p.stderr.decode('utf-8', 'replace')


def test_version_exact():
    p = run('--version')
    assert p.returncode == 0 and p.stdout == b'Dust 1.2.3\n' and p.stderr == b''


def test_help_forms_and_parser_precedence():
    long = run('--help')
    short = run('-h')
    assert long.returncode == short.returncode == 0
    assert b'Usage: executable [OPTIONS] [PATH]...' in long.stdout
    assert b'--files-from' in long.stdout and b'--output-json' in long.stdout
    assert b'Usage: executable [OPTIONS] [PATH]...' in short.stdout
    for p in (long, short):
        assert not p.stderr
    bad = run('--not-a-real-option', '--help', '--depth')
    assert bad.returncode == 2 and not bad.stdout
    assert b'unexpected argument' in bad.stderr


def test_parser_errors_and_duplicate_aliases():
    for args, needle in [(("--depth",), b'value is required'),
                         (("--depth", "oops"), b'invalid value'),
                         (("-d", "1", "--depth", "2"), b'cannot be used multiple times'),
                         (("--only-dir", "--only-file"), b'cannot be used with')]:
        p = run(*args)
        assert p.returncode == 2 and not p.stdout and needle in p.stderr
        assert b"For more information, try '--help'." in p.stderr


def test_scans_words_as_paths_and_unicode_paths(tmp_path):
    d = tmp_path / 'space 雪'
    d.mkdir()
    (d / 'run').write_text('x')
    p = run('-b', '-P', d)
    out, _ = decoded(p)
    assert p.returncode == 0 and 'run' in out and 'space 雪' in out


def test_file_root_and_empty_directory(tmp_path):
    f = tmp_path / 'one file'
    f.write_bytes(b'x')
    empty = tmp_path / 'empty'
    empty.mkdir()
    out = decoded(run('-b', '-P', f))[0]
    assert 'one file' in out and '4.0K' in out
    out = decoded(run('-b', '-P', empty))[0]
    assert 'empty' in out and '4.0K' in out


def test_directory_aggregate_and_apparent_size(tmp_path):
    d = tmp_path / 'root'
    d.mkdir()
    (d / 'a').write_bytes(b'a' * 2)
    out = decoded(run('-b', '-P', d))[0]
    assert 'a' in out and 'root' in out
    app = decoded(run('-s', '-b', '-P', d))[0]
    assert app != out


def test_synthetic_total_and_duplicate_roots(tmp_path):
    a = tmp_path / 'a'; b = tmp_path / 'b'
    a.write_bytes(b'x'); b.write_bytes(b'y')
    out = decoded(run('-b', '-P', a, b, a))[0]
    assert '(total)' in out and out.count('a') >= 1 and out.count('b') >= 1


def test_missing_roots_are_all_or_nothing(tmp_path):
    good = tmp_path / 'good'; good.write_text('ok')
    p = run('-P', good, tmp_path / 'absent one', tmp_path / 'absent二')
    out, err = decoded(p)
    assert p.returncode == 1 and not out
    assert 'absent one' in err and 'absent二' in err and 'No such file or directory' in err


def test_path_after_double_dash(tmp_path):
    f = tmp_path / '-strange'
    f.write_text('x')
    p = run('-b', '-P', '--', f.name, cwd=tmp_path)
    assert p.returncode == 0 and '-strange' in decoded(p)[0]


def test_json_tree_sizes_and_order(tmp_path):
    d = tmp_path / 'tree'; d.mkdir()
    (d / 'small').write_bytes(b'a')
    (d / 'large').write_bytes(b'x' * 5000)
    p = run('-j', '-P', d)
    assert p.returncode == 0
    obj = json.loads(p.stdout)
    assert obj['name'] == str(d) and isinstance(obj['size'], str)
    assert [x['name'] for x in obj['children']] == [str(d / 'large'), str(d / 'small')]
    assert all(x['children'] == [] for x in obj['children'])


def test_json_output_formats(tmp_path):
    f = tmp_path / 'f'; f.write_bytes(b'x')
    assert json.loads(run('-j', '-o', 'b', '-P', f).stdout)['size'] == '4096B'
    assert json.loads(run('-j', '-o=kb', '-P', f).stdout)['size'] == '4K'
    assert json.loads(run('-j', '-o', 'SI', '-P', f).stdout)['size'] == '4.1K'


def test_json_full_path_and_relative_name(tmp_path):
    (tmp_path / 'rel').mkdir()
    p = run('-j', '-P', 'rel', cwd=tmp_path)
    assert json.loads(p.stdout)['name'] == 'rel'
    p = run('-j', '-p', '-P', 'rel', cwd=tmp_path)
    assert json.loads(p.stdout)['name'] == 'rel'


def test_filecount_and_flat_only_file(tmp_path):
    d = tmp_path / 'd'; d.mkdir()
    (d / 'sub').mkdir(); (d / 'sub' / 'a').write_text('a'); (d / 'b').write_text('b')
    obj = json.loads(run('-j', '-f', '-P', d).stdout)
    assert obj['size'] == '2'
    file_obj = json.loads(run('-j', '-f', '-F', '-P', d).stdout)
    assert file_obj['size'] == '2' and len(file_obj['children']) == 2
    root_file = run('-f', '-b', '-P', d / 'b')
    assert '0' in decoded(root_file)[0]


def test_depth_zero_and_skip_total(tmp_path):
    d = tmp_path / 'd'; d.mkdir(); (d / 'f').write_text('x')
    obj = json.loads(run('-j', '-d', '0', '-P', d).stdout)
    assert obj['children'] == []
    p = run('-P', '--skip-total', '-b', d)
    assert '(total)' not in decoded(p)[0]


def test_filters_hidden_and_ignore_component(tmp_path):
    d = tmp_path / 'root'; d.mkdir()
    (d / '.secret').write_text('x'); (d / 'keep.txt').write_text('x')
    (d / 'data').mkdir(); (d / 'data' / 'x').write_text('x')
    (d / 'data_extra').mkdir(); (d / 'data_extra' / 'y').write_text('x')
    p = run('-j', '-i', '-X', 'data', '-P', d)
    names = json.dumps(json.loads(p.stdout), ensure_ascii=False)
    assert '.secret' not in names and 'data"' not in names and 'data_extra' in names
    p = run('-j', '-e', r'\.txt$', '-P', d)
    obj = json.loads(p.stdout)
    assert obj['size'] == '4.0K' and [n['name'] for n in obj['children']] == [str(d / 'keep.txt')]


def test_invalid_regex_fails_before_scan(tmp_path):
    p = run('-v', '[', '-P', tmp_path / 'missing')
    assert p.returncode == 1 and not p.stdout
    assert b'Ignoring bad value for regex' in p.stderr and b'regex parse error' in p.stderr


def test_min_size_strict_and_units(tmp_path):
    f = tmp_path / 'f'; f.write_bytes(b'x' * 1024)
    for threshold in ('1024', '1K', '1KiB'):
        obj = json.loads(run('-j', '-s', '-z', threshold, '-P', f).stdout)
        assert obj['name'] == str(f)
        assert obj['size'] == '0B'


def test_reverse_screen_reader_and_connectors(tmp_path):
    d = tmp_path / 'd'; d.mkdir(); (d / 'f').write_text('x')
    normal = decoded(run('-b', '-P', d))[0]
    reverse = decoded(run('-b', '-r', '-P', d))[0]
    reader = decoded(run('-R', '-P', d))[0]
    assert '┌──' in normal and '┌─┴' in normal
    assert '└─┬' in reverse
    assert not any(ch in reader for ch in '┌┐└┘├┤┬┴─│█')
    assert re.search(r'\bf\s+1\s+', reader)


def test_collapse_keeps_aggregate(tmp_path):
    d = tmp_path / 'd'; d.mkdir(); sub = d / 'sub'; sub.mkdir(); (sub / 'x').write_text('x')
    obj = json.loads(run('-j', '--collapse', 'sub', '-P', d).stdout)
    node = next(x for x in obj['children'] if x['name'] == str(sub))
    assert node['children'] == [] and node['size'] == '8.0K'


def test_file_types_json_groups(tmp_path):
    d = tmp_path / 'd'; d.mkdir()
    (d / 'a.txt').write_text('a'); (d / 'b.txt').write_text('b'); (d / 'c').write_text('c')
    obj = json.loads(run('-j', '-t', '-P', d).stdout)
    assert obj['name'] == '(total)'
    assert {x['name'] for x in obj['children']} == {'.txt', '(no extension)'}


def test_symlink_policy(tmp_path):
    target = tmp_path / 'target'; target.write_text('x')
    d = tmp_path / 'd'; d.mkdir(); (d / 'link').symlink_to(target)
    plain = json.loads(run('-j', '-P', d).stdout)
    link = plain['children'][0]
    assert link['size'] == '0B' and link['children'] == []
    followed = json.loads(run('-j', '-L', '-P', d).stdout)
    assert followed['children'][0]['size'] == '4.0K'


def test_files_from_and_files0_from(tmp_path):
    d = tmp_path / 'd'; d.mkdir(); a = d / 'a'; a.write_text('a')
    listing = tmp_path / 'list'; listing.write_text(str(a) + '\n')
    obj = json.loads(run('-j', '--files-from', listing, '-P').stdout)
    assert obj['name'] == '(total)' and obj['children'][0]['name'] == str(a)
    weird = d / 'line\nbreak'; weird.write_text('x')
    listing0 = tmp_path / 'list0'; listing0.write_bytes(os.fsencode(weird) + b'\0')
    obj = json.loads(run('-j', '--files0-from=' + str(listing0), '-P').stdout)
    assert obj['children'][0]['name'] == str(weird)


def test_empty_lists_and_empty_stdin(tmp_path):
    empty = tmp_path / 'empty-list'; empty.write_bytes(b'')
    p = run('-b', '--files-from', empty, '-P')
    assert p.returncode == 0 and '(total)' in decoded(p)[0]
    p = run('--files-from', '-', '-P', data=b'')
    assert p.returncode == 0 and b'No files provided' in p.stderr


def test_config_defaults_and_cli_override(tmp_path):
    d = tmp_path / 'd'; d.mkdir(); (d / 'a').write_text('x'); (d / 'b').write_text('x')
    cfg = tmp_path / 'config.toml'; cfg.write_text('number-of-lines = 1\nreverse = true\n')
    p = run('--config', cfg, '-b', '-P', d)
    assert p.returncode == 0
    text = decoded(p)[0]
    assert text.splitlines()[0].lstrip().startswith('d')


def test_filesystem_errors_and_progress_control(tmp_path):
    f = tmp_path / 'f'; f.write_text('x')
    p = run(f)
    assert b'\r \r' in p.stderr and b'\r \r' not in p.stdout
    p = run('-P', f)
    assert b'\r \r' not in p.stderr


def test_no_color_force_color_and_no_bars(tmp_path):
    f = tmp_path / 'f'; f.write_text('x')
    assert b'\x1b[' not in run('-c', f).stdout
    forced = run('-C', f)
    assert b'\x1b[31m' in forced.stdout and b'\x1b[0m' in forced.stdout
    no_bars = run('-b', '-P', f)
    assert b'%' not in no_bars.stdout and b'│' not in no_bars.stdout


def test_clustered_options_and_attached_values(tmp_path):
    f = tmp_path / 'f'; f.write_text('x')
    p = run('-pf', '-w', '+80', '-b', '-P', f)
    assert p.returncode == 0 and b'f' in p.stdout

