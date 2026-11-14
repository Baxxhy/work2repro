import os
import subprocess
from pathlib import Path

import pytest
from PIL import Image

EXE = Path('/workspace/executable')
USAGE_MODE = '<--quality <QUALITY>|--lossless|--max-size <MAX_SIZE>>'
USAGE_DEST = '<--output <OUTPUT>|--same-folder-as-input>'


def invoke(args, cwd, timeout=20):
    return subprocess.run([str(EXE), *map(str, args)], cwd=cwd, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=timeout)


def image(path, fmt='PNG', size=(80, 60), color=(210, 30, 70)):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new('RGB', size, color)
    im.save(path, format=fmt)
    return path


def decoded(path):
    with Image.open(path) as im:
        im.load()
        return im.format, im.size


@pytest.fixture
def root(tmp_path):
    return tmp_path


@pytest.mark.parametrize('flag', ['--version', '-V'], ids=['long-version', 'short-version'])
def test_version_is_exact_and_standalone(root, flag):
    p = invoke([flag], root)
    assert p.returncode == 0 and p.stdout == b'caesiumclt 1.3.0\n' and p.stderr == b''


def test_help_exact_and_short_help_summary(root):
    p = invoke(['--help'], root)
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.startswith(b'A fast and efficient lossy and/or lossless image compression tool\n\nUsage: executable')
    assert b'--min-savings <MIN_SAVINGS>' in p.stdout and b'--threads <THREADS>' in p.stdout
    short = invoke(['-h'], root)
    assert short.returncode == 0 and short.stderr == b''
    for term in [b'A fast and efficient', b'Usage:', b'executable', b'[FILES]...', b'--quality', b'--lossless', b'--output']:
        assert term in short.stdout


def test_help_short_circuits_later_validation_but_not_prior_parse_error(root):
    p = invoke(['--quality', '5', '--lossless', '--help'], root)
    assert p.returncode == 0 and b'Usage:' in p.stdout and p.stderr == b''
    p = invoke(['--help', '--nonexistent'], root)
    assert p.returncode == 0 and p.stderr == b''
    p = invoke(['--nonexistent', '--quality', '5', '--lossless', '--help'], root)
    assert p.returncode == 2 and p.stdout == b''
    assert b"unexpected argument '--nonexistent' found" in p.stderr


def test_version_and_help_preempt_required_args(root):
    for flag, expected in [('--version', b'caesiumclt 1.3.0\n'), ('--help', b'A fast')]:
        p = invoke([flag], root)
        assert p.returncode == 0 and p.stdout.startswith(expected) and p.stderr == b''


def test_missing_required_groups_are_named(root):
    p = invoke([], root)
    assert p.returncode == 2 and p.stdout == b''
    assert b'required arguments were not provided' in p.stderr
    assert USAGE_MODE.encode() in p.stderr and USAGE_DEST.encode() in p.stderr and b'Usage:' in p.stderr


@pytest.mark.parametrize('args,first,second', [
    (['--quality', '5', '--lossless', '-o', 'out'], b"'--quality <QUALITY>'", b"'--lossless'"),
    (['--quality', '5', '--max-size', '1KB', '-o', 'out'], b"'--quality <QUALITY>'", b"'--max-size <MAX_SIZE>'"),
    (['--lossless', '--max-size', '1KB', '-o', 'out'], b"'--lossless'", b"'--max-size <MAX_SIZE>'"),
    (['--quality', '5', '-o', 'out', '--same-folder-as-input'], b"'--output <OUTPUT>'", b"'--same-folder-as-input'"),
], ids=['quality-lossless', 'quality-max-size', 'lossless-max-size', 'destinations'])
def test_exclusive_modes_and_destinations(root, args, first, second):
    p = invoke(args, root)
    assert p.returncode == 2 and p.stdout == b''
    assert b'cannot be used with' in p.stderr and first in p.stderr and second in p.stderr


@pytest.mark.parametrize('option', ['--max-size', '-o', '--format', '--threads', '--suffix', '--verbose',
                                    '--png-opt-level', '--jpeg-chroma-subsampling', '--width', '--height',
                                    '--long-edge', '--short-edge', '-q', '-O'], ids=[
    'max-size', 'output', 'format', 'threads', 'suffix', 'verbose', 'png-level', 'chroma', 'width',
    'height', 'long-edge', 'short-edge', 'quality', 'overwrite'])
def test_missing_values_are_parser_errors(root, option):
    p = invoke([option], root)
    assert p.returncode == 2 and p.stdout == b''
    assert b'a value is required for' in p.stderr and b'but none was supplied' in p.stderr


def test_unknown_options_and_double_dash_paths(root):
    p = invoke(['--quality', '60', '-o', 'out', '--nonexistent'], root)
    assert p.returncode == 2 and b"unexpected argument '--nonexistent' found" in p.stderr
    assert b"tip: to pass '--nonexistent' as a value, use '-- --nonexistent'" in p.stderr
    p = invoke(['--quality', '60', '-o', 'out', '--', '--help'], root)
    assert p.returncode == 255 and p.stdout == b'' and p.stderr.strip() == b'Unable to compute the base path for the files.'


@pytest.mark.parametrize('args,needle', [
    (['--threads=-1'], b'-1 is not in 0..=4294967295'),
    (['--threads', '-1'], b"tip: to pass '-1' as a value, use '-- -1'"),
], ids=['negative-equals-invalid-value', 'negative-token-option'])
def test_threads_negative_forms(root, args, needle):
    p = invoke(['--quality', '20', '-o', 'out', *args], root)
    assert p.returncode == 2 and needle in p.stderr


@pytest.mark.parametrize('value,needle', [('150', b'Quality must be between 0 and 100'), ('abc', b"'abc' is not a valid number"),
                                          ('80.5', b"'80.5' is not a valid number")], ids=['high', 'text', 'fraction'])
def test_quality_range_and_integer(root, value, needle):
    p = invoke(['--quality', value, '-o', 'out'], root)
    assert p.returncode == 2 and b'--quality <QUALITY>' in p.stderr and needle in p.stderr


@pytest.mark.parametrize('args,needle', [
    (['--png-opt-level', '10'], b'PNG optimization level must be between 0 and 6'),
    (['--verbose', '10'], b'Verbosity must be between 0 and 3'),
    (['--verbose', 'no'], b'is not a valid number'),
    (['--format', 'bmp'], b'jpeg, png, gif, webp, tiff, original'),
    (['--overwrite', 'sometimes'], b'all, never, bigger'),
    (['--jpeg-chroma-subsampling', '4:2:1'], b"tip: a similar value exists: '4:1:1'"),
], ids=['png-range', 'verbose-range', 'verbose-type', 'format-values', 'overwrite-values', 'chroma-suggestion'])
def test_encoder_enum_and_range_validation(root, args, needle):
    p = invoke(['--quality', '50', '-o', 'out', *args], root)
    assert p.returncode == 2 and needle in p.stderr


def test_max_size_and_min_savings_invalid_values(root):
    p = invoke(['--max-size', 'abc', '-o', 'out'], root)
    assert p.returncode == 2 and b'Invalid size format' in p.stderr
    p = invoke(['--quality', '50', '--min-savings', '150%', '-o', 'out'], root)
    assert p.returncode == 2 and b'Percentage must be between 0 and 100, got 150' in p.stderr
    p = invoke(['--quality', '50', '--min-savings', 'xyz', '-o', 'out'], root)
    assert p.returncode == 2 and b"Invalid size format: 'xyz'" in p.stderr


@pytest.mark.parametrize('path_kind', ['missing', 'empty-dir', 'unsupported', 'empty-file'], ids=['missing', 'empty-dir', 'unsupported', 'empty-file'])
def test_fatal_discovery_cases(root, path_kind):
    target = root / 'input'
    if path_kind == 'empty-dir': target.mkdir()
    elif path_kind == 'unsupported': target.write_text('not image')
    elif path_kind == 'empty-file': target.touch()
    p = invoke(['--quality', '50', '-o', 'out', target], root)
    assert p.returncode == 255 and p.stdout == b''
    assert p.stderr.strip() == b'Unable to compute the base path for the files.'


def test_no_paths_differs_from_discovery_failure(root):
    p = invoke(['--quality', '50', '-o', 'out'], root)
    assert p.returncode == 0 and p.stderr.strip() == b'No files to compress'


def test_extensionless_jpeg_unicode_path_and_case_preservation(root):
    source = image(root / 'naïve photo', 'JPEG')
    p = invoke(['--quality', '80', '-o', root / 'dest', source], root)
    assert p.returncode == 0
    out = root / 'dest' / source.name
    assert out.exists() and decoded(out)[0] == 'JPEG'


def test_nonrecursive_recursive_and_keep_structure(root):
    src = root / 'tree'
    image(src / 'top.PNG')
    image(src / 'sub' / 'nested.jpg', 'JPEG')
    image(src / 'sub' / 'ignored.tiff', 'TIFF')
    p = invoke(['--quality', '70', '-o', root / 'flat', src], root)
    assert p.returncode == 0 and (root / 'flat' / 'top.PNG').exists()
    assert not (root / 'flat' / 'nested.jpg').exists()
    p = invoke(['--quality', '70', '-R', '-S', '-o', root / 'structured', src], root)
    assert p.returncode == 0
    assert (root / 'structured' / 'top.PNG').exists()
    assert (root / 'structured' / 'sub' / 'nested.jpg').exists()
    assert not list((root / 'structured').rglob('*.tiff'))


def test_flat_multi_input_mixed_invalid_and_position_interspersed_options(root):
    a = image(root / 'one' / 'a.png')
    b = image(root / 'two' / 'b.webp', 'WEBP')
    p = invoke([a, '--quality=60', root / 'missing', '-o', root / 'new' / 'dest', b], root)
    assert p.returncode == 0
    assert (root / 'new' / 'dest' / 'a.png').exists() and (root / 'new' / 'dest' / 'b.webp').exists()
    assert b'Compressed 2 files (2 success, 0 skipped, 0 errors)' in p.stdout


def test_standalone_double_dash_allows_dash_path(root):
    source = image(root / '-picture.png')
    p = invoke(['--quality', '50', '-o', root / 'out', '--', source], root)
    assert p.returncode == 0 and (root / 'out' / '-picture.png').exists()


def test_boolean_short_options_can_be_combined_and_keep_structure_without_recursive(root):
    src = image(root / 'nested' / 'source.png')
    p = invoke(['-q', '60', '-Rd', '-o', root / 'dry', root / 'nested'], root)
    assert p.returncode == 0 and not (root / 'dry').exists()
    assert b'Compressed 1 files (1 success, 0 skipped, 0 errors)' in p.stdout
    p = invoke(['--quality', '60', '--keep-structure', '-o', root / 'flat', root / 'nested'], root)
    assert p.returncode == 0 and (root / 'flat' / 'source.png').exists()


@pytest.mark.parametrize('threads', ['0', '2', '4', '999'], ids=['auto-explicit', 'two', 'four', 'capped-large'])
def test_accepted_thread_counts_complete(root, threads):
    src = image(root / f'threads-{threads}.png')
    p = invoke(['--quality', '50', '--threads', threads, '-o', root / f'out-{threads}', src], root)
    assert p.returncode == 0 and (root / f'out-{threads}' / src.name).exists()


def test_output_creation_suffix_and_same_folder(root):
    source = image(root / 'src' / 'photo.JPG', 'JPEG')
    p = invoke(['--quality', '60', '-o', root / 'missing' / 'deep', '--suffix', '_compressed', source], root)
    assert p.returncode == 0 and (root / 'missing' / 'deep' / 'photo_compressed.JPG').exists()
    p = invoke(['--quality', '60', '--same-folder-as-input', '--suffix', '_new', source], root)
    assert p.returncode == 0 and (root / 'src' / 'photo_new.JPG').exists()
    assert source.exists()


@pytest.mark.parametrize('fmt,extension,pilfmt', [('jpeg', '.jpg', 'JPEG'), ('png', '.png', 'PNG'), ('webp', '.webp', 'WEBP'),
                                                    ('gif', '.gif', 'GIF'), ('tiff', '.tiff', 'TIFF')],
                         ids=['jpeg', 'png', 'webp', 'gif', 'tiff'])
def test_conversion_has_canonical_extension_and_valid_content(root, fmt, extension, pilfmt):
    src = image(root / 'source.png')
    p = invoke(['--lossless', '--format', fmt, '-o', root / 'out', src], root)
    assert p.returncode == 0
    outputs = list((root / 'out').iterdir())
    assert len(outputs) == 1 and outputs[0].suffix == extension
    assert decoded(outputs[0]) == (pilfmt, (80, 60))


def test_batch_format_applies_to_all_and_resize_options(root):
    a, b = image(root / 'a.jpg', 'JPEG'), image(root / 'b.png')
    p = invoke(['--quality', '70', '--format', 'webp', '--width', '40', '-o', root / 'out', a, b], root)
    assert p.returncode == 0
    assert decoded(root / 'out' / 'a.webp') == ('WEBP', (40, 30))
    assert decoded(root / 'out' / 'b.webp') == ('WEBP', (40, 30))


@pytest.mark.parametrize('args,expected', [(['--width', '30'], (30, 23)), (['--height', '30'], (40, 30)),
                                           (['--width', '30', '--height', '10'], (30, 10)),
                                           (['--long-edge', '40'], (40, 30)), (['--short-edge', '20'], (27, 20))],
                         ids=['width', 'height', 'both', 'long-edge', 'short-edge'])
def test_resize_dimension_modes(root, args, expected):
    src = image(root / 'source.png')
    p = invoke(['--quality', '70', *args, '-o', root / 'out', src], root)
    assert p.returncode == 0 and decoded(root / 'out' / 'source.png')[1] == expected


def test_resize_conflicts_and_bad_dimensions(root):
    p = invoke(['--quality', '50', '--width', '20', '--long-edge', '30', '-o', 'out'], root)
    assert p.returncode == 2 and b"'--width <WIDTH>' cannot be used with '--long-edge <LONG_EDGE>'" in p.stderr
    p = invoke(['--quality', '50', '--width', 'abc', '-o', 'out'], root)
    assert p.returncode == 2 and b'invalid digit found in string' in p.stderr
    p = invoke(['--quality', '50', '--long-edge', '30', '--short-edge', '10', '-o', 'out'], root)
    assert p.returncode == 2 and b'cannot be used with' in p.stderr


def test_no_upscale_cancels_entire_resize(root):
    src = image(root / 'small.png', size=(20, 10))
    p = invoke(['--quality', '70', '--width', '10', '--height', '30', '--no-upscale', '-o', root / 'out', src], root)
    assert p.returncode == 0 and decoded(root / 'out' / 'small.png')[1] == (20, 10)
    p = invoke(['--quality', '70', '--width', '40', '--no-upscale', '-o', root / 'out2', src], root)
    assert p.returncode == 0 and decoded(root / 'out2' / 'small.png')[1] == (40, 20)


def test_quality_encodes_valid_results_and_jpeg_quality_size_order(root):
    src = image(root / 'photo.jpg', 'JPEG', (320, 240))
    sizes = []
    for q in (0, 50, 100):
        out = root / f'q{q}'
        p = invoke(['--quality', str(q), '-o', out, src], root)
        assert p.returncode == 0 and decoded(out / 'photo.jpg') == ('JPEG', (320, 240))
        sizes.append((out / 'photo.jpg').stat().st_size)
    assert sizes[0] <= sizes[1] <= sizes[2]
    assert sizes[0] < src.stat().st_size


def test_lossless_conversion_and_png_optimization_levels(root):
    src = image(root / 'source.png', size=(55, 40))
    p = invoke(['--lossless', '--format', 'webp', '-o', root / 'webp', src], root)
    assert p.returncode == 0 and decoded(root / 'webp' / 'source.webp') == ('WEBP', (55, 40))
    sizes = []
    for level in (0, 6):
        out = root / f'level{level}'
        p = invoke(['--quality', '75', '--format', 'png', '--png-opt-level', str(level), '--zopfli', '-o', out, src], root)
        assert p.returncode == 0 and decoded(out / 'source.png') == ('PNG', (55, 40))
        sizes.append((out / 'source.png').stat().st_size)
    assert sizes[1] <= sizes[0]


def test_max_size_achievable_and_tiny_target_fallback(root):
    src = image(root / 'photo.jpg', 'JPEG', (220, 160))
    for size in ('50KB', '0.5MB', '1KiB'):
        out = root / ('out' + size)
        p = invoke(['--max-size', size, '-o', out, src], root)
        assert p.returncode == 0 and (out / 'photo.jpg').stat().st_size > 0
    tiny = root / 'tiny'
    p = invoke(['--max-size', '100', '-o', tiny, src], root)
    assert p.returncode == 0 and decoded(tiny / 'photo.jpg')[0] == 'JPEG'


def test_dry_run_does_not_create_or_change_outputs_and_reports_success(root):
    src = image(root / 'source.png')
    before = src.read_bytes()
    p = invoke(['--quality', '60', '--dry-run', '--min-savings', '100%', '-o', root / 'absent' / 'out', src], root)
    assert p.returncode == 0 and b'Compressed 1 files (1 success, 0 skipped, 0 errors)' in p.stdout
    assert not (root / 'absent').exists() and src.read_bytes() == before


def test_quiet_and_verbose_zero_suppress_output_but_work(root):
    for flag, value in [('--quiet', None), ('--verbose', '0')]:
        src = image(root / f'{flag}.png')
        args = ['--quality', '50', flag] + ([value] if value else []) + ['-o', root / ('out' + flag), src]
        p = invoke(args, root)
        assert p.returncode == 0 and p.stdout == b'' and p.stderr == b''
        assert (root / ('out' + flag) / src.name).exists()


def test_quiet_verbose_conflict(root):
    p = invoke(['--quality', '50', '--verbose', '2', '--quiet', '-o', 'out'], root)
    assert p.returncode == 2 and b"'--verbose <VERBOSE>' cannot be used with '--quiet'" in p.stderr


def test_summary_counts_and_sizes_are_on_stdout(root):
    src = image(root / 'source.png')
    p = invoke(['--quality', '50', '-o', root / 'out', src], root)
    assert p.returncode == 0 and p.stderr == b''
    assert b'Compressed 1 files (1 success, 0 skipped, 0 errors)' in p.stdout
    assert b'->' in p.stdout and b'%' in p.stdout


def test_min_savings_equal_threshold_skips_and_creates_directory(root):
    src = image(root / 'source.png')
    first = invoke(['--quality', '50', '-o', root / 'first', src], root)
    assert first.returncode == 0
    candidate_size = (root / 'first' / 'source.png').stat().st_size
    # Use a fresh source so candidate encoding is byte-for-byte deterministic.
    source2 = image(root / 'source2.png')
    p = invoke(['--quality', '50', '--min-savings', '100%', '-o', root / 'skip', source2], root)
    assert p.returncode == 0 and (root / 'skip').is_dir() and not list((root / 'skip').iterdir())
    assert b'(0 success, 1 skipped, 0 errors)' in p.stdout


def test_keep_dates_and_default_new_timestamp(root):
    src = image(root / 'source.png')
    old = 1_600_000_000
    os.utime(src, (old, old))
    p = invoke(['--quality', '60', '--keep-dates', '--suffix', '_kept', '-o', root / 'out', src], root)
    assert p.returncode == 0
    out = root / 'out' / 'source_kept.png'
    assert abs(out.stat().st_mtime - old) <= .01 and abs(out.stat().st_atime - old) <= .01
    p = invoke(['--quality', '60', '-o', root / 'out2', src], root)
    assert p.returncode == 0 and (root / 'out2' / 'source.png').stat().st_mtime > old


def test_overwrite_never_and_bigger_policies(root):
    src = image(root / 'source.jpg', 'JPEG')
    out = root / 'out'; out.mkdir()
    target = out / 'source.jpg'; target.write_bytes(b'KEEP')
    old = 1_600_000_000; os.utime(target, (old, old))
    p = invoke(['--quality', '70', '--overwrite', 'never', '-o', out, src], root)
    assert p.returncode == 0 and target.read_bytes() == b'KEEP' and target.stat().st_mtime == old
    target.write_bytes(b'x' * 5000)
    p = invoke(['--quality', '70', '--overwrite', 'bigger', '-o', out, src], root)
    assert p.returncode == 0 and decoded(target)[0] == 'JPEG'
    small = target.read_bytes()
    p = invoke(['--quality', '70', '--overwrite', 'bigger', '-o', out, src], root)
    assert p.returncode == 0 and target.read_bytes() == small


def test_same_folder_without_suffix_replaces_input(root):
    src = image(root / 'inplace.png')
    original = src.read_bytes()
    p = invoke(['--quality', '40', '--same-folder-as-input', src], root)
    assert p.returncode == 0 and src.exists()
    assert decoded(src)[0] == 'PNG'


def test_recognized_truncated_jpeg_is_recovered(root):
    good = image(root / 'good.jpg', 'JPEG', (120, 80))
    truncated = root / 'truncated.jpg'
    data = good.read_bytes(); truncated.write_bytes(data[:max(200, len(data) // 8)])
    other = image(root / 'other.png')
    p = invoke(['--quality', '60', '--verbose', '2', '-o', root / 'out', good, truncated, other], root)
    assert p.returncode == 0 and b'Error compressing file:' not in p.stdout
    assert b'Compressed 3 files (3 success, 0 skipped, 0 errors)' in p.stdout
    assert decoded(root / 'out' / 'truncated.jpg')[0] == 'JPEG'
