import base64, hashlib, json, os, pathlib, re, struct, subprocess, tempfile
import pytest

EXE = pathlib.Path('/workspace/executable')
EVAL = pathlib.Path(__file__).resolve().parent

def invoke(args, *, home=None, cwd=None, data=None, env=None):
    e = os.environ.copy(); e['HOME'] = str(home or EVAL / 'home-default')
    if env: e.update(env)
    return subprocess.run([str(EXE), *map(str,args)], input=data, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=cwd or EVAL, env=e, timeout=20)

def clean(b): return re.sub(rb'\x1b\[[0-9;]*m', b'', b)
def png_dims(p):
    b=p.read_bytes(); assert b[:8] == b'\x89PNG\r\n\x1a\n'; assert b[12:16] == b'IHDR'; assert struct.unpack('>I',b[8:12])[0] == 13
    return struct.unpack('>II',b[16:24])
def render(tmp, *args, name='out.png', home=None):
    p=tmp/name; r=invoke([*args,'-o',str(p),'--silent'],home=home)
    return r,p

@pytest.mark.parametrize('flag',['-V','--version'],ids=['short-version','long-version'])
def test_version(flag):
    r=invoke([flag]); assert (r.returncode,r.stdout,r.stderr)==(0,b'codesnap-cli 0.13.1\n',b'')

def test_help_exact_ending_and_identity():
    r=invoke(['-h']); assert r.returncode==0 and r.stderr==b'' and r.stdout.endswith(b'\n') and b'Usage: codesnap [OPTIONS] --output <OUTPUT>' in r.stdout
    assert b'--raw-highlight-lines' in r.stdout and b'--type <TYPE>' in r.stdout

def test_full_help_is_distinct():
    a=invoke(['-h']); b=invoke(['--help']); assert a.returncode==b.returncode==0 and a.stdout!=b.stdout and b'Currently CodeSnap supports SVG format' in b.stdout

def test_subcommand_words_are_positionals():
    r=invoke(['list']); assert r.returncode==2 and not r.stdout and b"unexpected argument 'list'" in r.stderr

def test_output_required_before_runtime_input_check():
    r=invoke([]); assert r.returncode==2 and b'--output <OUTPUT>' in r.stderr

def test_no_input_runtime_error(tmp_path):
    r=invoke(['-o',str(tmp_path/'x.png')],home=tmp_path/'home'); assert r.returncode==1 and b'No code snippet provided' in clean(r.stdout) and not (tmp_path/'x.png').exists()

def test_duplicate_scalar_canonical_diagnostic():
    r=invoke(['-c','hi','-cs']); assert r.returncode==2 and not r.stdout and b"'--from-code [<Code>]' cannot be used multiple times" in r.stderr

@pytest.mark.parametrize('args,needle',[
 (['--has-breadcrumbs','maybe','-c','x','-o','x.png'],b"invalid value 'maybe' for '--has-breadcrumbs <HAS_BREADCRUMBS>'"),
 (['-o'],b"--output <OUTPUT>"), (['--type','bogus','-c','x','-o','x.png'],b'ascii'),
 (['--scale-factor','-1','-c','x','-o','x.png'],b'unexpected argument'),
 (['--out','x','-c','x','-o','x.png'],b'unexpected argument')],ids=['bool','missing-output-value','bad-type','negative-number','partial-option'])
def test_parser_rejections(args,needle):
    r=invoke(args); assert r.returncode==2 and not r.stdout and needle in r.stderr

def test_first_home_creates_exact_defaults_and_remote_themes(tmp_path):
    h=tmp_path/'home'; r=invoke(['-c','x','-o',str(tmp_path/'x.png'),'--silent'],home=h)
    assert r.returncode==0 and b'[INFO]' in r.stdout
    cfg=h/'.config/codesnap/config.json'; j=json.loads(cfg.read_text()); assert j['print_eggs'] is False
    s=j['snapshot_config']; assert s['theme']=='candy' and s['window']['margin']=={'x':82,'y':82} and s['watermark']['content']=='CodeSnap'
    assert (h/'.config/codesnap/remote_themes').is_dir()

def test_existing_config_no_info_or_rewrite(tmp_path):
    h=tmp_path/'home'; p=h/'.config/codesnap/config.json'; p.parent.mkdir(parents=True); p.write_text('{"print_eggs":false,"snapshot_config":{"background":"#ffffff"}}'); before=p.read_bytes()
    r=invoke(['-c','x','-o',str(tmp_path/'x.png'),'--silent'],home=h)
    assert r.returncode==0 and b'[INFO]' not in r.stdout and p.read_bytes()==before

def test_explicit_config_skips_default_but_prepares_remote_dir(tmp_path):
    h=tmp_path/'home'; c=tmp_path/'cfg file.json'; c.write_text('{"print_eggs":false,"snapshot_config":{"background":"#ffffff"}}')
    r=invoke(['-c','x','--config',str(c),'-o',str(tmp_path/'x.png'),'--silent'],home=h)
    assert r.returncode==0 and not (h/'.config/codesnap/config.json').exists() and (h/'.config/codesnap/remote_themes').is_dir()

def test_bad_config_is_handled_and_creates_no_output(tmp_path):
    c=tmp_path/'bad.json'; c.write_text('{'); out=tmp_path/'x.png'; r=invoke(['-c','x','--config',str(c),'-o',str(out),'--silent'],home=tmp_path/'h')
    assert r.returncode==1 and b'[ERROR]' in clean(r.stdout) and not out.exists()

def test_file_mode_and_file_precedence(tmp_path):
    src=tmp_path/'sample.rs'; src.write_text('fn file() {}'); out=tmp_path/'x.png'
    r=invoke(['-f',str(src),'-c','inline','-o',str(out),'--silent'],home=tmp_path/'h')
    assert r.returncode==0 and png_dims(out)[0]>0

def test_missing_file_runtime_failure(tmp_path):
    out=tmp_path/'x.png'; r=invoke(['-f',str(tmp_path/'absent.rs'),'-o',str(out)],home=tmp_path/'h')
    assert r.returncode==1 and b'No such file or directory' in clean(r.stdout) and not out.exists()

def test_stdin_inline_and_unicode(tmp_path):
    out=tmp_path/'x.png'; r=invoke(['-c','-','-o',str(out),'--silent'],home=tmp_path/'h',data='λ\n'.encode())
    assert r.returncode==0 and png_dims(out)[0]>0

def test_range_output_changes_and_reduces_size(tmp_path):
    code='\n'.join('line '+str(i) for i in range(1,31)); a=tmp_path/'all.png'; b=tmp_path/'part.png'
    for dest,args in [(a,['-c',code]),(b,['-c',code,'--range','3:6'])]:
        r=invoke([*args,'-o',str(dest),'--silent'],home=tmp_path/'h'); assert r.returncode==0
    assert b.stat().st_size < a.stat().st_size/2

def test_range_errors_are_handled(tmp_path):
    for value, phrase in [('1:2:3','Invalid range format'),(':','cannot parse integer from empty string'),('x','invalid digit found in string')]:
        out=tmp_path/(str(len(value))+'.png'); r=invoke(['-c','a\nb','--range',value,'-o',str(out)],home=tmp_path/'h')
        assert r.returncode==1 and phrase.encode() in clean(r.stdout) and not out.exists()

def test_line_number_and_highlight_change_bytes(tmp_path):
    paths=[]
    for n,args in enumerate([[],['--has-line-number'],['--highlight-range','2']]):
        p=tmp_path/f'{n}.png'; paths.append(p); r=invoke(['-c','a\nb\nc',*args,'-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0
    assert len({p.read_bytes() for p in paths})==3

def test_relative_and_raw_highlight_render(tmp_path):
    for i,extra in enumerate([['--range','3:6','--relative-highlight-range','--highlight-range','2:3'],['--raw-highlight-lines','[[1,"#ff000080"],[2,4,"#00ff0080"]]']]):
        r,p=render(tmp_path,'-c','a\nb\nc\nd\ne\nf',*extra,name=f'{i}.png',home=tmp_path/'h'); assert r.returncode==0 and p.stat().st_size>10000

def test_color_lazy_and_active_invalid(tmp_path):
    r=invoke(['-c','x','--line-number-color','nope','-o',str(tmp_path/'lazy.png'),'--silent'],home=tmp_path/'h'); assert r.returncode==0
    r=invoke(['-c','x','--has-line-number','--line-number-color','nope','-o',str(tmp_path/'bad.png')],home=tmp_path/'h'); assert r.returncode!=0 and b'Invalid hex color: nope' in r.stderr and not (tmp_path/'bad.png').exists()

def test_ignored_background_same_bytes(tmp_path):
    a=tmp_path/'a.png'; b=tmp_path/'b.png'
    for p,args in [(a,[]),(b,['--background','#gg0000'])]:
        r=invoke(['-c','x',*args,'-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0
    assert a.read_bytes()==b.read_bytes()

def test_bad_image_path_is_literal_bytes_and_not_written(tmp_path):
    p=tmp_path/'existing.png'; p.write_bytes(b'not png'); out=tmp_path/'out.png'
    r=invoke(['-i',str(p),'-o',str(out)],home=tmp_path/'h'); assert r.returncode==1 and b'Invalid PNG signature' in clean(r.stdout) and not out.exists()

def test_empty_image_stdin_error(tmp_path):
    out=tmp_path/'out.png'; r=invoke(['-i','-','-o',str(out)],home=tmp_path/'h',data=b''); assert r.returncode==1 and b'Unexpected end of data before image end' in clean(r.stdout) and not out.exists()

def test_output_png_svg_html_payload_equivalence(tmp_path):
    blobs=[]
    for ext in ['png','svg','html']:
        p=tmp_path/f'out.{ext}'; r=invoke(['-c','x','-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0
        raw=p.read_bytes()
        if ext=='png': blobs.append(raw)
        elif ext=='svg': blobs.append(base64.b64decode(re.search(rb'base64,([^" ]+)',raw).group(1)))
        else: blobs.append(base64.b64decode(re.search(rb'base64,([^" ]+)',raw).group(1)))
    assert blobs[0]==blobs[1]==blobs[2]

def test_raw_png_stdout_and_ascii_warning(tmp_path):
    r=invoke(['-c','x','-o','raw','--silent'],home=tmp_path/'h'); assert r.returncode==0 and r.stdout.startswith(b'\x89PNG') and len(r.stdout)>1000
    p=tmp_path/'ascii.png'; r=invoke(['-c','x','--type','ascii','-o',str(p)],home=tmp_path/'h'); assert r.returncode==0 and b'ASCII snapshot only supports copying to clipboard' in clean(r.stdout) and not p.exists()

def test_unknown_theme_and_unknown_file_hint_fail_before_output(tmp_path):
    for opts,phrase in [(['--code-theme','NOPE'],'Cannot find NOPE theme'),(['--file-path','missing.unknown_xyz'],'No such file missing.unknown_xyz')]:
        out=tmp_path/(str(len(phrase))+'.png'); r=invoke(['-c','x',*opts,'-o',str(out)],home=tmp_path/'h'); assert r.returncode==1 and phrase.encode() in clean(r.stdout) and not out.exists()

def test_execute_and_skip_render(tmp_path):
    p=tmp_path/'cmd.png'; r=invoke(['--execute','printf hello','--execute','printf world','-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0 and p.exists()
    q=tmp_path/'skip.png'; r=invoke(['--execute','printf hello','--skip','-o',str(q),'--silent'],home=tmp_path/'h'); assert r.returncode==0 and q.exists()

def test_title_empty_changes_raster_layout(tmp_path):
    a=tmp_path/'a.png'; b=tmp_path/'b.png'
    for p,args in [(a,[]),(b,['--title',''])]:
        r=invoke(['-c','x','--mac-window-bar','false','--scale-factor','1',*args,'-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0
    assert png_dims(a)==(518,284) and png_dims(b)==(518,298)

def test_scale_zero_and_scale_dimensions(tmp_path):
    out=tmp_path/'bad.png'; r=invoke(['-c','x','--scale-factor','0','-o',str(out)],home=tmp_path/'h'); assert r.returncode==1 and b'scale factor must be greater than 1' in clean(r.stdout) and not out.exists()
    dims=[]
    for factor in [1,2,5]:
        p=tmp_path/f'{factor}.png'; r=invoke(['-c','x','--scale-factor',str(factor),'-o',str(p),'--silent'],home=tmp_path/'h'); assert r.returncode==0; dims.append(png_dims(p))
    assert dims[1]==(dims[0][0]*2,dims[0][1]*2) and dims[2]==(dims[0][0]*5,dims[0][1]*5)
