import struct
import wave

def raw_input(tmp_path, name, values, rate=8000):
    p=tmp_path/name
    p.write_bytes(struct.pack('<%dh'%len(values),*values))
    return p

def test_concatenate_mix_multiply_and_per_input_volume(run, tmp_path):
    a=raw_input(tmp_path,'a.raw',[1000,2000,3000,4000])
    b=raw_input(tmp_path,'b.raw',[500,-500])
    fmt=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer']
    out=tmp_path/'concat.raw'
    r=run(['--combine','concatenate',*fmt,str(a),*fmt,str(b),*fmt,str(out)])
    assert r.returncode==0
    assert struct.unpack('<6h',out.read_bytes())==(1000,2000,3000,4000,500,-500)
    mix=tmp_path/'mix.raw'
    r=run(['-m',*fmt,str(a),'-v','0.5',*fmt,str(b),*fmt,str(mix)])
    assert r.returncode==0 and len(mix.read_bytes())==8
    vals=struct.unpack('<4h',mix.read_bytes())
    assert vals[0] != 1000 and vals[2] != 3000
    mul=tmp_path/'mul.raw'
    r=run(['-T',*fmt,str(a),*fmt,str(b),*fmt,str(mul)])
    assert r.returncode==0 and len(mul.read_bytes())==8

def test_incompatible_input_rates_fail(run, tmp_path):
    a=raw_input(tmp_path,'a.raw',[1,2,3])
    b=raw_input(tmp_path,'b.raw',[1,2,3])
    fmt=['-t','raw','-c','1','-b','16','-e','signed-integer']
    r=run(['-r','8000',*fmt,str(a),'-r','16000',*fmt,str(b),str(tmp_path/'out.wav')])
    assert r.returncode != 0

def test_stdin_stdout_wav_stream_pipeline(run, make_wav, tmp_path):
    source=make_wav('pipe.wav',[0,100,-100,300],rate=8000)
    read=subprocess_bytes=source.read_bytes()
    first=run(['-t','wav','-','-t','wav','-'],input_bytes=read)
    assert first.returncode==0
    # Ensure emitted stdout is a valid headered WAV by querying through stdin.
    info=run(['--info','-s','-'],input_bytes=first.stdout)
    assert info.returncode==0 and info.stdout.strip()==b'4'

def test_no_clobber_does_not_silently_replace(run, tmp_path):
    src=raw_input(tmp_path,'src.raw',[10,20])
    out=tmp_path/'existing.raw'; out.write_bytes(b'preserve-me')
    fmt=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer']
    r=run(['--no-clobber',*fmt,str(src),*fmt,str(out)])
    assert r.returncode != 0 or out.read_bytes()==b'preserve-me'

def test_clobber_replaces_existing_output(run, tmp_path):
    src=raw_input(tmp_path,'src.raw',[10,20])
    out=tmp_path/'existing.raw'; out.write_bytes(b'old')
    fmt=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer']
    r=run(['--clobber',*fmt,str(src),*fmt,str(out)])
    assert r.returncode==0 and out.read_bytes()==src.read_bytes()

def test_plot_mode_scripts_and_status(run, tmp_path):
    src=raw_input(tmp_path,'in.raw',[0]*16)
    fmt=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src)]
    for mode, marker in [('gnuplot',b'plot'),('octave',b'freqz')]:
        r=run(['--plot',mode,*fmt,'-n','lowpass','1000'])
        assert r.returncode==2 and marker.lower() in r.stdout.lower() and not r.stderr

def test_quiet_mode_keeps_fatal_error(run, tmp_path):
    p=tmp_path/'missing.wav'
    r=run(['-q',str(p),str(tmp_path/'out.wav')])
    assert r.returncode!=0 and b'FAIL' in r.stderr and str(p).encode() in r.stderr

def test_verbose_reports_io_and_effect_chain(run, make_wav, tmp_path):
    src=make_wav('in.wav',[0,1000,-1000],rate=8000)
    out=tmp_path/'out.wav'
    r=run(['-V3',str(src),str(out),'gain','-3'])
    assert r.returncode==0
    for word in (b'Input',b'Output',b'gain'):
        assert word.lower() in r.stderr.lower()

def test_synth_default_waveform_matches_sine(run, tmp_path):
    outputs=[]
    for spelling in ([],['sine']):
        p=tmp_path/('synth'+str(len(outputs))+'.raw')
        r=run(['-R','-D','-n','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(p),'synth','0.01',*spelling,'440'])
        assert r.returncode==0
        outputs.append(p.read_bytes())
    assert outputs[0]==outputs[1] and len(outputs[0])==160

def test_effect_boundaries_and_invalid_options(run, tmp_path):
    # Null input has the specified 48 kHz mono defaults.
    valid=run(['-n','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(tmp_path/'ok.raw'),'synth','0.01','sine','440','lowpass','4000'])
    assert valid.returncode==0 and (tmp_path/'ok.raw').stat().st_size==160
    for chain in (['tempo','0'],['speed','-1'],['pitch'],['fade'],['tremolo'],['chorus'],['delay','-1']):
        r=run(['-n','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(tmp_path/'bad.raw'),*chain])
        assert r.returncode!=0, chain
