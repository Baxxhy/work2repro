import gzip
import os
import pathlib
import subprocess
import tempfile

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
EXE = pathlib.Path('/workspace/executable')


def put(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text)
    return p


def run(*args, input=None):
    return subprocess.run([str(EXE), *map(str, args)], input=input, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def lines(s):
    return s.splitlines()


def test_top_level_help_and_version():
    for arg in ((), ('--help',), ('-h',)):
        p = run(*arg)
        assert p.returncode == 0
        assert all(x in p.stdout for x in ('bedtools is a powerful toolset for genome arithmetic',
                    'Usage:     bedtools <subcommand>', 'intersect', 'merge', 'subtract', 'coverage'))
    p = run('--version')
    assert p.returncode == 0 and 'bedtools' in p.stdout and any(c.isdigit() for c in p.stdout)
    p = run('not-a-command')
    assert p.returncode != 0 and p.stderr


def test_intersect_pair_reports_and_unmatched(tmp_path):
    a = put(tmp_path, 'a', 'chr1\t0\t10\ta\nchr1\t10\t12\tb\n')
    b = put(tmp_path, 'b', 'chr1\t3\t7\tx\nchr1\t10\t11\ty\n')
    assert lines(run('intersect','-a',a,'-b',b).stdout) == ['chr1\t3\t7\ta']
    assert lines(run('intersect','-a',a,'-b',b,'-wa','-wb').stdout) == ['chr1\t0\t10\ta\tchr1\t3\t7\tx']
    assert lines(run('intersect','-a',a,'-b',b,'-wo').stdout) == ['chr1\t0\t10\ta\tchr1\t3\t7\tx\t4']
    assert lines(run('intersect','-a',a,'-b',b,'-c').stdout) == ['chr1\t0\t10\ta\t1','chr1\t10\t12\tb\t1']
    assert lines(run('intersect','-a',a,'-b',b,'-v').stdout) == []


def test_intersect_union_leftouter_fraction_and_validation(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t10\tA\nchr1\t20\t21\tB\n')
    b=put(tmp_path,'b','chr1\t2\t5\tx\nchr1\t4\t8\ty\n')
    assert lines(run('intersect','-a',a,'-b',b,'-wao').stdout)==[
        'chr1\t0\t10\tA\tchr1\t2\t5\tx\t3','chr1\t0\t10\tA\tchr1\t4\t8\ty\t4',
        'chr1\t20\t21\tB\t.\t-1\t-1\t.\t0']
    assert lines(run('intersect','-a',a,'-b',b,'-f','0.6','-u').stdout)==['chr1\t0\t10\tA']
    p=run('intersect','-a',a,'-b',b,'-f','0')
    assert p.returncode != 0 and p.stdout == '' and p.stderr.rstrip().endswith('***** ERROR: -f must be in the range (0.0, 1.0]. *****')


def test_intersect_multidb_names(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t5\tx\n')
    b1=put(tmp_path,'b1','chr1\t1\t2\n'); b2=put(tmp_path,'b2','chr1\t3\t4\n')
    p=run('intersect','-a',a,'-b',b1,b2,'-names','left','right','-wa','-wb')
    assert lines(p.stdout)==['chr1\t0\t5\tx\tleft\tchr1\t1\t2','chr1\t0\t5\tx\tright\tchr1\t3\t4']
    assert lines(run('intersect','-a',a,'-b',b1,b2,'-C').stdout)==['chr1\t0\t5\tx\t1\t1','chr1\t0\t5\tx\t2\t1']


def test_closest_ties_distance_and_null(tmp_path):
    a=put(tmp_path,'a','chr1\t5\t6\ta\t0\t-\nchr2\t0\t1\tz\t0\t+\n')
    b=put(tmp_path,'b','chr1\t3\t4\tl\t0\t+\nchr1\t7\t8\tr\t0\t+\n')
    p=run('closest','-a',a,'-b',b,'-D','a')
    assert lines(p.stdout)==['chr1\t5\t6\ta\t0\t-\tchr1\t7\t8\tr\t0\t+\t-1',
                            'chr1\t5\t6\ta\t0\t-\tchr1\t3\t4\tl\t0\t+\t1',
                            'chr2\t0\t1\tz\t0\t+\t.\t-1\t-1\t.\t-1\t.\t-1']


def test_coverage_and_genomecov(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t5\tx\n'); b=put(tmp_path,'b','chr1\t1\t4\nchr1\t3\t6\n')
    assert lines(run('coverage','-a',a,'-b',b).stdout)==['chr1\t0\t5\tx\t2\t4\t5\t0.8000000']
    assert lines(run('coverage','-a',a,'-b',b,'-counts').stdout)==['chr1\t0\t5\tx\t2']
    g=put(tmp_path,'genome','chr1\t6\n')
    assert lines(run('genomecov','-i',b,'-g',g,'-bg').stdout)==['chr1\t1\t3\t1','chr1\t3\t4\t2','chr1\t4\t6\t1']
    assert lines(run('genomecov','-i',b,'-g',g,'-d').stdout)==['chr1\t1\t0','chr1\t2\t1','chr1\t3\t1','chr1\t4\t2','chr1\t5\t1','chr1\t6\t1']


def test_merge_aggregation_and_errors(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t3\tx\t2\nchr1\t3\t5\ty\t4\nchr1\t8\t9\tz\t6\n')
    assert lines(run('merge','-i',a).stdout)==['chr1\t0\t5','chr1\t8\t9']
    assert lines(run('merge','-i',a,'-d','3').stdout)==['chr1\t0\t9']
    assert lines(run('merge','-i',a,'-c','4,5','-o','collapse,mean').stdout)==['chr1\t0\t5\tx,y\t3','chr1\t8\t9\tz\t6']


def test_map_subtract_and_modifiers(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t10\tA\t0\t+\n')
    b=put(tmp_path,'b','chr1\t2\t4\tb1\t2\t+\nchr1\t6\t8\tb2\t4\t-\n')
    assert lines(run('map','-a',a,'-b',b,'-c','5','-o','sum').stdout)==['chr1\t0\t10\tA\t6']
    assert lines(run('map','-a',a,'-b',b,'-c','4','-o','collapse').stdout)==['chr1\t0\t10\tA\tb1,b2']
    assert lines(run('subtract','-a',a,'-b',b).stdout)==['chr1\t0\t2\tA\t0\t+','chr1\t4\t6\tA\t0\t+','chr1\t8\t10\tA\t0\t+']
    assert lines(run('subtract','-a',a,'-b',b,'-s').stdout)==['chr1\t0\t2\tA\t0\t+','chr1\t4\t10\tA\t0\t+']


def test_slop_shift_flank_complement(tmp_path):
    g=put(tmp_path,'g','chr1\t20\n'); a=put(tmp_path,'a','chr1\t2\t5\tx\t0\t-\nchr1\t18\t20\ty\t0\t+\n')
    assert lines(run('slop','-i',a,'-g',g,'-b','3').stdout)==['chr1\t0\t8\tx\t0\t-','chr1\t15\t20\ty\t0\t+']
    assert lines(run('shift','-i',a,'-g',g,'-s','5').stdout)==['chr1\t7\t10\tx\t0\t-','chr1\t19\t20\ty\t0\t+']
    assert lines(run('flank','-i',a,'-g',g,'-b','2').stdout)==['chr1\t0\t2\tx\t0\t-','chr1\t5\t7\tx\t0\t-','chr1\t16\t18\ty\t0\t+']
    assert lines(run('complement','-i',a,'-g',g).stdout)==['chr1\t0\t2','chr1\t5\t18']


def test_sort_cluster_spacing_and_windows(tmp_path):
    a=put(tmp_path,'a','chr2\t2\t3\tb\nchr1\t5\t10\tx\nchr1\t5\t7\ty\nchr1\t13\t15\tz\n')
    assert lines(run('sort','-i',a).stdout)==['chr1\t5\t10\tx','chr1\t5\t7\ty','chr1\t13\t15\tz','chr2\t2\t3\tb']
    s=put(tmp_path,'s','chr1\t0\t3\na\nchr1\t2\t5\tb\nchr1\t8\t9\tc\n')
    assert lines(run('cluster','-i',s).stdout)==['chr1\t0\t3\ta\t1','chr1\t2\t5\tb\t1','chr1\t8\t9\tc\t2']
    assert lines(run('spacing','-i',s).stdout)==['chr1\t0\t3\ta\t.','chr1\t2\t5\tb\t-1','chr1\t8\t9\tc\t3']
    g=put(tmp_path,'g','chr1\t10\n')
    assert lines(run('makewindows','-g',g,'-w','4','-s','3','-i','winnum').stdout)==['chr1\t0\t4\t1','chr1\t3\t7\t2','chr1\t6\t10\t3','chr1\t9\t10\t4']


def test_expand_and_groupby(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t2\tA,B\t1,2\ttail\n')
    assert lines(run('expand','-i',a,'-c','5,4').stdout)==['chr1\t0\t2\t1\tA\ttail','chr1\t0\t2\t2\tB\ttail']
    t=put(tmp_path,'t','x\t1\nx\t2\ny\t4\nx\t8\n')
    assert lines(run('groupby','-i',t,'-g','1','-c','2','-o','sum').stdout)==['x\t3','y\t4','x\t8']


def test_multiinter_and_unionbedg(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t4\n'); b=put(tmp_path,'b','chr1\t2\t6\n')
    assert lines(run('multiinter','-i',a,b).stdout)==['chr1\t0\t2\t1\t1\t1\t0','chr1\t2\t4\t2\t1,2\t1\t1','chr1\t4\t6\t1\t2\t0\t1']
    x=put(tmp_path,'x','chr1\t0\t4\tA\n'); y=put(tmp_path,'y','chr1\t2\t6\tB\n')
    assert lines(run('unionbedg','-i',x,y,'-filler','_').stdout)==['chr1\t0\t2\tA\t_','chr1\t2\t4\tA\tB','chr1\t4\t6\t_\tB']


def test_annotate_jaccard_reldist(tmp_path):
    a=put(tmp_path,'a','chr2\t0\t4\tq\nchr1\t0\t4\tp\n')
    b=put(tmp_path,'b','chr1\t1\t3\nx\nchr2\t2\t6\ty\n')
    assert lines(run('annotate','-i',a,'-files',b).stdout)==['chr1\t0\t4\tp\t0.500000','chr2\t0\t4\tq\t0.500000']
    j=run('jaccard','-a',a,'-b',b).stdout.splitlines()
    assert j[0]=='intersection\tunion\tjaccard\tn_intersections' and j[1]=='4\t12\t0.333333\t2'
    d=run('reldist','-a',a,'-b',a,'-detail').stdout.splitlines()
    assert len(d)==2 and all(x.endswith('\t0.000') for x in d)


def test_random_sample_and_summary(tmp_path):
    g=put(tmp_path,'g','chr1\t20\n')
    p=run('random','-g',g,'-l','5','-n','4','-seed','9')
    q=run('random','-g',g,'-l','5','-n','4','-seed','9')
    assert p.returncode==0 and p.stdout==q.stdout and len(lines(p.stdout))==4
    a=put(tmp_path,'a','chr1\t0\t3\nx\nchr1\t5\t9\ty\n')
    assert len(lines(run('sample','-i',a,'-n','2').stdout))==2
    s=run('summary','-i',a,'-g',g).stdout.splitlines()
    assert s[0]=='chrom\tchrom_length\tnum_ivls\ttotal_ivl_bp\tchrom_frac_genome\tfrac_all_ivls\tfrac_all_bp\tmin\tmax\tmean'
    assert s[1].startswith('chr1\t20\t2\t7\t') and s[-1].startswith('all\t20\t2\t7\t1.0\t1.0\t1.0')


def test_getfasta_maskfasta_and_nuc(tmp_path):
    fa=put(tmp_path,'ref.fa','>chr1 description\nACGTACGT\n'); bed=put(tmp_path,'a.bed','chr1\t1\t7\tx\t0\t-\n')
    assert run('getfasta','-fi',fa,'-bed',bed).stdout=='>chr1:1-7\nCGTACG\n'
    out=tmp_path/'masked.fa'
    assert run('maskfasta','-fi',fa,'-bed',bed,'-fo',out).returncode==0
    assert 'ANNNNNNT' in out.read_text()
    n=run('nuc','-fi',fa,'-bed',put(tmp_path,'n.bed','chr1\t0\t4\n'))
    assert n.stdout.splitlines()[0]=='#1_usercol\t2_usercol\t3_usercol\t4_pct_at\t5_pct_gc\t6_num_A\t7_num_C\t8_num_G\t9_num_T\t10_num_N\t11_num_oth\t12_seq_len'
    assert n.stdout.splitlines()[1].endswith('\t0.500000\t0.500000\t1\t1\t1\t1\t0\t0\t4')


def test_bed12_conversion_and_pair_tools(tmp_path):
    bed12=put(tmp_path,'b12','chr1\t10\t30\tn\t7\t-\t10\t30\t0\t2\t5,10\t0,10\n')
    assert lines(run('bed12tobed6','-i',bed12,'-n').stdout)==['chr1\t10\t15\tn\t2\t-','chr1\t20\t30\tn\t1\t-']
    a=put(tmp_path,'pe','chr1\t0\t5\tchr1\t10\t15\tp\t0\t+\t-\n')
    b=put(tmp_path,'b','chr1\t2\t3\tx\t0\t+\n')
    assert lines(run('pairtobed','-a',a,'-b',b).stdout)==[lines(a.read_text())[0]+'\t'+lines(b.read_text())[0]]


def test_window_and_igv_links(tmp_path):
    a=put(tmp_path,'a','chr1\t5\t8\tn\n'); b=put(tmp_path,'b','chr1\t10\t11\nx\n')
    assert lines(run('window','-a',a,'-b',b,'-w','3','-c').stdout)==['chr1\t5\t8\tn\t1']
    assert run('igv','-i',a,'-slop','7').stdout.splitlines()[:2]==['snapshotDirectory ./','goto chr1:-2-15']
    html=run('links','-i',a).stdout
    assert '<h3>BED Entries from: stdin </h3>' in html and 'chr1:6-8' in html


def test_validation_sort_and_iobuf(tmp_path):
    bad=put(tmp_path,'bad','chr1\t-1\t2\n')
    p=run('sort','-i',bad)
    assert p.returncode==1 and p.stdout=='' and 'Unexpected file format.' in p.stderr
    p=run('sort','-i',bad,'-iobuf','2G')
    assert p.returncode==1 and 'Unrecognized parameter: -iobuf' in p.stderr
    p=run('intersect','-a',bad,'-b',bad,'-iobuf','20L')
    assert p.returncode!=0 and "Unrecognized memory buffer size suffix 'L'" in p.stderr


def test_slop_pct_shift_pct_and_flank_strand(tmp_path):
    g=put(tmp_path,'g','chr1\t100\n')
    a=put(tmp_path,'a','chr1\t30\t40\tp\t0\t+\nchr1\t30\t40\tm\t0\t-\n')
    assert lines(run('slop','-i',a,'-g',g,'-l','2','-r','5','-s').stdout)==[
        'chr1\t28\t45\tp\t0\t+','chr1\t25\t42\tm\t0\t-']
    assert lines(run('shift','-i',a,'-g',g,'-s','-0.2','-pct').stdout)==[
        'chr1\t27\t37\tp\t0\t+','chr1\t27\t37\tm\t0\t-']
    assert lines(run('flank','-i',a,'-g',g,'-l','2','-r','5','-s').stdout)==[
        'chr1\t28\t30\tp\t0\t+','chr1\t40\t45\tp\t0\t+',
        'chr1\t25\t30\tm\t0\t-','chr1\t40\t42\tm\t0\t-']


def test_makewindows_count_reverse_and_summary_empty_chrom(tmp_path):
    g=put(tmp_path,'g','chr1\t10\nchr2\t2\n')
    p=run('makewindows','-g',g,'-n','3','-i','winnum','-reverse')
    assert lines(p.stdout)==['chr1\t0\t3\t3','chr1\t3\t6\t2','chr1\t6\t10\t1']
    assert 'smaller than the number of windows requested' in p.stderr
    a=put(tmp_path,'a','chr1\t0\t2\n')
    assert lines(run('summary','-i',a,'-g',g).stdout)[2].startswith('chr2\t2\t0\t0\t')


def test_complement_clip_and_stranded_merge(tmp_path):
    g=put(tmp_path,'g','chr1\t10\nchr2\t5\n')
    a=put(tmp_path,'a','chr1\t-ignored\t0\n')
    # Normal complement includes entire uncovered chromosomes and preserves genome order.
    a=put(tmp_path,'valid','chr1\t2\t6\n')
    assert lines(run('complement','-i',a,'-g',g).stdout)==['chr1\t0\t2','chr1\t6\t10','chr2\t0\t5']
    s=put(tmp_path,'s','chr1\t0\t4\ta\t0\t+\nchr1\t2\t6\tb\t0\t-\nchr1\t3\t5\tc\t0\t*\n')
    assert lines(run('merge','-i',s,'-s').stdout)==['chr1\t0\t4','chr1\t2\t6']


def test_sample_validation_and_expand_single_column(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t1\tA,B\ttail\n')
    assert lines(run('expand','-i',a,'-c','4').stdout)==['chr1\t0\t1\tA\ttail','chr1\t0\t1\tB\ttail']
    p=run('sample','-i',a,'-n','2')
    assert p.returncode!=0 and 'fewer records than the requested number' in p.stderr


def test_pair_modes_and_window_filters(tmp_path):
    pe=put(tmp_path,'pe','chr1\t0\t5\tchr1\t10\t15\tp\t0\t+\t-\n')
    b=put(tmp_path,'b','chr1\t2\t3\tx\t0\t+\n')
    assert lines(run('pairtobed','-a',pe,'-b',b,'-type','either').stdout)==[pe.read_text().rstrip()+'\t'+b.read_text().rstrip()]
    assert lines(run('pairtobed','-a',pe,'-b',b,'-type','neither').stdout)==[]
    a=put(tmp_path,'a','chr1\t0\t2\ta\nchr1\t20\t22\tb\n')
    assert lines(run('window','-a',a,'-b',b,'-w','3','-v').stdout)==['chr1\t20\t22\tb']
    assert lines(run('window','-a',a,'-b',b,'-w','3','-u').stdout)==['chr1\t0\t2\ta']


def test_igv_option_validation_and_links_custom_base(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t2\tn\t0\t+\n')
    p=run('igv','-i',a,'-sort','bogus')
    assert p.returncode!=0 and 'Invalid sort option' in p.stderr
    html=run('links','-i',a,'-base','https://example.test/view?x=1').stdout
    assert 'https://example.test/view?x=1&position=chr1:0-2' in html


def test_shuffle_seed_and_chrom_constraint(tmp_path):
    g=put(tmp_path,'g','chr1\t20\nchr2\t15\n')
    a=put(tmp_path,'a','chr1\t2\t5\tn\t7\t+\nchr2\t3\t8\tm\t8\t-\n')
    p=run('shuffle','-i',a,'-g',g,'-seed','42')
    q=run('shuffle','-i',a,'-g',g,'-seed','42')
    assert p.returncode==0 and p.stdout==q.stdout
    rows=[x.split('\t') for x in lines(p.stdout)]
    assert len(rows)==2
    assert all(int(r[2])-int(r[1])==length for r,length in zip(rows,(3,5)))
    c=run('shuffle','-i',a,'-g',g,'-chrom','-seed','42')
    assert [r.split('\t')[0] for r in lines(c.stdout)]==['chr1','chr2']


def test_split_simple_creates_named_parts(tmp_path):
    a=put(tmp_path,'a',''.join(f'chr1\t{i}\t{i+1}\tr{i}\n' for i in range(5)))
    prefix=tmp_path/'part'
    p=run('split','-i',a,'-p',prefix,'-n','2','-a','simple')
    assert p.returncode==0
    assert (tmp_path/'part.00001.bed').read_text()=='chr1\t0\t1\tr0\nchr1\t2\t3\tr2\nchr1\t4\t5\tr4\n'
    assert (tmp_path/'part.00002.bed').read_text()=='chr1\t1\t2\tr1\nchr1\t3\t4\tr3\n'


def test_fisher_report_dimensions(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t2\nchr1\t3\t5\n')
    b=put(tmp_path,'b','chr1\t1\t4\nchr1\t4\t6\n')
    g=put(tmp_path,'g','chr1\t10\n')
    p=run('fisher','-a',a,'-b',b,'-g',g)
    assert p.returncode==0
    assert '# Number of query intervals: 2' in p.stdout
    assert '# Number of db intervals: 2' in p.stdout
    assert '# Number of overlaps: 3' in p.stdout
    assert '# Number of possible intervals (estimated):' in p.stdout
    assert p.stdout.rstrip().splitlines()[-2]=='left\tright\ttwo-tail\tratio'


def test_annotation_counts_both_and_headers(tmp_path):
    a=put(tmp_path,'a','chr1\t0\t10\tx\t0\t+\n')
    b=put(tmp_path,'b','chr1\t1\t5\tb1\t0\t+\nchr1\t3\t8\tb2\t0\t-\n')
    assert lines(run('annotate','-i',a,'-files',b,'-counts').stdout)==['chr1\t0\t10\tx\t0\t+\t2']
    assert lines(run('annotate','-i',a,'-files',b,'-both','-names','ann').stdout)==[
        '#\t\t\t\t\t\tann_cnt\tann_pct','chr1\t0\t10\tx\t0\t+\t2\t0.700000']
    assert lines(run('annotate','-i',a,'-files',b,'-s').stdout)[0].endswith('\t0.400000')


def test_gff_vcf_geometry_and_original_record_preservation(tmp_path):
    gff=put(tmp_path,'x.gff','chr1\tsrc\tgene\t3\t8\t.\t+\t.\tID=g\n')
    bed=put(tmp_path,'b','chr1\t4\t6\n')
    assert run('intersect','-a',gff,'-b',bed).stdout=='chr1\tsrc\tgene\t5\t6\t.\t+\t.\tID=g\n'
    assert run('intersect','-a',gff,'-b',bed,'-wa').stdout==gff.read_text()
    vcf=put(tmp_path,'x.vcf','##fileformat=VCFv4.2\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\nchr1\t6\tv\tAAAA\tT\t.\t.\t.\n')
    vb=put(tmp_path,'vb','chr1\t7\t12\n')
    assert run('intersect','-a',vcf,'-b',vb).stdout=='chr1\t6\tv\tAAAA\tT\t.\t.\t.\n'
    # VCF intervals are interpreted from REF span while original VCF fields survive output.
    vbed=put(tmp_path,'vbed','chr1\t7\t8\n')
    assert lines(run('merge','-i',vbed).stdout)==['chr1\t7\t8']


def test_gzip_inputs_and_large_coordinates(tmp_path):
    raw='chr1\t800\t830\nchr1\t9000000000\t9000000003\n'
    gz=tmp_path/'a.bed.gz'
    with gzip.open(gz,'wt') as f:
        f.write(raw)
    assert lines(run('merge','-i',gz).stdout)==['chr1\t800\t830','chr1\t9000000000\t9000000003']
    sci=put(tmp_path,'sci','chr1\t8e02\t830\n')
    assert lines(run('merge','-i',sci).stdout)==['chr1\t800\t830']
    p=run('sort','-i',put(tmp_path,'exp','chr1\t1e10\t10000000001\n'))
    assert p.returncode!=0 and p.stdout=='' and 'Unexpected file format.' in p.stderr
