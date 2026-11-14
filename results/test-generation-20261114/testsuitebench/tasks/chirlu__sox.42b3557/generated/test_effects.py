import struct
import wave

def test_trim_reverse_repeat_and_pad_frame_counts(run, raw16, tmp_path):
    src=raw16('in.raw',[10,20,30,40,50,60])
    base=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src)]
    for eff, expected in [(['trim','2s','3s'],3),(['reverse'],6),(['repeat','1'],12),(['pad','2s'],8)]:
        out=tmp_path/(eff[0]+'.raw')
        r=run([*base,'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),*eff])
        assert r.returncode == 0 and out.stat().st_size == expected*2, eff
    rev=tmp_path/'reverse.raw'
    assert struct.unpack('<6h',rev.read_bytes()) == (60,50,40,30,20,10)

def test_channel_conversion_swap_and_oops(run, tmp_path):
    src=tmp_path/'stereo.raw'; src.write_bytes(struct.pack('<4h',1000,200,-1000,500))
    inp=['-t','raw','-r','8000','-c','2','-b','16','-e','signed-integer',str(src)]
    swapped=tmp_path/'swap.raw'
    r=run([*inp,'-t','raw','-r','8000','-c','2','-b','16','-e','signed-integer',str(swapped),'swap'])
    assert r.returncode == 0 and struct.unpack('<4h',swapped.read_bytes()) == (200,1000,500,-1000)
    oops=tmp_path/'oops.raw'
    r=run([*inp,'-t','raw','-r','8000','-c','2','-b','16','-e','signed-integer',str(oops),'oops'])
    assert r.returncode == 0 and struct.unpack('<4h',oops.read_bytes()) == (800,800,-1500,-1500)
    mono=tmp_path/'mono.raw'
    r=run([*inp,'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(mono),'channels','1'])
    assert r.returncode == 0 and len(mono.read_bytes()) == 4

def test_downsample_upsample_metadata(run, raw16, tmp_path):
    src=raw16('in.raw',list(range(20)))
    inp=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src)]
    for effect, count, rate in [('downsample',10,4000),('upsample',40,16000)]:
        out=tmp_path/(effect+'.wav')
        r=run([*inp,str(out),effect])
        assert r.returncode == 0
        with wave.open(str(out),'rb') as w:
            assert w.getnframes()==count and w.getframerate()==rate

def test_filter_changes_signal_and_preserves_metadata(run, tmp_path):
    src=tmp_path/'tone.wav'
    # deterministic square wave with strong high-frequency component
    import math
    samples=[int(20000*math.sin(2*math.pi*1500*i/8000)) for i in range(800)]
    with wave.open(str(src),'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(8000); w.writeframes(struct.pack('<%dh'%len(samples),*samples))
    out=tmp_path/'filtered.wav'
    r=run([str(src),str(out),'lowpass','500'])
    assert r.returncode==0
    with wave.open(str(out),'rb') as w:
        assert (w.getnframes(),w.getframerate())==(800,8000)
        data=w.readframes(800)
    assert data != src.read_bytes()[44:]

def test_stats_and_stat_are_analysis_on_stderr(run, make_wav, tmp_path):
    src=make_wav('input.wav',[0,1000,-1000,2000],rate=8000)
    for eff, word in [('stat',b'Samples read'),('stats',b'RMS')] :
        r=run([str(src),'-n',eff])
        assert r.returncode==0 and word in r.stderr and not r.stdout

def test_effects_file_chains_have_separate_lines(run, raw16, tmp_path):
    src=raw16('source.raw',[1000]*800)
    inp=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src)]
    script=tmp_path/'effects.txt'; script.write_text('trim 0.01 0.02\ngain -6\n')
    separate=tmp_path/'separate.raw'
    r=run(['--effects-file',str(script),*inp,'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(separate)])
    assert r.returncode==0 and separate.stat().st_size==720*2
    script.write_text('trim 0.01 0.02 gain -6\n')
    same=tmp_path/'same.raw'
    r=run(['--effects-file',str(script),*inp,'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(same)])
    assert r.returncode==0 and same.stat().st_size==160*2

def test_volume_and_gain_are_per_sample(run, raw16, tmp_path):
    src=raw16('source.raw',[1000,-2000,3000])
    inp=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src)]
    out=tmp_path/'gain.raw'
    r=run([*inp,'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),'gain','-6.020599913'])
    assert r.returncode==0
    vals=struct.unpack('<3h',out.read_bytes())
    assert all(abs(a-b/2)<=2 for a,b in zip(vals,[1000,-2000,3000]))

def test_downsample_bad_factor_and_filter_missing_arguments_fail(run, raw16, tmp_path):
    src=raw16('in.raw',[1,2,3,4])
    inp=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src),str(tmp_path/'out.raw')]
    for effect in (['downsample','0'],['upsample','257'],['highpass'],['lowpass','-1']):
        assert run([*inp,*effect]).returncode != 0
