import os
import signal
import struct
import subprocess
from pathlib import Path

FORMATS = '8svx aif aifc aiff aiffc al amb au avr cdda cdr cvs cvsd cvu dat dvms f32 f4 f64 f8 fssd gsrt hcom htk ima ircam la lpc lpc10 lu maud nist prc raw s1 s16 s2 s24 s3 s32 s4 s8 sb sf sl sln smp snd sndr sndt sou sox sph sw txw u1 u16 u2 u24 u3 u32 u4 u8 ub ul uw vms voc vox wav wavpcm wve xa'
EFFECTS = 'allpass band bandpass bandreject bass bend biquad chorus channels compand contrast dcshift deemph delay dither divide+ downsample earwax echo echos equalizer fade fir firfit+ flanger gain highpass hilbert input# ladspa loudness lowpass mcompand noiseprof noisered norm oops output# overdrive pad phaser pitch rate remix repeat reverb reverse riaa silence sinc speed splice stat stats stretch swap synth tempo treble tremolo trim upsample vad vol'

def test_version_and_help_inventory(run, exe):
    r = run(['--version'])
    assert r.returncode == 0
    assert r.stdout == f'{exe}:      SoX v14.4.2\n'.encode()
    h = run(['--help'])
    assert h.returncode == 0
    assert h.stdout.startswith(f'{exe}:      SoX v14.4.2\n'.encode())
    for section in (b'SPECIAL FILENAMES', b'GLOBAL OPTIONS', b'FORMAT OPTIONS', b'AUDIO FILE FORMATS', b'EFFECTS'):
        assert section in h.stdout
    assert FORMATS.encode() in h.stdout and EFFECTS.encode() in h.stdout
    assert b'8192' in h.stdout and b'DFT' in h.stdout and b'10' in h.stdout

def test_effect_help_valid_names_returns_one_and_documents_gain(run):
    r = run(['--help-effect', 'gain'])
    assert r.returncode == 1
    for fragment in (b'gain [-e|-b|-B|-r]', b'Equalise channels', b'Balance channels', b'gain-dB'):
        assert fragment in r.stdout

def test_effect_help_all_is_substantial(run):
    r = run(['--help-effect', 'all'])
    assert r.returncode == 1 and len(r.stdout) > 250
    assert all(x in r.stdout for x in (b'gain', b'reverb', b'echo'))

def test_format_help_all_and_xa(run):
    all_help = run(['--help-format', 'all'])
    assert all_help.returncode == 1 and len(all_help.stdout) > 2000
    for x in (b'WAV', b'AIFF', b'AU'):
        assert x in all_help.stdout
    xa = run(['--help-format', 'xa'])
    assert xa.returncode == 1 and b'Maxis' in xa.stdout and b'Reads: yes' in xa.stdout

def test_unknown_help_names_list_valid_inventory(run):
    for kind, arg, expected in [('--help-effect', 'no-such-effect', b'EFFECTS:'), ('--help-format', 'no-such-format', b'AUDIO FILE FORMATS:')]:
        r = run([kind, arg])
        assert r.returncode != 0 and expected in r.stdout + r.stderr

def test_no_input_and_missing_input_diagnostics(run, tmp_path):
    r = run([])
    assert r.returncode != 0 and b'No input filenames specified' in r.stderr
    missing = tmp_path / 'absent.wav'
    r = run([str(missing), str(tmp_path/'out.wav')])
    assert r.returncode != 0 and b"can't open input file" in r.stderr and str(missing).encode() in r.stderr

def test_invalid_global_options_and_format_parameters_fail(run, tmp_path):
    cases = [(['--buffer'], 'buffer'), (['--buffer','abc'], 'buffer'), (['--buffer','15'], 'buffer'),
             (['-r','0'], 'rate'), (['-c','0'], 'channel'), (['-t','bogus'], 'format'),
             (['-e','nonesuch'], 'encoding')]
    for prefix, clue in cases:
        r = run([*prefix, '-n', str(tmp_path/'out.raw'), 'synth', '0.01', 'sine', '440'])
        assert r.returncode != 0, prefix

def test_last_file_selector_wins(run, tmp_path):
    out = tmp_path/'out.raw'
    r = run(['-t','bogus','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer','-n',str(out),'synth','0.01','sine','440'])
    assert r.returncode == 0 and out.stat().st_size == 160

def test_raw_synthesis_lengths_and_encoding_sizes(run, tmp_path):
    for bits, size in [(8,80),(16,160),(32,320)]:
        p=tmp_path/f'{bits}.raw'
        r=run(['-R','-D','-n','-t','raw','-r','8000','-c','1','-b',str(bits),'-e','signed-integer',str(p),'synth','0.01','sine','440'])
        assert r.returncode == 0 and p.stat().st_size == size
    p=tmp_path/'441.raw'
    assert run(['-n','-t','raw','-r','44100','-c','1','-b','8','-e','unsigned-integer',str(p),'synth','0.01','sine','440']).returncode == 0
    assert p.stat().st_size == 441

def test_raw_input_gain_saturates_and_warns(run, raw16, tmp_path, exe):
    inp=raw16('in.raw',[20000,-20000,10000])
    out=tmp_path/'out.raw'
    r=run(['-R','-D','-G','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(inp),'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),'gain','20'])
    assert r.returncode == 0
    assert struct.unpack('<3h',out.read_bytes()) == (32767,-32767,32767)
    assert f'{exe} WARN gain: gain clipped 3 samples; decrease volume?'.encode() in r.stderr

def test_sox_options_buffer_and_effects_file(run, tmp_path):
    src=tmp_path/'src.raw'; src.write_bytes(bytes(800))
    base=['-t','raw','-r','8000','-c','1','-b','8','-e','unsigned-integer',str(src)]
    for size in ('1024','4096','16384'):
        out=tmp_path/f'b{size}.raw'
        r=run(['--buffer',size,*base,'-t','raw','-r','8000','-c','1','-b','8','-e','unsigned-integer',str(out),'gain','0'])
        assert r.returncode == 0 and out.read_bytes() == src.read_bytes()
    missing=run(['--effects-file',str(tmp_path/'missing'),*base,str(tmp_path/'x.raw')])
    assert missing.returncode != 0

def test_invalid_and_unknown_effect_fail(run, tmp_path):
    out=tmp_path/'x.raw'
    for effect in (['not-an-effect'], ['trim'], ['lowpass'], ['downsample','0']):
        r=run(['-n','-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out),*effect])
        assert r.returncode != 0, effect
