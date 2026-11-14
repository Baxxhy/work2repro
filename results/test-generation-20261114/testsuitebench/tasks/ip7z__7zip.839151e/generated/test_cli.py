import pytest
import hashlib
import os
import pathlib
import re
import subprocess
import tempfile
import zlib

EXE = '/workspace/executable'


def run(args, cwd, data=None, timeout=15):
    return subprocess.run([EXE, *map(str, args)], cwd=cwd, input=data,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=timeout)


def out(p):
    return p.stdout.decode('utf-8', 'replace')


def err(p):
    return p.stderr.decode('utf-8', 'replace')


def test_help_and_usage():
    p = run(['--help'], '/workspace/eval')
    assert p.returncode == 0
    s = out(p)
    assert 'Usage: 7za <command>' in s
    for token in ['a : Add files to archive', 'e : Extract files from archive',
                  'x : eXtract files with full paths', '-mx[N]', '-p{Password}',
                  '-o{Directory}', '-r[-|0]', '-t{Type}', '-v{Size}', '-si', '-so']:
        assert token in s
    for command in ['b :', 'd :', 'h :', 'i :', 'l :', 'rn :', 't :', 'u :']:
        assert command in s
    for switch in ['--', '-ai', '-ax', '-ao', '-an', '-bb', '-bd', '-bs', '-bt', '-mmt',
                   '-slt', '-snh', '-snl', '-sni', '-sns', '-spd', '-spe', '-spf', '-ssc', '-sse', '-ssp', '-ssw', '-stl', '-stm', '-stx', '-y']:
        assert switch in s


def test_no_arguments_prints_usage():
    p = run([], '/workspace/eval')
    assert p.returncode == 0 and 'Usage:' in out(p)


def test_information_report():
    p = run(['i'], '/workspace/eval')
    assert p.returncode == 0 and not p.stderr
    s = out(p)
    for token in ['Formats:', 'Codecs:', 'Hashers:', '7 z BC AF', 'P K 03 04', 'offset=257',
                  '1F 8B 08', 'BCJ2', '40108', 'SHA256']:
        assert token in s


def test_unknown_command_and_switch_are_cli_errors():
    with tempfile.TemporaryDirectory() as d:
        p = run(['wat'], d)
        assert p.returncode == 7 and 'Unsupported command:' in err(p) and 'wat' in err(p)
        p = run(['a', '-definitely-unknown', 'x.7z'], d)
        assert p.returncode == 7 and 'Unknown switch:' in err(p)


@pytest.mark.parametrize('switch, phrase', [
    ('-y-', 'Too long switch:'), ('-rBAD', 'Too long switch:'),
    ('-ix', 'Too short switch:'), ('-aox', 'Incorrect switch postfix'),
    ('-stmXYZ', 'Unsupported switch postfix -stm'), ('-t', 'Too short switch:'),
])
def test_invalid_switch_postfixes(switch, phrase):
    import pytest
    with tempfile.TemporaryDirectory() as d:
        p = run(['a', switch, 'x.7z'], d)
        assert p.returncode == 7 and phrase in err(p)


def test_duplicate_singleton_switches():
    with tempfile.TemporaryDirectory() as d:
        p = run(['a', '-t7z', '-tzip', 'x.7z'], d)
        assert p.returncode == 7 and 'Multiple instances for switch:' in err(p) and '-tzip' in err(p)
        p = run(['x', '-oA', '-oB', 'missing.7z'], d)
        assert p.returncode == 7 and 'Multiple instances for switch:' in err(p)


def test_missing_archive_diagnostic():
    with tempfile.TemporaryDirectory() as d:
        p = run(['l', 'absent.7z'], d)
        assert p.returncode == 2
        assert all(x in err(p) for x in ['errno=2', 'absent.7z', 'System ERROR:'])


def test_archive_create_list_test_and_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root/'a.txt').write_bytes(b'alpha\x00omega')
        (root/'empty').write_bytes(b'')
        p = run(['a', 'sample.7z', 'a.txt', 'empty'], d)
        assert p.returncode == 0 and (root/'sample.7z').stat().st_size > 0
        assert 'Everything is Ok' in out(p) and 'Files read from disk: 2' in out(p)
        l = run(['l', '-slt', 'sample.7z'], d)
        assert l.returncode == 0 and 'Type = 7z' in out(l) and 'a.txt' in out(l) and 'empty' in out(l)
        t = run(['t', 'sample.7z'], d)
        assert t.returncode == 0 and 'Everything is Ok' in out(t)
        x = run(['x', 'sample.7z', '-oextract'], d)
        assert x.returncode == 0
        assert (root/'extract'/'a.txt').read_bytes() == b'alpha\x00omega'
        assert (root/'extract'/'empty').read_bytes() == b''


def test_7z_stdout_exact_payload_and_selection():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root/'sub').mkdir()
        (root/'sub'/'one.txt').write_bytes(b'one\x00')
        (root/'two.txt').write_bytes(b'two')
        assert run(['a', 'a.7z', 'sub', 'two.txt'], d).returncode == 0
        p = run(['x', '-so', 'a.7z', 'sub/one.txt'], d)
        assert p.returncode == 0 and p.stdout == b'one\x00'
        q = run(['x', '-so', 'a.7z', 'not-there'], d)
        assert q.returncode == 0 and q.stdout == b''


def test_archive_type_signature_zip_and_tar():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root/'data.txt').write_text('content')
        for typ, name, sig in [('zip','z.zip',b'PK\x03\x04'), ('tar','t.tar',b'data.txt')]:
            p = run(['a', '-t'+typ, name, 'data.txt'], d)
            assert p.returncode == 0
            raw = (root/name).read_bytes()
            if typ == 'zip': assert raw.startswith(sig)
            else: assert raw.startswith(sig) and len(raw) % 512 == 0
            q = run(['l', name], d)
            assert q.returncode == 0 and 'data.txt' in out(q)
            x = run(['x', name, '-o'+name+'.out'], d)
            assert x.returncode == 0
            assert (root/(name+'.out')/'data.txt').read_text() == 'content'


def test_wrong_extension_detected_by_signature():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root/'f').write_text('hello')
        assert run(['a','real.7z','f'],d).returncode == 0
        (root/'misleading.zip').write_bytes((root/'real.7z').read_bytes())
        p = run(['l','misleading.zip'],d)
        assert p.returncode == 0 and 'Type = 7z' in out(p) and 'f' in out(p)


def test_update_replaces_and_preserves_unrelated_members():
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root/'a').write_text('old'); (root/'b').write_text('keep')
        assert run(['a','x.7z','a','b'],d).returncode == 0
        (root/'a').write_text('newer content')
        p = run(['a','x.7z','a'],d)
        assert p.returncode == 0
        x = run(['x','x.7z','-oout'],d)
        assert x.returncode == 0
        assert (root/'out'/'a').read_text() == 'newer content'
        assert (root/'out'/'b').read_text() == 'keep'


def test_delete_and_rename():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'a').write_text('A'); (root/'b').write_text('B')
        assert run(['a','f.7z','a','b'],d).returncode == 0
        p=run(['rn','f.7z','a','dir/renamed'],d)
        assert p.returncode == 0
        assert run(['l','f.7z'],d).returncode == 0
        x=run(['x','f.7z','-oout'],d)
        assert x.returncode == 0 and (root/'out'/'dir'/'renamed').read_text() == 'A'
        p=run(['d','f.7z','b'],d)
        assert p.returncode == 0
        l=run(['l','f.7z'],d)
        assert 'b' not in out(l)


def test_hash_algorithms_are_real():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); payload=b'abc'; (root/'f').write_bytes(payload)
        p=run(['h','-scrcSHA256','f'],d)
        assert p.returncode == 0 and hashlib.sha256(payload).hexdigest() in out(p).lower()
        p=run(['h','-scrcCRC32','f'],d)
        assert p.returncode == 0 and f'{zlib.crc32(payload):08X}' in out(p)


def test_hash_stdin_empty_sha256():
    with tempfile.TemporaryDirectory() as d:
        p=run(['h','-si','-scrcSHA256'],d,b'')
        assert p.returncode == 0 and hashlib.sha256(b'').hexdigest() in out(p).lower()


def test_add_missing_input_is_warning_and_keeps_readable_input():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'ok').write_text('yes')
        p=run(['a','warn.7z','ok','missing'],d)
        assert p.returncode == 1
        assert 'WARNING:' in err(p) and 'missing' in err(p)
        assert 'Scan WARNINGS: 1' in out(p)
        t=run(['t','warn.7z'],d)
        assert t.returncode == 0


def test_wildcard_and_dotfile_selection():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'.hidden.txt').write_text('h'); (root/'a.txt').write_text('a'); (root/'b.bin').write_text('b')
        p=run(['a','sel.7z','*.txt'],d)
        assert p.returncode == 0
        l=out(run(['l','sel.7z'],d))
        assert '.hidden.txt' in l and 'a.txt' in l and 'b.bin' not in l


def test_include_exclude_and_spd_literal_name():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'a.txt').write_text('a'); (root/'b.txt').write_text('b'); (root/'*.txt').write_text('literal')
        p=run(['a','filtered.7z','-i!*.txt','-x!b.txt'],d)
        assert p.returncode == 0
        l=out(run(['l','filtered.7z'],d))
        assert 'a.txt' in l and 'b.txt' not in l
        p=run(['a','literal.7z','-spd','*.txt'],d)
        assert p.returncode == 0
        l=out(run(['l','literal.7z'],d))
        assert '*.txt' in l


def test_flat_extract_and_overwrite_modes():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'tree').mkdir(); (root/'tree'/'f').write_text('archive')
        assert run(['a','f.7z','tree'],d).returncode == 0
        (root/'flat').mkdir(); (root/'flat'/'f').write_text('existing')
        p=run(['e','-y','-aos','f.7z','-oflat'],d)
        assert p.returncode == 0 and (root/'flat'/'f').read_text() == 'existing'
        p=run(['e','-y','-aoa','f.7z','-oflat'],d)
        assert p.returncode == 0 and (root/'flat'/'f').read_text() == 'archive'


def test_list_technical_crc_and_unicode_names():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); name='日本語-Καλημέρα.txt'; data=b'payload'; (root/name).write_bytes(data)
        assert run(['a','u.7z',name],d).returncode == 0
        p=run(['l','-slt','u.7z'],d)
        assert p.returncode == 0 and name in out(p)
        assert f'{zlib.crc32(data):08X}' in out(p)


def test_case_distinct_members_remain_distinct():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'A').write_text('upper'); (root/'a').write_text('lower')
        p=run(['a','case.7z','A','a'],d)
        assert p.returncode == 0
        l=out(run(['l','case.7z'],d))
        assert re.search(r'\bA\b',l) and re.search(r'\ba\b',l)


def test_switch_case_and_operands_after_switches():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'f').write_text('x')
        p=run(['A','-MX0','f.7z','f'],d)
        assert p.returncode == 0
        l=run(['l','-SLT','f.7z'],d)
        assert l.returncode == 0 and 'Type = 7z' in out(l)


def test_stdout_routing_and_timing_switches():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'f').write_text('x')
        p=run(['a','-bso0','quiet.7z','f'],d)
        assert p.returncode == 0 and p.stdout == b''
        p=run(['a','-bt','timed.7z','f'],d)
        assert p.returncode == 0
        assert all(s in out(p) for s in ['Kernel  Time','User    Time','Process Time','Global  Time'])


def test_syntax_and_no_crash_on_malformed_operands():
    with tempfile.TemporaryDirectory() as d:
        for args in [['a'], ['l'], ['x'], ['t'], ['a','-i!','a.7z'], ['a','-saX','a.7z']]:
            p=run(args,d,timeout=8)
            assert p.returncode in (1,2,7)


def test_listfile_expansion_and_missing_listfile():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); (root/'one').write_text('1'); (root/'two').write_text('2')
        (root/'items.lst').write_text('one\ntwo\n', encoding='utf-8')
        p=run(['a','list.7z','@items.lst'],d)
        assert p.returncode == 0
        l=out(run(['l','list.7z'],d))
        assert 'one' in l and 'two' in l
        p=run(['a','no.7z','@absent.lst'],d)
        assert p.returncode == 7
        assert 'The file operation error for listfile' in err(p) and 'absent.lst' in err(p)


def test_all_byte_values_roundtrip_exactly():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); payload=bytes(range(256))*8; (root/'bytes.bin').write_bytes(payload)
        assert run(['a','bytes.7z','bytes.bin'],d).returncode == 0
        p=run(['x','-so','bytes.7z','bytes.bin'],d)
        assert p.returncode == 0 and p.stdout == payload


def test_benchmark_small_settings_finishes():
    p=run(['b','-md=256k','-mmt1'],'/workspace/eval',timeout=20)
    assert p.returncode == 0
    s=out(p)
    for token in ['Compiler:', 'CPU', 'Freq', 'Linux', 'PageSize', 'd=256k mt1']:
        assert token in s


def test_unknown_hash_algorithm_does_not_succeed_silently():
    with tempfile.TemporaryDirectory() as d:
        pathlib.Path(d,'f').write_text('x')
        p=run(['h','-scrcSHA512','f'],d)
        assert p.returncode != 0 or 'SHA512' in out(p) or 'SHA512' in err(p)
