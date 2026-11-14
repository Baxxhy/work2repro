import os
import signal
import struct

def test_invalid_raw_seven_bit_warns_and_succeeds(run, tmp_path):
    p=tmp_path/'out.raw'
    r=run(['-n','-t','raw','-r','8000','-c','1','-b','7','-e','signed-integer',str(p),'synth','0.001','sine','440'])
    assert r.returncode==0
    assert b"raw can't encode Signed Integer PCM to 7-bit" in r.stderr

def test_sox_opts_supplies_no_dither(run, tmp_path):
    p=tmp_path/'out.raw'
    r=run(['-n','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(p),'synth','0.01','sine','440'],env={'SOX_OPTS':'-D -R'})
    assert r.returncode==0 and p.stat().st_size==160

def test_guarded_explicit_gain_does_not_hide_clipping(run, raw16, tmp_path, exe):
    src=raw16('source.raw',[20000,-20000,10000]); out=tmp_path/'out.raw'
    args=['-R','-D','-G','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src),'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),'gain','20']
    r=run(args)
    assert r.returncode==0
    assert struct.unpack('<3h',out.read_bytes())==(32767,-32767,32767)
    assert f'{exe} WARN gain: gain clipped 3 samples; decrease volume?'.encode() in r.stderr

def test_global_norm_reference_crash_cases(run, raw16, tmp_path):
    # These two process failures are explicitly part of the 14.4.2 contract.
    r=run(['--norm','-n',str(tmp_path/'null.raw'),'synth','0.1','sine','440','vol','3'])
    assert r.returncode == -signal.SIGSEGV
    assert not r.stdout and not r.stderr
    inp=raw16('two.raw',[1,-1]); out=tmp_path/'out.raw'
    r=run(['-R','-D','--norm','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(inp),'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),'gain','20'])
    assert r.returncode == -signal.SIGSEGV
    assert not r.stdout and not r.stderr

def test_input_ignore_length_option_acceptance_and_bad_volume_error(run, tmp_path):
    r=run(['-v','not-a-number','-n',str(tmp_path/'out.wav'),'synth','0.01','sine','440'])
    assert r.returncode!=0
    assert b'volume' in r.stderr.lower() or b'numeric' in r.stderr.lower()
