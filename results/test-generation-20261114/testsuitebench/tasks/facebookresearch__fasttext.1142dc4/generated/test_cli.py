import os, struct, subprocess
from pathlib import Path
import pytest

EVAL = Path(__file__).resolve().parent
EXE = Path('/workspace/executable') if Path('/workspace/executable').exists() else EVAL.parent / 'executable'

def run(*args, input=None, cwd=None):
    return subprocess.run([str(EXE), *map(str,args)], input=input, text=True, capture_output=True, cwd=cwd, timeout=45)

def native(path):
    b=bytearray()
    i=lambda x: struct.pack('<i',x)
    q=lambda x: struct.pack('<q',x)
    f=lambda x: struct.pack('<f',x)
    b += i(793712314)+i(12)
    # args
    b += b''.join(i(x) for x in (2,5,5,1,5,1,3,3,0,0,0,100)) + struct.pack('<d',0.0001)
    entries=[('apple',20,0),('banana',10,0),('</s>',4,0),('__label__pos',2,1),('__label__neg',2,1)]
    b += i(5)+i(3)+i(2)+q(38)+q(-1)
    for w,c,t in entries: b += w.encode()+b'\0'+q(c)+bytes([t])
    b += b'\0' # input not quantized
    b += q(3)+q(2)+b''.join(f(x) for x in (2,0,-2,0,0,0))
    b += b'\0' # output not quantized
    b += q(2)+q(2)+b''.join(f(x) for x in (2,0,-2,0))
    path.write_bytes(b)

@pytest.fixture
def env(tmp_path):
    d=tmp_path
    model=d/'native.bin'; native(model)
    return d,model

def test_no_command_usage():
    r=run(); assert r.returncode != 0 and not r.stdout
    assert r.stderr.startswith('usage: fasttext <command> <args>')
    assert '  supervised              train a supervised classifier' in r.stderr

def test_unknown_command_usage():
    r=run('wat'); assert r.returncode != 0 and not r.stdout and 'usage: fasttext <command> <args>' in r.stderr

def test_nn_and_analogies_noargs_usage():
    for cmd in ('nn','analogies'):
        r=run(cmd); assert r.returncode == 1 and not r.stderr
        assert r.stdout.startswith(f'usage: fasttext {cmd} <model> <k>')
        assert '(optional; 10 by default)' in r.stdout and r.stdout.endswith('\n\n')

def test_training_missing_paths_help():
    r=run('supervised'); assert r.returncode != 0 and not r.stdout
    assert r.stderr.startswith('Empty input or output path.\n\nThe following arguments are mandatory:')
    for opt in ('-input','-output','-dim','-loss','-autotune-duration','-qout','[100]','[softmax]'): assert opt in r.stderr

def test_flag_parser_failures(tmp_path):
    src=tmp_path/'in'; src.write_text('__label__a hello\n')
    for args, phrase in [(('supervised','-input',src,'-output'), 'missing an argument'), (('supervised',str(src)), 'Provided argument without a dash'), (('supervised','-bogus','x'), 'Unknown argument: -bogus')]:
        r=run(*args); assert r.returncode != 0 and phrase in r.stderr

def test_dump_invalid_usage(env):
    _,m=env
    for args in (('dump',m),('dump',m,'wat')):
        r=run(*args); assert r.returncode == 1 and not r.stderr
        assert r.stdout.startswith('usage: fasttext dump') and r.stdout.endswith('option from args,dict,input,output\n')

def test_required_usages(env):
    _,m=env
    for cmd in ('test','test-label','predict','predict-prob','print-word-vectors','print-sentence-vectors','print-ngrams'):
        r=run(cmd,m) if cmd in ('test','test-label','predict','predict-prob','print-ngrams') else run(cmd)
        assert r.returncode != 0 and r.stderr.startswith('usage: fasttext '+cmd)

def test_native_dump_and_dict(env):
    _,m=env
    r=run('dump',m,'args'); assert r.returncode==0
    assert 'dim 2\n' in r.stdout and 'loss softmax\n' in r.stdout and 'model sup\n' in r.stdout
    d=run('dump',m,'dict'); lines=d.stdout.splitlines()
    assert int(lines[0])==5 and len(lines)==6
    assert 'apple 20 word' in lines and '__label__pos 2 label' in lines

def test_native_predictions_threshold_k_and_stdin(env):
    _,m=env
    r=run('predict',m,'-',input='apple\nbanana\n'); assert r.returncode==0
    assert r.stdout.splitlines()==['__label__pos','__label__neg']
    r=run('predict-prob',m,'-',2,0,input='apple\n')
    assert r.returncode==0 and r.stdout.startswith('__label__pos ') and '__label__neg ' in r.stdout
    assert run('predict',m,'-',input='').stdout==''

def test_prediction_file_failures(env):
    d,m=env; r=run('predict',m,d/'absent')
    assert r.returncode!=0 and r.stdout=='' and r.stderr=='Input file cannot be opened!\n'

def test_model_format_errors(tmp_path):
    empty=tmp_path/'empty'; empty.write_bytes(b'')
    r=run('predict',empty,'-',input='apple\n')
    assert r.returncode!=0 and not r.stdout and f'{empty} has wrong file format!' in r.stderr
    absent=tmp_path/'missing.bin'; r=run('dump',absent,'args')
    assert r.returncode!=0 and f'{absent} cannot be opened for loading!' in r.stderr

def test_native_vector_queries(env):
    _,m=env
    r=run('print-word-vectors',m,input='apple mystery\n')
    assert r.returncode==0
    rows=r.stdout.splitlines(); assert len(rows)==2
    assert rows[0].startswith('apple ') and len(rows[0].split())==3
    assert rows[1]=='mystery 0 0 0 '

def test_native_test_metrics(env):
    d,m=env; data=d/'eval.txt'; data.write_text('__label__pos apple\n')
    r=run('test',m,data)
    assert r.returncode==0 and r.stdout.startswith('N\t1\nP@1\t') and '\nR@1\t' in r.stdout
    absent=d/'absent-label'; absent.write_text('__label__other apple\n')
    r=run('test',m,absent); assert r.stdout=='N\t0\nP@1\tnan\nR@1\tnan\n'

def test_test_stdin_native_limitation(env):
    _,m=env; r=run('test',m,'-',input='__label__pos apple\n')
    assert r.returncode==0 and r.stdout=='N\t0\nP@1\tnan\nR@1\tnan\n'

def test_test_label_reports_all_labels(env):
    d,m=env; data=d/'one'; data.write_text('__label__pos apple\n')
    r=run('test-label',m,data,2)
    assert r.returncode==0 and '__label__pos' in r.stdout and '__label__neg' in r.stdout
    assert 'P@2\t' in r.stdout and 'R@2\t' in r.stdout

def train(tmp_path, mode='supervised', corpus='__label__a alpha\n__label__b beta\n', extra=()):
    src=tmp_path/'train.txt'; src.write_text(corpus)
    out=tmp_path/'model'
    r=run(mode,'-input',src,'-output',out,'-epoch',0,'-dim',5,'-bucket',100,'-minCount',1,'-thread',1,'-verbose',0,*extra)
    return r,out,src

def test_epoch_zero_training_artifacts_and_dump(tmp_path):
    r,out,_=train(tmp_path,extra=('-saveOutput',))
    assert r.returncode==0, r.stderr
    assert out.with_suffix('.bin').stat().st_size>0 and out.with_suffix('.vec').stat().st_size>0
    assert out.with_suffix('.bin').read_bytes()[:8]==struct.pack('<ii',793712314,12)
    header=out.with_suffix('.vec').read_text().splitlines()[0]
    w,d=map(int,header.split()); assert d==5 and w==len(out.with_suffix('.vec').read_text().splitlines())-1
    assert out.with_suffix('.output').read_text().splitlines()[0]=='2 5'
    assert 'model sup' in run('dump',out.with_suffix('.bin'),'args').stdout

def test_unsupervised_model_types(tmp_path):
    for mode, expected in [('skipgram','model sg'),('cbow','model cbow')]:
        sub=tmp_path/mode; sub.mkdir()
        r,out,_=train(sub,mode, 'alpha beta\n'*6, ('-minn','0','-maxn','0'))
        assert r.returncode==0, r.stderr
        assert expected in run('dump',out.with_suffix('.bin'),'args').stdout

def test_unicode_and_custom_label_prefix(tmp_path):
    r,out,_=train(tmp_path,corpus='__class__good café 😀\n__class__bad tea\n',extra=('-label','__class__'))
    assert r.returncode==0, r.stderr
    dictout=run('dump',out.with_suffix('.bin'),'dict').stdout
    assert 'café' in dictout and '😀' in dictout and '__class__good' in dictout

def test_exact_empty_vocabulary_failure(tmp_path):
    src=tmp_path/'empty'; src.write_text('')
    out=tmp_path/'bad'
    r=run('skipgram','-input',src,'-output',out,'-epoch',0,'-dim',5,'-bucket',10,'-minn',0,'-maxn',0,'-thread',1,'-verbose',0)
    assert r.returncode==-6 and r.stdout==''
    assert r.stderr=="terminate called after throwing an instance of 'std::invalid_argument'\n  what():  Empty vocabulary. Try a smaller -minCount value.\n"
    assert out.with_suffix('.bin').exists() and out.with_suffix('.bin').stat().st_size==0
    assert not out.with_suffix('.vec').exists()

def test_native_nn_prompt_and_negative_k(env):
    _,m=env
    r=run('nn',m,-2,input='apple\n')
    assert r.returncode==0 and r.stdout.startswith('Query word? ')
    assert 'banana ' in r.stdout and 'Query word? ' in r.stdout[12:]

def test_native_nn_zero_k_native_crash(env):
    _,m=env; r=run('nn',m,0,input='apple\n')
    assert r.returncode==-11 and r.stdout=='Query word? ' and r.stderr==''

def test_sentence_vector_lines(env):
    _,m=env
    r=run('print-sentence-vectors',m,input='apple banana\n\n')
    assert r.returncode==0
    lines=r.stdout.splitlines(); assert len(lines)==2
    assert all(len(x.split())==2 for x in lines)
    assert all(float(v)==0 for v in lines[1].split())

def test_training_subwords_increase_binary_size(tmp_path):
    sizes=[]
    for name, bounds in [('plain',('0','0')),('sub',('2','4'))]:
        d=tmp_path/name; d.mkdir()
        r,out,_=train(d,'skipgram','king queen running walked\n'*5,('-minn',bounds[0],'-maxn',bounds[1]))
        assert r.returncode==0, r.stderr
        sizes.append(out.with_suffix('.bin').stat().st_size)
    assert sizes[1]>sizes[0]

def test_pretrained_vectors_and_dimension_validation(tmp_path):
    corpus=tmp_path/'train'; corpus.write_text('__label__a alpha\n__label__b beta\n')
    vec=tmp_path/'pre.vec'; vec.write_text('2 5\nalpha 1 2 3 4 5\nbeta 5 4 3 2 1\n')
    out=tmp_path/'pre'; r=run('supervised','-input',corpus,'-output',out,'-epoch',0,'-dim',5,'-bucket',10,'-thread',1,'-verbose',0,'-pretrainedVectors',vec)
    assert r.returncode==0, r.stderr
    bad=tmp_path/'bad'; r=run('supervised','-input',corpus,'-output',bad,'-epoch',0,'-dim',8,'-pretrainedVectors',vec,'-verbose',0)
    assert r.returncode!=0 and not bad.with_suffix('.vec').exists()

def test_exact_small_softmax_abort(tmp_path):
    src=tmp_path/'tiny'; src.write_text('__label__a alpha alpha\n__label__b beta beta\n'*3)
    out=tmp_path/'tiny-model'
    r=run('supervised','-input',src,'-output',out,'-dim',5,'-epoch',3,'-thread',1,'-bucket',20,'-verbose',0)
    assert r.returncode==-6 and r.stdout==''
    assert r.stderr=="terminate called after throwing an instance of 'fasttext::DenseMatrix::EncounteredNaNError'\n  what():  Encountered NaN.\n"
    assert out.with_suffix('.bin').exists() and out.with_suffix('.bin').stat().st_size==0
    assert not out.with_suffix('.vec').exists()
