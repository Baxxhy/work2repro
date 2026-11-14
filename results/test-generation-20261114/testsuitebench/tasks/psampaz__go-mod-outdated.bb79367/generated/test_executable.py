import json
import os
import re
import subprocess
import time
from pathlib import Path

EXE = Path('/workspace/executable')


def run(data=b'', *args):
    return subprocess.run([str(EXE), *args], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, timeout=15)


def obj(**kw):
    return json.dumps(kw, ensure_ascii=False, separators=(',', ':')).encode()


def ascii_table(rows):
    headers = ['MODULE', 'VERSION', 'NEW VERSION', 'DIRECT', 'VALID TIMESTAMPS']
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    def border():
        return '+' + '+'.join('-' * (w + 2) for w in widths) + '+\n'
    def line(row, center=False):
        cells = []
        for i, (s, w) in enumerate(zip(row, widths)):
            pad = w - len(s)
            left = pad // 2 if center else 0
            right = pad - left
            cells.append(' ' + ' ' * left + s + ' ' * right + ' ')
        return '|' + '|'.join(cells) + '|\n'
    return border() + line(headers, True) + border() + ''.join(line(r) for r in rows) + border()


def markdown_table(rows):
    headers = ['MODULE', 'VERSION', 'NEW VERSION', 'DIRECT', 'VALID TIMESTAMPS']
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    def line(row, center=False):
        cells = []
        for s, w in zip(row, widths):
            p = w - len(s)
            l = p // 2 if center else 0
            cells.append(' ' + ' ' * l + s + ' ' * (p-l) + ' ')
        return '|' + '|'.join(cells) + '|\n'
    return line(headers, True) + '|' + '|'.join('-' * (w+2) for w in widths) + '|\n' + ''.join(line(r) for r in rows)


def test_empty_input_and_whitespace_are_silent():
    for data in (b'', b' \t\r\n\n'):
        p = run(data)
        assert p.returncode == 0 and p.stdout == b'' and p.stderr == b''


def test_empty_object_has_default_cells():
    p = run(b'{}')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.decode() == ascii_table([['', '', '', 'true', 'true']])


def test_json_stream_whitespace_order_and_no_trailing_newline_required():
    data = b'\r\n {"Path":"second"}\t{"Path":"first"}\n'
    p = run(data)
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.decode() == ascii_table([
        ['second', '', '', 'true', 'true'], ['first', '', '', 'true', 'true']])


def test_multiline_objects_unknown_fields_and_ignored_optional_fields():
    data = b'{\n"Path":"m","Versions":["v9"],"Dir":"/x","GoMod":"/x/go.mod", "GoVersion":"1.99", "Error":{"Err":"oops"}, "Extra":1\n}'
    p = run(data)
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.decode() == ascii_table([['m', '', '', 'true', 'true']])


def test_main_module_is_always_discarded():
    p = run(b'{"Path":"visible","Main":false} {"Path":"hidden","Main":true,"Update":{"Version":"v2"}}')
    assert p.stdout.decode() == ascii_table([['visible', '', '', 'true', 'true']])


def test_direct_filter_uses_top_level_indirect_and_missing_means_direct():
    data = b'{"Path":"missing"} {"Path":"direct","Indirect":false} {"Path":"indirect","Indirect":true}'
    p = run(data, '--direct')
    assert p.returncode == 0 and p.stdout.decode() == ascii_table([
        ['missing', '', '', 'true', 'true'], ['direct', '', '', 'true', 'true']])


def test_update_filter_requires_top_level_update_and_combines_with_direct():
    data = (b'{"Path":"direct-update","Update":{"Version":"n"}} '
            b'{"Path":"indirect-update","Indirect":true,"Update":{}} '
            b'{"Path":"replacement-only","Replace":{"Update":{"Version":"r"}}}')
    p = run(data, '-update', '-direct')
    assert p.returncode == 0 and p.stdout.decode() == ascii_table([
        ['direct-update', '', 'n', 'true', 'true']])


def test_replacement_projects_values_but_keeps_original_path():
    data = obj(Path='original', Version='top', Update={'Version':'top-new'},
               Replace={'Path':'fork', 'Version':'fork-v', 'Update':{'Version':'fork-new'}})
    p = run(data)
    assert p.stdout.decode() == ascii_table([['original', 'fork-v', 'fork-new', 'true', 'true']])


def test_replacement_missing_fields_do_not_fall_back():
    data = obj(Path='original', Version='top-v', Update={'Version':'top-n'}, Replace={})
    p = run(data)
    assert p.stdout.decode() == ascii_table([['original', '', '', 'true', 'true']])


def test_replacement_update_filter_and_indirect_filter_use_top_level():
    data = b'{"Path":"r","Indirect":true,"Replace":{"Update":{"Version":"v"}}}'
    assert run(data, '-update').stdout == b''
    assert run(data, '-direct').stdout == b''
    p = run(data)
    assert p.stdout.decode() == ascii_table([['r', '', 'v', 'false', 'true']])


def test_markdown_spelling_and_equals_style_option_forms():
    data = obj(Path='m', Version='v1', Update={'Version':'v2'})
    expected = markdown_table([['m','v1','v2','true','true']]).encode()
    for args in (('--style','markdown'), ('-style','markdown'), ('--style=markdown',), ('-style=markdown',)):
        p = run(data, *args)
        assert p.returncode == 0 and p.stdout == expected and p.stderr == b''


def test_style_fallback_and_option_order():
    data = obj(Path='m')
    expected = ascii_table([['m','','','true','true']]).encode()
    for args in ((), ('--style','default'), ('--style',''), ('--style','Markdown'),
                 ('--ci','--style=other','--direct')):
        p = run(data, *args)
        assert p.stdout == expected


def test_double_dash_ends_option_parsing():
    p = run(b'{"Path":"m"}', '--', '--help', '--bogus')
    assert p.returncode == 0 and p.stdout.decode() == ascii_table([['m','','','true','true']])
    assert p.stderr == b''


def test_help_exact_text_and_argv0():
    p = run(b'invalid', '--direct', '--help')
    expected = (f'Usage of {EXE}:\n'
                '  -ci\n    \tNon-zero exit code when at least one outdated dependency was found\n'
                '  -direct\n    \tList only direct modules\n'
                '  -style string\n    \tOutput style, pass \'markdown\' for a Markdown table (default "default")\n'
                '  -update\n    \tList only modules with updates\n').encode()
    assert p.returncode == 0 and p.stdout == b'' and p.stderr == expected


def test_unknown_option_diagnostic_and_usage():
    p = run(b'', '--nonexistent')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr.startswith(b'flag provided but not defined: -nonexistent\nUsage of ')
    assert p.stderr.endswith(b'  -update\n    \tList only modules with updates\n')


def test_missing_style_value_diagnostic():
    p = run(b'', '--style')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr.startswith(b'flag needs an argument: -style\nUsage of ')


def test_invalid_boolean_values_diagnostic():
    for flag in ('ci', 'direct', 'update'):
        p = run(b'', f'-{flag}=perhaps')
        assert p.returncode == 2 and p.stdout == b''
        assert f'invalid boolean value "perhaps" for -{flag}'.encode() in p.stderr
        assert b'Usage of ' in p.stderr


def test_unknown_before_help_is_error():
    p = run(b'', '--bogus', '--help')
    assert p.returncode == 2 and p.stdout == b''
    assert p.stderr.startswith(b'flag provided but not defined: -bogus\n')


def test_invalid_json_reports_timestamped_decoder_error_without_table():
    cases = [
        (b'{"Path":"x"', b'unexpected EOF'),
        (b'not json at all', b"invalid character 'o' in literal null (expecting 'u')"),
        (b'i', b"invalid character 'i' looking for beginning of value"),
        (b'{"Path":"x",}', b"invalid character '}' looking for beginning of object key string"),
        (b'{"Path":"a\nb"}', b"invalid character '\\n' in string literal"),
        (b'[]', b'json: cannot unmarshal array into Go value of type mod.Module'),
        (b'{"Path":{}}', b'json: cannot unmarshal object into Go struct field Module.Path of type string'),
        (b'{"Main":"x"}', b'json: cannot unmarshal string into Go struct field Module.Main of type bool'),
        (b'{"Version":1}', b'json: cannot unmarshal number into Go struct field Module.Version of type string'),
        (b'{"Time":"not-a-date"}', b'parsing time "not-a-date"'),
    ]
    for data, fragment in cases:
        before = time.time()
        p = run(data)
        after = time.time()
        assert p.returncode == 0 and p.stdout == b''
        assert fragment in p.stderr
        m = re.match(rb'^(\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}) (.*)\n$', p.stderr)
        assert m, p.stderr
        assert before - 2 <= time.mktime(time.strptime(m.group(1).decode(), '%Y/%m/%d %H:%M:%S')) <= after + 2
        if data == b'{"Path":"x"':
            assert m.group(2) == b'unexpected EOF'


def test_first_json_error_stops_stream_and_no_later_rows():
    p = run(b'{"Path":"first"} {"Path":1} {"Path":"later"}')
    assert p.stdout == b'' and b'cannot unmarshal number' in p.stderr


def test_known_field_types_are_strict_and_nested_modules_validate():
    invalid = [b'{"Versions":"v1"}', b'{"Replace":[]}', b'{"Update":{"Path":false}}',
               b'{"Indirect":0}', b'{"Error":"oops"}', b'{"Time":"2024-02-30T00:00:00Z"}',
               b'{"Time":"2024-01-01T25:00:00Z"}', b'{"Path":"x",}']
    for data in invalid:
        p = run(data)
        assert p.stdout == b'' and p.stderr.endswith(b'\n')


def test_non_json_values_after_object_are_errors_but_whitespace_is_allowed():
    p = run(b'{"Path":"x"}\ntrue')
    assert p.stdout == b'' and p.stderr.endswith(b'\n')


def test_timestamp_order_uses_absolute_instants_and_strict_comparison():
    data = (b'{"Path":"later","Time":"2024-01-01T00:00:01Z","Update":{"Time":"2024-01-01T00:00:00Z"}} '
            b'{"Path":"equal","Time":"2024-01-01T01:00:00+01:00","Update":{"Time":"2024-01-01T00:00:00Z"}} '
            b'{"Path":"earlier","Time":"2023-12-31T23:59:59Z","Update":{"Time":"2024-01-01T00:00:00Z"}}')
    p = run(data)
    assert p.stdout.decode() == ascii_table([
        ['later','','','true','false'], ['equal','','','true','true'], ['earlier','','','true','true']])


def test_timestamp_missing_update_and_replacement_comparisons():
    data = (b'{"Path":"no-update","Time":"2024-01-01T00:00:00Z"} '
            b'{"Path":"replacement","Time":"2099-01-01T00:00:00Z","Update":{"Time":"2000-01-01T00:00:00Z"},"Replace":{"Time":"2000-01-01T00:00:00Z","Update":{"Time":"2099-01-01T00:00:00Z"}}}')
    p = run(data)
    assert p.stdout.decode() == ascii_table([
        ['no-update','','','true','true'], ['replacement','','','true','true']])


def test_unusual_offset_components_and_fractional_seconds_are_accepted():
    data = (b'{"Path":"offset","Time":"1970-01-01T00:00:00+99:99","Update":{"Time":"1970-01-01T00:00:00Z"}} '
            b'{"Path":"fraction","Time":"1970-01-01T00:00:00.123Z","Update":{"Time":"1970-01-01T00:00:00.123Z"}}')
    p = run(data)
    assert p.stdout.decode() == ascii_table([
        ['offset','','','true','false'], ['fraction','','','true','true']])


def test_ci_status_is_based_on_retained_effective_updates():
    p = run(b'{"Path":"m","Update":{}}', '--ci')
    assert p.returncode == 1 and p.stderr == b'' and b'| m ' in p.stdout
    assert run(b'{"Path":"m"}', '--ci').returncode == 0
    assert run(b'{"Path":"m","Indirect":true,"Update":{}}', '--ci', '--direct').returncode == 0
    assert run(b'{"Path":"m","Main":true,"Update":{}}', '--ci').returncode == 0
    assert run(b'{"Path":"m","Replace":{"Update":{}}}', '--ci').returncode == 1
    assert run(b'{"Path":"m","Update":{},"Replace":{}}', '--ci').returncode == 0


def test_without_ci_updates_do_not_change_success_status():
    p = run(b'{"Path":"m","Update":{}}')
    assert p.returncode == 0 and p.stderr == b''


def test_preserves_opaque_versions_unicode_and_cell_whitespace():
    path = '包🙂:α@repo'
    version = ' v01+incompatible β '
    new = 'v2-rc.1+meta'
    data = json.dumps({'Path':path, 'Version':version, 'Update':{'Version':new}}, ensure_ascii=False).encode()
    p = run(data, '--style=markdown')
    assert p.returncode == 0
    assert path.encode() in p.stdout and version.encode() in p.stdout and new.encode() in p.stdout
    assert p.stdout.decode().count('\n') == 3


def test_filtering_happens_before_column_width_calculation():
    data = b'{"Path":"a-very-very-long-omitted-path","Indirect":true} {"Path":"x"}'
    p = run(data, '--direct')
    assert p.stdout.decode() == ascii_table([['x','','','true','true']])


def test_large_stream_and_long_fields_have_no_truncation_or_repeated_header():
    count = 1000
    long_path = 'p' * 600
    long_version = 'v' * 140
    data = b' '.join(obj(Path=(long_path if i == 501 else f'm{i}'), Version=long_version) for i in range(count))
    p = run(data)
    out = p.stdout.decode()
    assert p.returncode == 0 and out.count('MODULE') == 1
    assert out.count('| m') >= 999 and long_path in out and long_version in out
    assert out.count('\n') == count + 4


def test_markdown_large_width_unicode_alignment_is_preserved():
    data = json.dumps({'Path':'界🙂e\u0301'}, ensure_ascii=False).encode()
    p = run(data, '--style', 'markdown')
    out = p.stdout.decode()
    assert '界🙂e\u0301' in out
    assert out.startswith('|') and out.count('\n') == 3
