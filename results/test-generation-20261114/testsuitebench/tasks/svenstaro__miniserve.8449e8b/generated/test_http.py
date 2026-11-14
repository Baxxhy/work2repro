import os, re, subprocess, tempfile, time, urllib.request, urllib.error, urllib.parse, socket, signal
from pathlib import Path
import pytest

BIN='/workspace/executable'

class Server:
    def __init__(self, root, *opts, env=None):
        e=os.environ.copy()
        for k in list(e):
            if k.startswith('MINISERVE_') or k.startswith('MINISERVER_'): e.pop(k)
        if env: e.update(env)
        self.p=subprocess.Popen([BIN,*map(str,opts),str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=e)
        deadline=time.time()+8; data=b''
        while time.time()<deadline:
            if self.p.poll() is not None: raise AssertionError(('server exited',self.p.returncode,self.p.stdout.read(),self.p.stderr.read()))
            try:
                data += self.p.stdout.read1(512)
            except Exception: pass
            m=re.search(rb'https?://(?:\[[^]]+\]|[^:/\s]+):(\d+)',data)
            if m:
                self.port=int(m.group(1)); self.url=m.group(0).decode(); break
            time.sleep(.05)
        else: raise AssertionError(('no startup url',data))
    def close(self):
        self.p.terminate()
        try:self.p.wait(timeout=3)
        except subprocess.TimeoutExpired:self.p.kill(); self.p.wait()
    def req(self,path='/',method='GET',headers=None,data=None):
        q=urllib.request.Request(self.url+path,data=data,headers=headers or {},method=method)
        try:
            with urllib.request.urlopen(q,timeout=3) as r:return r.status,r.headers,r.read()
        except urllib.error.HTTPError as e:return e.code,e.headers,e.read()

@pytest.fixture
def server_factory():
    made=[]
    def start(root,*opts,env=None):
        s=Server(root,*opts,env=env); made.append(s); return s
    yield start
    for s in made:s.close()

def test_files_status_mime_and_url_encoding(tmp_path,server_factory):
    (tmp_path/'hello world.txt').write_bytes(b'hello\x00\xff')
    (tmp_path/'page.html').write_text('<h1>x</h1>')
    (tmp_path/'data.json').write_text('{}')
    (tmp_path/'image.png').write_bytes(b'png')
    (tmp_path/'blob.bin').write_bytes(b'\x00\xff')
    (tmp_path/'café &+%.txt').write_text('unicode')
    s=server_factory(tmp_path)
    for name,body,mime in [('hello world.txt',b'hello\x00\xff','text/plain'),('page.html',b'<h1>x</h1>','text/html'),('data.json',b'{}','application/json'),('image.png',b'png','image/png'),('blob.bin',b'\x00\xff','application/octet-stream')]:
        code,h,b=s.req('/'+urllib.parse.quote(name)); assert code==200 and b==body and h.get_content_type()==mime and int(h['Content-Length'])==len(body)
    assert s.req('/caf%C3%A9%20%26%2B%25.txt')[2]==b'unicode'
    assert s.req('/missing')[0]==404

def test_file_path_direct_and_large_bytes(tmp_path,server_factory):
    data=bytes(range(256))*5000; f=tmp_path/'binary.dat'; f.write_bytes(data)
    s=server_factory(f)
    code,h,b=s.req('/'); assert code==200 and b==data and int(h['Content-Length'])==len(data)

def test_head_range_and_headers(tmp_path,server_factory):
    (tmp_path/'f.txt').write_bytes(b'0123456789'*30)
    s=server_factory(tmp_path,'--header','X-Test-Header:abc','--header','Cache-Control:no-cache')
    g=s.req('/f.txt'); h=s.req('/f.txt','HEAD')
    assert h[0]==200 and h[2]==b'' and h[1]['Content-Length']==g[1]['Content-Length']
    assert h[1]['X-Test-Header']=='abc' and g[1]['Cache-Control']=='no-cache'
    code,headers,b=s.req('/f.txt',headers={'Range':'bytes=10-19'}); assert code==206 and b==b'0123456789' and headers['Content-Range'].startswith('bytes 10-19/')

def test_listings_hidden_order_title_and_ui(tmp_path,server_factory):
    (tmp_path/'aaa.txt').write_text('a'); (tmp_path/'zzz.txt').write_text('z'); (tmp_path/'.hidden').write_text('h'); (tmp_path/'folder').mkdir()
    s=server_factory(tmp_path,'--title','<A&B>"\'','--dirs-first','--hide-version-footer','--hide-theme-selector','--show-wget-footer')
    code,h,b=s.req('/'); page=b.decode()
    assert code==200 and '<html' in page and '</html>' in page and 'aaa.txt' in page and 'zzz.txt' in page and 'folder/' in page
    assert '.hidden' not in page and page.index('folder/') < page.index('aaa.txt')
    assert '&lt;A&amp;B&gt;' in page and 'wget' in page and ('-r' in page or '--recursive' in page)
    assert s.req('/.hidden')[0] in (403,404)

def test_hidden_raw_and_exact_sizes(tmp_path,server_factory):
    (tmp_path/'.secret').write_text('yes'); (tmp_path/'bytes.txt').write_bytes(b'x'*1234); (tmp_path/'empty').mkdir()
    s=server_factory(tmp_path,'--hidden','--size-display','exact')
    page=s.req('/?raw=true')[2].decode(); assert '.secret' in page and '1234' in page and '<html' in page

def test_index_spa_pretty_and_disabled_listing(tmp_path,server_factory):
    (tmp_path/'index.html').write_text('INDEX'); (tmp_path/'about.html').write_text('ABOUT'); sub=tmp_path/'sub'; sub.mkdir(); (sub/'index.html').write_text('SUB')
    s=server_factory(tmp_path,'--index','index.html','--spa','--pretty-urls')
    assert s.req('/')[2]==b'INDEX' and s.req('/sub/')[2]==b'SUB' and s.req('/about')[2]==b'ABOUT' and s.req('/not-here')[2]==b'INDEX'
    s2=server_factory(tmp_path,'--disable-indexing'); assert s2.req('/sub/')[0] in (403,404) and s2.req('/about.html')[0]==200

def test_prefix_health_and_random_route(tmp_path,server_factory):
    (tmp_path/'f').write_text('x'); s=server_factory(tmp_path,'--route-prefix','/prefix/')
    assert s.req('/prefix')[0]==200 and s.req('/prefix/f')[2]==b'x' and s.req('/')[0]==404
    assert s.req('/__miniserve_internal/healthcheck')[0]==200
    t=server_factory(tmp_path,'--random-route'); m=re.search(r'/(?:[0-9a-fA-F]{6})/?$',t.url)
    assert m or t.url and t.req('/')[0]==404

def test_symlink_follow_and_no_symlinks(tmp_path,server_factory):
    outside=tmp_path.parent/'outside-test-file'; outside.write_text('outside'); root=tmp_path/'root'; root.mkdir(); (root/'link').symlink_to(outside)
    s=server_factory(root); code,_,body=s.req('/link'); assert code==200 and body==b'outside'
    t=server_factory(root,'--no-symlinks'); assert t.req('/link')[0] in (403,404) and 'link' not in t.req('/')[2].decode()

def test_authentication_and_hash(tmp_path,server_factory):
    (tmp_path/'f').write_text('ok')
    import hashlib
    digest=hashlib.sha256(b'secret').hexdigest()
    s=server_factory(tmp_path,'--auth','alice:pw','--auth',f'bob:sha256:{digest}')
    assert s.req('/f')[0]==401 and 'WWW-Authenticate' in s.req('/f')[1]
    assert s.req('/f',headers={'Authorization':'Basic '+__import__('base64').b64encode(b'alice:pw').decode()})[2]==b'ok'
    assert s.req('/f',headers={'Authorization':'Basic '+__import__('base64').b64encode(b'bob:secret').decode()})[2]==b'ok'

def test_archives_and_indexing_disable(tmp_path,server_factory):
    (tmp_path/'f.txt').write_text('archive-data')
    s=server_factory(tmp_path)
    for q in ('tar','tar_gz','zip'): assert s.req('/?download='+q)[0]==403
    t=server_factory(tmp_path,'--enable-tar','--enable-tar-gz','--enable-zip')
    assert b'Download .tar.gz' in t.req('/')[2]
    for q,magic in [('tar',b'archive-data'),('tar_gz',b'\x1f\x8b'),('zip',b'PK')]:
        code,h,b=t.req('/?download='+q); assert code==200 and magic in b[:100] if q!='tar' else code==200 and b'archive-data' in b
    d=server_factory(tmp_path,'--disable-indexing','--enable-tar'); assert d.req('/?download=tar')[0]==404

def test_upload_and_mkdir_forms(tmp_path,server_factory):
    (tmp_path/'sub').mkdir(); s=server_factory(tmp_path,'--upload-files','--mkdir')
    page=s.req('/')[2].decode(); assert 'id="mkdir"' in page and 'name="mkdir"' in page
    # Multipart body with file field.
    boundary='----eval-boundary'; body=(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="new.txt"\r\nContent-Type: text/plain\r\n\r\nUPLOADED\r\n--{boundary}--\r\n').encode()
    code,_,_=s.req('/upload?path=/sub',headers={'Content-Type':'multipart/form-data; boundary='+boundary},method='POST',data=body)
    assert code in (200,201,302,303) and (tmp_path/'sub'/'new.txt').read_bytes()==b'UPLOADED'
    assert s.req('/upload?path=/sub',method='POST',data=b'mkdir=child',headers={'Content-Type':'application/x-www-form-urlencoded'})[0] < 400
    assert (tmp_path/'sub'/'child').is_dir()

def test_upload_disabled_and_delete_is_non_destructive(tmp_path,server_factory):
    (tmp_path/'victim.txt').write_text('safe'); s=server_factory(tmp_path)
    assert s.req('/upload?path=/',method='POST',data=b'x')[0]>=400
    assert s.req('/victim.txt',method='DELETE')[0] in (404,405)
    assert (tmp_path/'victim.txt').read_text()=='safe'

def test_webdav(tmp_path,server_factory):
    (tmp_path/'child.txt').write_text('x'); s=server_factory(tmp_path,'--enable-webdav')
    code,h,b=s.req('/','PROPFIND',{'Depth':'1'}); assert code in (200,207) and b and 'xml' in h.get('Content-Type','') and b'child.txt' in b
    code,h,_=s.req('/','OPTIONS'); assert code==200 and 'DAV' in h and 'OPTIONS' in h.get('Allow','') and 'PROPFIND' in h.get('Allow','')

def test_path_traversal_never_exposes_outside(tmp_path,server_factory):
    (tmp_path/'secret').write_text('inside'); outside=tmp_path.parent/'eval-outside-secret'; outside.write_text('TOPSECRET')
    s=server_factory(tmp_path)
    for path in ('/../eval-outside-secret','/%2e%2e/eval-outside-secret','/%252e%252e/eval-outside-secret'):
        code,_,body=s.req(path); assert code in (400,403,404) and b'TOPSECRET' not in body

def test_readme_title_qr_and_theme_options(tmp_path,server_factory):
    (tmp_path/'README.md').write_text('# Readme marker')
    (tmp_path/'f').write_text('data')
    plain=server_factory(tmp_path)
    assert b'qrcode' not in plain.req('/')[2].lower()
    readme=server_factory(tmp_path,'--readme','--qrcode','--color-scheme','monokai','--color-scheme-dark','zenburn')
    page=readme.req('/')[2].decode().lower()
    assert 'readme marker' in page and ('qrcode' in page or 'qr' in page or '<svg' in page)

def test_compression_and_concurrent_requests(tmp_path,server_factory):
    payload=(b'compressible-content-'*10000); (tmp_path/'large.txt').write_bytes(payload)
    s=server_factory(tmp_path,'--compress-response')
    results=[]
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results=list(pool.map(lambda _:s.req('/large.txt'),range(4)))
    for code,h,b in results:
        assert code==200
        if h.get('Content-Encoding')=='gzip':
            import gzip; assert gzip.decompress(b)==payload
        else: assert b==payload

def test_directory_size_metadata_and_sort_links(tmp_path,server_factory):
    sub=tmp_path/'sized'; sub.mkdir(); (sub/'content').write_bytes(b'x'*321)
    s=server_factory(tmp_path,'--directory-size','--size-display','exact')
    page=s.req('/')[2].decode()
    assert 'Last modification' in page and 'sort' in page.lower()
    assert '<td class="size-cell"></td>' in page
    assert 'DirSize' in page and '/__miniserve_internal/api' in page
