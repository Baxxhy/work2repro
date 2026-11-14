import os
import pathlib
import subprocess
import tempfile
import zlib
import pytest

EXE = pathlib.Path('/workspace/executable')
HELP = '''Compress or decompress the INPUT file(s); reads from STDIN if INPUT is `-` or not provided.

Usage: executable [OPTIONS...] [INPUT... | -] [-o OUTPUT]

Options:
  -o OUTPUT                     Write output to a single file, OUTPUT.
  -k, --keep                    Preserve INPUT file(s). [Default] 
  --rm                          Remove INPUT file(s) after successful (de)compression to file.

  -#                            Desired compression level, where `#` is a number between 1 and 19;
                                lower numbers provide faster compression, higher numbers yield
                                better compression ratios. [Default: 3]

  -d, --decompress              Perform decompression.
  -D DICT                       Use DICT as the dictionary for compression or decompression.

  -f, --force                   Disable input and output checks. Allows overwriting existing files,
                                receiving input from the console, printing output to STDOUT, and
                                operating on links, block devices, etc. Unrecognized formats will be
                                passed-through through as-is.

  -h                            Display short usage and exit.
  -H, --help                    Display full help and exit.
  -V, --version                 Display the program version and exit.

'''
VERSION = '*** Zstandard CLI (64-bit) v1.6.0, by Yann Collet ***\n'

def run(*args, data=None, cwd=None, env=None, timeout=10):
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=cwd, env=env, timeout=timeout)

def frame(payload, *opts):
    p=run('-q','-c',*opts,data=payload)
    assert p.returncode == 0, p.stderr
    assert p.stdout.startswith(b'\x28\xb5\x2f\xfd')
    return p.stdout

def test_short_help_exact():
    p=run('-h')
    assert p.returncode == 0 and p.stdout.decode() == HELP and p.stderr == b''

def test_full_help_has_short_help_and_documented_options():
    p=run('--help')
    assert p.returncode == 0 and HELP in p.stdout.decode()
    assert all(x in p.stdout.decode() for x in ('Advanced options:', '--train-fastcover', '--format=gzip', '--priority=rt'))
    assert not any(x in p.stdout.decode().lower() for x in ('subcommand','commands:','available commands'))

def test_version_modes():
    assert run('--version').stdout.decode() == VERSION
    assert run('-qq','-V').stdout == b'1.6.0\n'
    p=run('-vvv','-V')
    assert p.stdout.decode().startswith(VERSION+'*** supports: zstd, gzip\n')
    assert p.stderr == b''

def test_pipe_round_trip_arbitrary_binary():
    payload=bytes(range(256))*4+b'\0\xff'*99
    c=run('-c',data=payload)
    assert c.returncode == 0 and c.stderr == b'' and c.stdout[:4] == b'\x28\xb5\x2f\xfd'
    d=run('-dc',data=c.stdout)
    assert d.returncode == 0 and d.stdout == payload and d.stderr == b''

def test_empty_pipe_compresses_to_valid_nonempty_frame():
    c=run('-c',data=b'')
    assert c.returncode == 0 and c.stdout.startswith(b'\x28\xb5\x2f\xfd') and c.stdout
    assert run('-dc',data=c.stdout).stdout == b''

def test_empty_stdin_decompression_is_error():
    p=run('-d',data=b'')
    assert p.returncode != 0 and b'unexpected end of file' in p.stderr

def test_named_file_default_output_and_roundtrip():
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td)/'space ü.txt'; payload=b'abc\0'*1000; src.write_bytes(payload)
        p=run(src)
        assert p.returncode == 0 and p.stdout == b''
        z=pathlib.Path(str(src)+'.zst')
        assert src.exists() and z.read_bytes().startswith(b'\x28\xb5\x2f\xfd')
        q=run('-d',z)
        assert q.returncode == 0 and src.read_bytes()==payload

def test_explicit_output_force_and_transactional_overwrite():
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td)/'a'; out=pathlib.Path(td)/'chosen'; src.write_bytes(b'hello')
        out.write_bytes(b'keep')
        p=run('-o',out,src)
        assert p.returncode != 0 and out.read_bytes()==b'keep'
        p=run('-f','-o',out,src)
        assert p.returncode == 0 and out.read_bytes().startswith(b'\x28\xb5\x2f\xfd')

def test_dash_terminates_options_for_leading_dash_path():
    with tempfile.TemporaryDirectory() as td:
        pathlib.Path(td,'-input').write_bytes(b'x')
        p=run('--','-input',cwd=td)
        assert p.returncode == 0 and pathlib.Path(td,'-input.zst').exists()

def test_combined_flags_and_last_operation_selector():
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td,'a'); f.write_bytes(b'abc')
        c=run('-qf',f)
        assert c.returncode == 0
        z=pathlib.Path(td,'a.zst')
        p=run('--compress','-dc',z)
        assert p.returncode == 0 and p.stdout == b'abc'

def test_stdin_stdout_with_explicit_dash_and_no_transcoding():
    payload=b'\x00\r\n\xff'
    c=run('-c','-',data=payload)
    assert c.returncode == 0 and run('-d','-',data=c.stdout).stdout == payload

def test_bad_named_format_and_tiny_header_diagnostics():
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td,'plain.zst'); f.write_bytes(b'nope')
        p=run('-d',f)
        assert p.returncode == 1 and p.stderr.decode()==f'zstd: {f}: unsupported format \n'
        f.write_bytes(b'\x28\xb5\x2f')
        p=run('-d',f)
        assert p.returncode == 1 and p.stderr.decode()==f'zstd: {f}: unknown header \n'

def test_corrupt_frame_does_not_leave_destination():
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td,'bad.zst'); f.write_bytes(b'\x28\xb5\x2f\xfdcorrupted data here')
        out=pathlib.Path(td,'out')
        p=run('-d','-o',out,f)
        assert p.returncode == 1 and not out.exists()
        assert b'Decoding error (36) :' in p.stderr

def test_truncated_stdin_reports_premature_end():
    c=frame(b'payload'*200,'-C')
    p=run('-d',data=c[:-1])
    assert p.returncode == 1 and p.stderr == b'/*stdin*\\ : Read error (39) : premature end \n'

def test_streaming_stdout_keeps_decoded_data_before_late_checksum_failure():
    payload=b'payload'*200; c=frame(payload,'-C')
    p=run('-d','-c',data=c[:-1])
    assert p.returncode == 1 and p.stdout == payload

def test_concatenated_frames_and_skippable_frame():
    a=frame(b'first'); b=frame(b'second')
    skip=b'\x50\x2a\x4d\x18'+(3).to_bytes(4,'little')+b'xyz'
    p=run('-dc',data=a+skip+b)
    assert p.returncode == 0 and p.stdout==b'firstsecond'

def test_checksum_corruption_rejected():
    c=frame(b'checksum payload','-C')
    damaged=c[:-1]+bytes([c[-1]^1])
    p=run('-d','-c',data=damaged)
    assert p.returncode != 0 and b"doesn't match checksum" in p.stderr

def test_multiple_frames_and_compression_determinism():
    payload=b'compress me '*1000
    assert frame(payload)==frame(payload)
    q=run('-dc',data=frame(payload)+frame(payload))
    assert q.returncode==0 and q.stdout==payload*2

def test_levels_options_and_threaded_roundtrip():
    payload=b'Z'*20000
    for opts in [('-1',),('-19',),('--fast=2x',),('--long=20x',),('-T2',),('--single-thread',),('--ultra','-20')]:
        c=frame(payload,*opts)
        assert run('-dc',data=c).stdout==payload

def test_fast_trailing_character_is_same_setting():
    payload=b'hello world '*500
    assert frame(payload,'--fast=2x')==frame(payload,'--fast=2')

def test_unknown_options_have_help_diagnostic():
    p=run('--longX')
    assert p.returncode==1 and p.stderr.decode().startswith('Incorrect parameter: --longX \n')
    assert HELP in p.stderr.decode()

def test_missing_dictionary_argument_exact():
    p=run('-Dfoo')
    assert p.returncode==1 and p.stdout==b'' and p.stderr==b'error: missing command argument \n'

def test_long_boolean_assignment_rejected():
    for option in ('--check=1','--progress=maybe','--asyncio=no'):
        p=run(option)
        assert p.returncode==1 and b'Incorrect parameter:' in p.stderr

def test_invalid_stream_size_is_transactional():
    p=run('-c','--stream-size=4',data=b'abc')
    assert p.returncode==11 and p.stdout==b'' and p.stderr==b'zstd: error 11 : Src size is incorrect \n'

def test_named_input_suffix_mapping_and_unknown_suffix():
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td,'thing'); src.write_bytes(b'data')
        z=pathlib.Path(str(src)+'.zst'); z.write_bytes(frame(b'data'))
        p=run('-d',z)
        assert p.returncode==0 and src.read_bytes()==b'data'
        weird=pathlib.Path(td,'thing.blob'); weird.write_bytes(frame(b'data'))
        p=run('-d',weird)
        assert p.returncode==1 and b'unknown suffix' in p.stderr and not pathlib.Path(str(weird)[:-5]).exists()
        out=pathlib.Path(td,'exact')
        p=run('-d','-o',out,weird)
        assert p.returncode==0 and out.read_bytes()==b'data'

def test_compression_keeps_input_and_rm_removes_only_after_success():
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td,'keep'); src.write_bytes(b'hello')
        assert run(src).returncode==0 and src.exists()
        other=pathlib.Path(td,'remove'); other.write_bytes(b'world')
        assert run('--rm',other).returncode==0 and not other.exists() and pathlib.Path(str(other)+'.zst').exists()

def test_gzip_format_roundtrip():
    payload=b'gzip binary\0'*100
    with tempfile.TemporaryDirectory() as td:
        src=pathlib.Path(td,'in'); out=pathlib.Path(td,'out.gz'); src.write_bytes(payload)
        p=run('-q','--format=gzip','-o',out,src)
        assert p.returncode==0 and out.read_bytes().startswith(b'\x1f\x8b')
        q=run('-q','-d','-c',out)
        assert q.returncode==0 and q.stdout==payload

def test_pass_through_only_when_requested():
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td,'plain'); f.write_bytes(b'plain text')
        p=run('-d','-c',f)
        assert p.returncode!=0
        q=run('-d','-c','--pass-through',f)
        assert q.returncode==0 and q.stdout==b'plain text'

def test_test_mode_validates_without_output():
    with tempfile.TemporaryDirectory() as td:
        f=pathlib.Path(td,'data.zst'); f.write_bytes(frame(b'valid data'))
        p=run('-t',f)
        assert p.returncode==0 and not pathlib.Path(td,'data').exists() and f.exists()
        f.write_bytes(b'not zstd')
        p=run('-t',f)
        assert p.returncode==1 and p.stderr.decode()==f'zstd: {f}: unsupported format \n'

def test_list_mode_rejects_stdin():
    p=run('-l',data=b'')
    assert p.returncode==1 and p.stdout==b''
    assert p.stderr==b'zstd: --list does not support reading from standard input \nNo files given \n'

def test_recursive_output_and_flat_directory_last_wins():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); inp=root/'in'; inp.mkdir(); (inp/'a').write_bytes(b'a')
        one=root/'one'; two=root/'two'; one.mkdir(); two.mkdir()
        p=run('-q','-r','--output-dir-flat',one,'--output-dir-flat',two,inp)
        assert p.returncode==0 and not list(one.iterdir()) and (two/'a.zst').exists()

def test_filelist_preserves_input_lines():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); f=root/'a'; f.write_bytes(b'a'); listing=root/'list'; listing.write_text(str(f)+'\n')
        p=run('-q','--filelist',listing)
        assert p.returncode==0 and pathlib.Path(str(f)+'.zst').exists()

def test_trace_csv_header_and_records_append():
    with tempfile.TemporaryDirectory() as td:
        root=pathlib.Path(td); src=root/'in'; src.write_bytes(b'abc'); log=root/'trace.csv'
        p=run('-q','--trace',log,src)
        assert p.returncode==0
        lines=log.read_text().splitlines()
        assert lines[0]=='Algorithm, Version, Method, Mode, Level, Workers, Dictionary Size, Uncompressed Size, Compressed Size, Duration Nanos, Compression Ratio, Speed MB/s'
        assert len(lines)==2 and lines[1].split(', ')[0:3]==['zstd','10600','compress']
        size=log.stat().st_size
        p=run('-q','--trace',log,src)
        assert p.returncode==0 and log.stat().st_size>size

def test_concurrent_independent_compressions():
    with tempfile.TemporaryDirectory() as td:
        fs=[]
        for i in range(4):
            f=pathlib.Path(td,str(i)); f.write_bytes(bytes([i])*10000); fs.append(f)
        procs=[subprocess.Popen([str(EXE),'-q',str(f)],stdout=subprocess.PIPE,stderr=subprocess.PIPE) for f in fs]
        assert all(p.wait(timeout=5)==0 for p in procs)
        for i,f in enumerate(fs):
            assert run('-q','-d','-c',str(f)+'.zst').stdout==bytes([i])*10000
