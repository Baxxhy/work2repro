import os, re, subprocess, tempfile, pathlib, stat
import pytest

BIN = '/workspace/executable'

def run(*args, cwd=None, timeout=5):
    return subprocess.run([BIN, *map(str,args)], cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
def plain(b):
    return re.sub(rb'\x1b\[[0-9;]*m', b'', b).decode('utf-8')
def mkfile(p, data=b'x'):
    pathlib.Path(p).write_bytes(data)
    return pathlib.Path(p)
def size_rows(p):
    return plain(p.stdout).splitlines()

def test_version_precedence_and_alias():
    for flag in ('--version','-V'):
        r=run(flag, '--format', 'BAD')
        assert (r.returncode,r.stdout,r.stderr)==(0,b'dua 2.32.2\n',b'')

def test_global_help_and_subcommand_help():
    assert run('--help').returncode == 0
    assert b'Commands:' in run('--help').stdout
    for cmd in ('aggregate','a','interactive','i','completions'):
        r=run(cmd,'--help')
        assert r.returncode==0 and b'Usage: executable' in r.stdout and not r.stderr

def test_parse_errors_are_status_two_and_helpful():
    for args, needle in [(('--format','bad'),b"invalid value 'bad'"),(('--threads','x'),b"invalid value 'x'"),(('--wat',),b"error:"),(('--ignore-dirs',),b'--ignore-dirs')]:
        r=run(*args); assert r.returncode==2 and needle in r.stderr and b'--help' in r.stderr and not r.stdout
    r=run('--threads','2','--threads','3'); assert r.returncode==2 and b'cannot be used multiple times' in r.stderr
    r=run('aggregate','--format','bytes'); assert r.returncode==2

def test_completion_shells_and_bad_case():
    for sh in ('bash','elvish','fish','powershell','zsh'):
        r=run('completions',sh); assert r.returncode==0 and r.stdout.endswith(b'\n') and not r.stderr
    r=run('completions','BASH'); assert r.returncode==2 and b"invalid value 'BASH'" in r.stderr

def test_file_sizes_format_and_names():
    with tempfile.TemporaryDirectory() as d:
        p=mkfile(pathlib.Path(d)/"a $'雪",b'12345')
        r=run('--apparent-size','--format','bytes','aggregate','--no-sort',p)
        assert r.returncode==0 and b'12345 b' in plain(r.stdout).encode() and str(p).encode() in r.stdout
        assert b'\x1b[32m' in r.stdout
        r=run('-A','-f','BYTES','a $\'雪',cwd=d)
        assert r.returncode==0 and b'12345 b' in r.stdout

def test_expansion_sort_totals_and_no_total():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d); mkfile(root/'b',b'22'); mkfile(root/'a',b'1'); (root/'.hidden').write_bytes(b'')
        r=run('-A','-f','bytes','aggregate','--no-sort',root)
        out=plain(r.stdout); assert r.returncode==0 and 'a' in out and 'b' in out and '.hidden' in out and 'total' in out
        assert out.index('.hidden') < out.index('a') < out.index('b')
        assert 'total' not in plain(run('-A','-f','bytes','aggregate','--no-total',root).stdout)

def test_explicit_order_duplicates_and_single_file_total():
    with tempfile.TemporaryDirectory() as d:
        a=mkfile(pathlib.Path(d)/'a',b'aa'); b=mkfile(pathlib.Path(d)/'b',b'b')
        r=run('-A','-f','bytes','aggregate','--no-sort',a,b,a)
        out=plain(r.stdout); assert out.index(str(a)) < out.index(str(b)) < out.rindex(str(a)) and 'total' in out
        assert 'total' not in plain(run('aggregate','--no-total',a).stdout)

def test_failed_roots_render_and_no_sort_omits():
    r=run('-f','bytes','aggregate','/definitely/missing/eval-x','/definitely/missing/eval-y')
    assert r.returncode==1 and b'<1 IO Error>' in r.stdout and b'<2 IO Errors>' in r.stdout
    r=run('-f','bytes','aggregate','--no-sort','/definitely/missing/eval-x','/definitely/missing/eval-y')
    assert r.returncode==1 and b'/definitely/missing' not in r.stdout and b'<2 IO Errors>' in r.stdout

def test_apparent_directory_and_recursive_symlinks():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d)/'tree'; root.mkdir(); mkfile(root/'f',b'12345'); (root/'ln').symlink_to(root/'f'); (root/'broken').symlink_to(root/'none')
        r=run('-A','-f','bytes','aggregate','--no-sort',root)
        out=plain(r.stdout); assert 'f' in out and 'ln' in out and 'broken' in out and '<1 IO Error>' in out and r.returncode==1
        r=run('-A','-f','bytes','aggregate',root/'ln'); assert b'5 b' in plain(r.stdout).encode()

def test_hardlink_dedup_and_count_option():
    with tempfile.TemporaryDirectory() as d:
        a=mkfile(pathlib.Path(d)/'a',b'x'); b=pathlib.Path(d)/'b'; os.link(a,b)
        r=run('-f','bytes','aggregate','--no-sort',a,b); assert b'4096 b' in r.stdout and b'8192 b' not in r.stdout
        r=run('-l','-f','bytes','aggregate','--no-sort',a,b); assert b'8192 b' in r.stdout

def test_ignore_accumulates_stats_and_threads():
    with tempfile.TemporaryDirectory() as d:
        root=pathlib.Path(d)/'tree'; root.mkdir(); x=root/'x'; x.mkdir(); mkfile(x/'f',b'abc'); y=root/'y'; y.mkdir(); mkfile(y/'g',b'12345')
        r=run('-A','-f','bytes','--ignore-dirs',x,'aggregate','--stats',root)
        assert r.returncode==0 and b'Statistics {' in r.stderr and b'entries_traversed:' in r.stderr
        assert b'3 b' not in plain(r.stdout).encode()
        for n in ('0','1','3'):
            assert run('--threads',n,'-A','aggregate','--no-sort',root).returncode==0

def test_log_append_and_failure():
    with tempfile.TemporaryDirectory() as d:
        log=pathlib.Path(d)/'log'; log.write_text('prior\n')
        for _ in range(2): assert run('--log-file',log,'aggregate','/missing/log-target').returncode==1
        s=log.read_text(); assert s.startswith('prior') and s.count('dua options')==2 and s.count('Ignoring canonicalized')==2
        r=run('--log-file',pathlib.Path(d)/'absent'/'log','aggregate'); assert r.returncode==1 and b'No such file or directory' in r.stderr

def test_non_tty_interactive_fails_without_report():
    for c in ('interactive','i'):
        r=run(c); assert r.returncode==1 and b'Interactive mode requires a connected terminal' in r.stderr and not r.stdout

def test_format_conversions_and_zero():
    with tempfile.TemporaryDirectory() as d:
        p=mkfile(pathlib.Path(d)/'f',b'')
        for fmt,expected in [('binary',b'0   B'),('metric',b'0  B'),('mb',b'0.00 MB'),('mib',b'0.00 MiB'),('gb',b'0.00 GB'),('gib',b'0.00 GiB')]:
            r=run('-A','-f',fmt,'aggregate',p); assert r.returncode==0 and expected in r.stdout
