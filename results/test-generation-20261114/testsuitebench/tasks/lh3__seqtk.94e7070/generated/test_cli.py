import gzip
import os
import subprocess
from pathlib import Path

import pytest

BIN = Path('/workspace/executable')
ROOT = Path('/workspace/eval')


def run(*args, data=None):
    return subprocess.run([str(BIN), *map(str, args)], input=data, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, cwd=ROOT)


def put(tmp_path, name, data):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


def test_usage_and_unknown_command():
    r = run()
    assert r.returncode == 1 and all(x in r.stderr for x in (b'Usage:', b'seqtk <command>', b'Version: 1.5-r133', b'trimfq'))
    r = run('--help')
    assert r.returncode == 1 and b"[main] unrecognized command '--help'. Abort!\n" == r.stderr


def test_missing_input_has_standard_error(tmp_path):
    r = run('size', str(tmp_path / 'absent.fa'))
    assert r.returncode == 1 and b'[E::stk_size] failed to open the input file/stream.' in r.stderr


def test_seq_normalize_filter_transform_and_strand(tmp_path):
    p = put(tmp_path, 'reads.fa', b'>a comment\natcg\n>b\nAC\n>c\nATN\n')
    assert run('seq', '-l', '0', p).stdout == b'>a comment\natcg\n>b\nAC\n>c\nATN\n'
    assert run('seq', '-L2', '-2', p).stdout == b'>b\nAC\n'
    assert run('seq', '-N', p).stdout == b'>a comment\natcg\n>b\nAC\n'
    assert run('seq', '-U', '-C', p).stdout == b'>a\nATCG\n>b\nAC\n>c\nATN\n'
    assert run('seq', '-r', put(tmp_path, 'one.fa', b'>x note\nATCGRYSWKMBDHVN\n')).stdout == b'>x note\nNBDHVKMWSRYCGAT\n'
    assert run('seq', '-R', '-a', put(tmp_path, 'single.fa', b'>x\nAC\n')).stdout == b'>x+\nAC\n>x-\nGT\n'


def test_seq_quality_regions_and_sampling(tmp_path):
    fq = put(tmp_path, 'q.fq', b'@r c\nATCGATCGATCG\n+ignored\nIIIHHHGGGFFF\n')
    assert run('seq', '-q40', fq).stdout == b'@r c\nATCgatcgatcg\n+\nIIIHHHGGGFFF\n'
    assert run('seq', '-q40', '-nN', fq).stdout == b'@r c\nATCNNNNNNNNN\n+\nIIIHHHGGGFFF\n'
    p = put(tmp_path, 'region.fa', b'>x\nATCGATCG\n')
    reg = put(tmp_path, 'r.bed', b'x\t2\t5\n')
    assert run('seq', '-M', reg, p).stdout == b'>x\nATcgaTCG\n'
    assert run('seq', '-M', reg, '-c', p).stdout == b'>x\natCGAtcg\n'
    assert run('seq', '-M', reg, '-n', 'N', p).stdout == b'>x\nATNNNTCG\n'
    assert run('seq', '-f', '0', p).stdout == b''
    assert run('seq', '-f', '1', p).stdout == b'>x\nATCGATCG\n'
    assert run('seq', '-a', '-F', 'I', p).stdout == b'>x\nATCGATCG\n'


def test_seq_compaction_quirk_and_offset(tmp_path):
    p = put(tmp_path, 'space.fq', b'@x\nATCG ACGT\n+\nIIII IIII\n')
    assert run('seq', '-S', '-l0', p).stdout == b'@x\nATCGACGTT\n+\nIIIIIIIII\n'
    q = put(tmp_path, 'offset.fq', b'@x\nAAAA\n+\nIIII\n')
    assert run('seq', '-V', '-Q64', q).stdout == b'@x\nAAAA\n+\n****\n'


def test_seeded_fraction_is_repeatable(tmp_path):
    p = put(tmp_path, 'records.fa', b''.join(b'>r%d\nA\n' % i for i in range(20)))
    first = run('seq', '-f', '0.5', '-s', '27', p)
    second = run('seq', '-f', '0.5', '-s', '27', p)
    assert first.stdout == second.stdout


def test_subseq_regions_and_table(tmp_path):
    p = put(tmp_path, 'x.fa', b'>x comment\nACGTAC\n>y\nTT\n')
    reg = put(tmp_path, 'regions', b'x 2 5\ny 2\nmissing\n')
    assert run('subseq', p, reg).stdout == b'>x:3-5 comment\nGTA\n>y:2-2\nT\n'
    assert run('subseq', '-t', p, reg).stdout == b'x\t3\tGTA\ny\t2\tT\n'
    fq = put(tmp_path, 'x.fq', b'@x c\nACGT\n+\nabcd\n')
    rr = put(tmp_path, 'rr', b'x 1 3\n')
    assert run('subseq', fq, rr).stdout == b'@x:2-3 c\nCG\n+\nab\n'
    bed6 = put(tmp_path, 'strand.bed', b'x\t0\t4\tname\t0\t-\n')
    assert run('subseq', '-s', '-t', p, bed6).stdout == b'x\t1\tACGT\n'


def test_size_comp_and_gzip(tmp_path):
    p = put(tmp_path, 'a.fa', b'>x\nACGT\n>z\n\n')
    gz = tmp_path / 'reads.gz'
    gz.write_bytes(gzip.compress(Path(p).read_bytes()))
    assert run('size', str(gz)).stdout == b'2\t4\n'
    assert run('size', data=b'').stdout == b'0\t0\n'
    row = run('comp', p).stdout.decode().splitlines()
    assert len(row) == 2 and row[0].split('\t') == ['x','4','1','1','1','1','0','0','0','0','0','0','0']
    assert row[1].split('\t')[:2] == ['z','0']


def test_fqchk_and_trimfq(tmp_path):
    p = put(tmp_path, 'reads.fq', b'@x\nAC\n+\n!I\n')
    out = run('fqchk', '-q', '1', p).stdout.decode().splitlines()
    assert out[0] == 'min_len: 2; max_len: 2; avg_len: 2.00; 2 distinct quality values'
    assert out[1].startswith('POS\t#bases\t%A') and out[2].startswith('ALL\t2\t50.0\t0.0\t0.0\t0.0\t50.0')
    assert run('trimfq', '-b', '5', p).stdout == b'@x\nAC\n+\n!I\n'
    long = put(tmp_path, 'long.fq', b'@x c\n' + b'A'*100 + b'\n+\n' + b'I'*60+b'!'*40+b'\n')
    assert run('trimfq', long).stdout == b'@x c\n'+b'A'*60+b'\n+\n'+b'I'*60+b'\n'


def test_sample_seeded_modes(tmp_path):
    p = put(tmp_path, 'many.fa', b'>a\nA\n>b\nC\n>c\nG\n>d\nT\n')
    assert run('sample', '-s', '11', p, '1.0').stdout.count(b'>') == 1
    assert run('sample', p, '0').stdout == b''
    assert run('sample', p, '9').stdout == Path(p).read_bytes()
    r = run('sample', '-2', p, '2')
    assert r.returncode == 0 and r.stdout.count(b'>') == 2
    r = run('sample', '-2', '-', '2', data=b'')
    assert r.returncode == 1 and b'cannot be STDIN' in r.stderr


def test_mergepe_dropse_rename(tmp_path):
    a = put(tmp_path, 'a.fa', b'>a/1 c1\nA\n>same\nC\n')
    b = put(tmp_path, 'b.fa', b'>a/2 c2\nT\n>same\nG\n')
    assert run('mergepe', a, b).stdout == b'>a/1 c1\nA\n>a/2 c2\nT\n>same\nC\n>same\nG\n'
    p = put(tmp_path, 'inter.fa', b'>x/1 c1\nA\n>x/2 c2\nC\n>same\nG\n>same\nT\n')
    assert run('dropse', p).stdout == b'>x/1 c1\nA\n>x/2 c2\nC\n>same c2\nG\n>same\nT\n'
    q = put(tmp_path, 'rename.fa', b'>old c\nA\n>other\nB\n')
    assert run('rename', q).stdout == b'>1 c\nA\n>2 c\nB\n'
    assert run('rename', q, 'p').stdout == b'>p1 c\nA\n>p2 c\nB\n'


def test_mergefa_famask_mutfa(tmp_path):
    a = put(tmp_path, 'a.fa', b'>x\nACGT\n')
    b = put(tmp_path, 'b.fa', b'>y\nAGCT\n')
    r = run('mergefa', a, b)
    assert r.stdout == b'>x\nASS T\n'.replace(b' ', b'') and b'Different sequence names: x != y' in r.stderr and b'(same,diff,hom-het,het-hom,het-het)=' in r.stderr
    src = put(tmp_path, 'src.fa', b'>x note\nACGT\n')
    mask = put(tmp_path, 'mask.fa', b'>x\nXxAX\n')
    assert run('famask', src, mask).stdout == b'>x\nAcAT\n'
    snp = put(tmp_path, 'snp', b'x 2 C N\nx 2 C G\nx 9 A T\n')
    assert run('mutfa', src, snp).stdout == b'>x\nAGGT\n'


def test_listhet_hety_gap_gc(tmp_path):
    p = put(tmp_path, 'iupac.fa', b'>x\nAMrSVN?\n')
    assert run('listhet', p).stdout == b'x\t2\tM\nx\t3\tr\nx\t4\tS\n'
    h = put(tmp_path, 'het.fa', b'>x\nACMR\n')
    assert run('hety', '-w', '10', h).stdout == b'x\t0\t4\t5.00\t4\t2\n'
    g = put(tmp_path, 'gap.fa', b'>x\nNacNNt\n')
    assert run('gap', '-l', '2', g).stdout == b'x\t0\t1\nx\t3\t5\n'
    assert run('gc', '-f', '0.5', '-l', '2', put(tmp_path,'gc.fa',b'>x\nGGCAAA\n')).stdout == b'x\t0\t3\t3\n'


def test_cutn_hpc_hrun(tmp_path):
    p = put(tmp_path, 'cut.fa', b'>x\nAANNNCC\n')
    assert run('cutN', '-n', '3', p).stdout == b'>x:1-2\nAA\n>x:6-7\nCC\n'
    assert run('cutN', '-g', '-n', '3', p).stdout == b'2\t5\n'
    q = put(tmp_path, 'hpc.fq', b'@x c\nAAaaCC\n+\n123456\n>z\n\n')
    assert run('hpc', q).stdout == b'>x\nAaC\n'
    assert run('hrun', 'x', data=b'>x\nAAAAA\n').returncode == 1
    assert run('hrun', '5', put(tmp_path,'run.fa',b'>x\nAAAAAC\n')).stdout == b'x\t0\t5\tA\n'


def test_split_randbase_kfreq_telo(tmp_path):
    p = put(tmp_path, 'split.fa', b'>a c\nAC\n>b\nGT\n')
    prefix = str(tmp_path / 'part')
    r = run('split', '-n', '3', prefix, p)
    assert r.returncode == 0
    assert Path(prefix+'.00001.fa').read_bytes() == b'>a c\nAC\n'
    assert Path(prefix+'.00002.fa').read_bytes() == b'>b\nGT\n'
    assert Path(prefix+'.00003.fa').read_bytes() == b''
    amb = put(tmp_path, 'amb.fa', b'>x note\nAMRSWYKmrsywkNBDHVX\n')
    assert run('randbase', amb).stdout == b'>x\nACGGTTTcgcttgNBDHVX\n'
    k = put(tmp_path, 'k.fa', b'>x\nAAATTTNAAA\n>short\nA\n')
    rows = run('kfreq', 'AAA', k).stdout.splitlines()
    assert rows == [b'x\t10\t+\t3\t2', b'short\t1\t-\t0\t0']
    telo = put(tmp_path, 'telo.fa', b'>x\nCCCTAACCCTAA\n')
    r = run('telo', telo)
    assert r.stdout == b'x\t0\t12\t12\n' and r.stderr == b'12\t12\n'


@pytest.mark.parametrize('command,args', [
    ('size', ()), ('seq', ()), ('comp', ()), ('sample', ()), ('subseq', ()),
    ('fqchk', ()), ('trimfq', ()), ('mergepe', ()), ('mergefa', ()),
    ('famask', ()), ('mutfa', ()), ('split', ()), ('randbase', ()),
    ('hrun', ()), ('kfreq', ()),
], ids=['size','seq','comp','sample','subseq','fqchk','trimfq','mergepe','mergefa','famask','mutfa','split','randbase','hrun','kfreq'])
def test_missing_required_args(command, args):
    r = run(command, *args)
    assert r.returncode == 1 and b'Usage:' in r.stderr
