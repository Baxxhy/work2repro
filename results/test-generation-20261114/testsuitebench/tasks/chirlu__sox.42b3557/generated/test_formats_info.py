import struct
import wave
from pathlib import Path

def test_wav_roundtrip_and_info_fields(run, make_wav, tmp_path):
    source=make_wav('source.wav',[0,1000,-1000,32767,-32768],rate=8000)
    out=tmp_path/'copy.wav'
    r=run([str(source),str(out)])
    assert r.returncode == 0
    with wave.open(str(out),'rb') as w:
        assert (w.getframerate(),w.getnchannels(),w.getnframes(),w.getsampwidth()) == (8000,1,5,2)
        assert w.readframes(5) == source.read_bytes()[44:54]
    fields={flag:run(['--info',flag,str(out)]) for flag in ['-t','-r','-c','-s','-D','-b','-e']}
    assert fields['-r'].stdout.strip() == b'8000'
    assert fields['-c'].stdout.strip() == b'1'
    assert fields['-s'].stdout.strip() == b'5'
    assert fields['-t'].stdout.strip().lower() == b'wav'
    assert fields['-b'].stdout.strip() == b'16'
    assert fields['-e'].stdout.strip() and b'PCM' in fields['-e'].stdout
    full=run(['--info',str(out)])
    assert full.returncode == 0
    for label in (b'Input File',b'Channels',b'Sample Rate',b'Precision',b'Duration',b'Sample Encoding'):
        assert label in full.stdout

def test_header_autodetection_and_no_extension(run, make_wav, tmp_path):
    wav=make_wav('original.wav',[1,-1,2],rate=11025)
    noext=tmp_path/'audio.with.dots'
    noext.write_bytes(wav.read_bytes())
    r=run(['--info','-r',str(noext)])
    assert r.returncode == 0 and r.stdout.strip() == b'11025'

def test_aiff_comments_visible_and_wav_comments_not_serialized(run, tmp_path):
    raw=tmp_path/'in.raw'; raw.write_bytes(struct.pack('<4h',1,2,3,4))
    common=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(raw)]
    ai=tmp_path/'comment.aiff'
    r=run([*common,'--comment','test-marker',str(ai)])
    assert r.returncode == 0
    q=run(['--info','-a',str(ai)])
    assert q.returncode == 0 and b'test-marker' in q.stdout
    wav=tmp_path/'comment.wav'
    assert run([*common,'--comment','test-marker',str(wav)]).returncode == 0
    q=run(['--info','-a',str(wav)])
    assert q.returncode == 0 and not q.stdout
    full=run(['--info',str(wav)])
    assert b'test-marker' not in full.stdout

def test_dat_header_and_roundtrip(run, raw16, tmp_path):
    inp=raw16('data.raw',[0,1000,-1000,2000])
    dat=tmp_path/'data.dat'; out=tmp_path/'back.raw'
    args=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(inp)]
    r=run([*args,'-t','dat',str(dat)])
    assert r.returncode == 0
    content=dat.read_text(errors='replace')
    assert '; Sample Rate 8000' in content and '; Channels 1' in content
    r=run(['-t','dat',str(dat),'-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(out)])
    assert r.returncode == 0 and len(out.read_bytes()) == 8

def test_endian_raw_output_and_transform_inverse(run, raw16, tmp_path):
    inp=raw16('input.raw',[0x1234,-2,0x4567])
    base=['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(inp)]
    little=tmp_path/'little.raw'; big=tmp_path/'big.raw'
    assert run([*base,'-t','raw','-L','-r','8000','-c','1','-b','16','-e','signed-integer',str(little)]).returncode == 0
    assert run([*base,'-t','raw','-B','-r','8000','-c','1','-b','16','-e','signed-integer',str(big)]).returncode == 0
    assert little.read_bytes() != big.read_bytes()
    assert big.read_bytes() == bytes.fromhex('1234fffe4567')

def test_info_missing_and_corrupt_inputs_fail_cleanly(run, tmp_path):
    for name, data in [('empty.wav',b''),('bad.wav',b'not-a-wave')]:
        p=tmp_path/name; p.write_bytes(data)
        r=run(['--info',str(p)])
        assert r.returncode != 0
        assert r.stderr
    r=run(['--info','-r',str(tmp_path/'missing.wav')])
    assert r.returncode != 0 and r.stderr

def test_info_multiple_fields_and_totals(run, make_wav, tmp_path):
    a=make_wav('a.wav',[1,2,3],rate=8000); b=make_wav('b.wav',[4,5],rate=8000)
    each=run(['--info','-s',str(a),str(b)])
    total=run(['--info','-T','-s',str(a),str(b)])
    assert each.returncode == total.returncode == 0
    assert each.stdout.splitlines() == [b'3',b'2']
    assert total.stdout.strip() == b'5'

def xa_header(magic=b'XA\0\0', decoded=0, tag=0, channels=2, rate=22050, avg=88200, align=4, bits=16):
    return (magic + struct.pack('<IHHIIHH',decoded,tag,channels,rate,avg,align,bits))

def test_xa_header_only_info_omits_unknown_length_fields(run, tmp_path):
    for index, magic in enumerate((b'XA\0\0',b'XAI\0',b'XAJ\0')):
        p=tmp_path/f'zero{index}.xa'; p.write_bytes(xa_header(magic=magic))
        r=run(['--info',str(p)])
        assert r.returncode==0
        for field in (b'Input File',b'Channels',b'Sample Rate',b'Precision',b'Sample Encoding'):
            assert field in r.stdout
        for field in (b'Duration',b'Samples read',b'File Size',b'Bit Rate'):
            assert field not in r.stdout

def test_xa_malformed_headers_fail_and_writer_is_read_only(run, tmp_path):
    for name, data in [('empty.xa',b''),('magic.xa',b'XA\0\0'),('wrong.xa',b'NOPE'+bytes(20)),('zerochannels.xa',xa_header(channels=0)),('wrongbits.xa',xa_header(bits=8))]:
        p=tmp_path/name; p.write_bytes(data)
        r=run(['--info','-r',str(p)])
        assert r.returncode!=0
    src=tmp_path/'source.raw'; src.write_bytes(bytes(8))
    out=tmp_path/'cannot.xa'
    r=run(['-t','raw','-r','8000','-c','1','-b','16','-e','signed-integer',str(src),'-t','xa',str(out)])
    assert r.returncode!=0 and not out.exists()
