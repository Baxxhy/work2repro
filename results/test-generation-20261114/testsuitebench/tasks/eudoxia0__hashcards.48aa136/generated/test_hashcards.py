import json
import os
import pathlib
import re
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

BIN = pathlib.Path('/workspace/executable')
if not BIN.exists():
    BIN = pathlib.Path(__file__).resolve().parent.parent / 'executable'


def run(*args, cwd=None, env=None, timeout=10):
    e = os.environ.copy()
    e.pop('RUST_LOG', None)
    if env:
        e.update(env)
    return subprocess.run([str(BIN), *map(str, args)], cwd=cwd, env=e,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)


def collection(tmp_path, files=None):
    root = tmp_path / 'collection'
    root.mkdir(parents=True)
    for name, data in (files or {}).items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data if isinstance(data, bytes) else data.encode())
    return root


def test_top_help_and_version(tmp_path):
    p = run('--help')
    assert p.returncode == 0 and p.stderr == b''
    assert p.stdout.decode().startswith('A plain text-based spaced repetition system.\n\nUsage: executable <COMMAND>')
    assert 'drill    Drill cards through a web interface' in p.stdout.decode()
    assert 'export  Export a collection' in p.stdout.decode()
    assert run('-V').stdout == b'hashcards 0.3.0\n'
    assert run().returncode == 2 and run().stdout == b''
    assert run().stderr.startswith(b'A plain text-based spaced repetition system.')


def test_help_precedence_and_help_dispatch():
    assert run('--help', '--anything').returncode == 0
    assert run('help').stdout == run('--help').stdout
    assert run('help', 'stats').stdout == run('stats', '--help').stdout
    assert run('help', '--help').returncode == 2


def test_parser_rejects_unknown_commands_and_global_version_after_command():
    for args, fragment in [(('StAtS',), b'unrecognized subcommand'), (('stats', '--version'), b'unexpected argument'), (('stats', '--wat'), b'unexpected argument')]:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b''
        assert fragment in p.stderr and b'Usage:' in p.stderr and b"For more information, try '--help'." in p.stderr


def test_subcommand_help_blocks():
    expected_check = '''Check the integrity of a collection\n\nUsage: executable check [DIRECTORY]\n\nArguments:\n  [DIRECTORY]  Path to the collection directory. By default, the current working directory is used\n\nOptions:\n  -h, --help  Print help\n'''
    expected_export = '''Export a collection\n\nUsage: executable export [OPTIONS] [DIRECTORY]\n\nArguments:\n  [DIRECTORY]  Path to the collection directory. By default, the current working directory is used\n\nOptions:\n      --output <OUTPUT>  Optional path to the output file. By default, the output is printed to stdout\n  -h, --help             Print help\n'''
    assert run('check', '--help').stdout.decode() == expected_check
    assert run('export', '--help').stdout.decode() == expected_export
    assert run('stats', '--help').stdout.decode().startswith('Print collection statistics\n\nUsage: executable stats [OPTIONS] [DIRECTORY]')
    oh = run('orphans', '--help').stdout.decode()
    assert 'Commands relating to orphan cards\n\nUsage: executable orphans <COMMAND>' in oh
    assert 'list    List the hashes of all orphan cards' in oh and 'delete  Remove all orphan cards' in oh
    q = run('orphans')
    assert q.returncode == 2 and q.stdout == b'' and q.stderr.decode().startswith('Commands relating to orphan cards')


def test_drill_help_options_and_defaults():
    h = run('drill', '--help').stdout.decode()
    for x in ['--card-limit', '--new-card-limit', '--host', '[default: 127.0.0.1]', '--port', '[default: 8000]', '--from-deck', '--open-browser', 'true', 'false', '--answer-controls', 'full', 'binary', '[default: full]', '--bury-siblings', 'all four rating buttons (Forgot/Hard/Good/Easy)']:
        assert x in h


def test_exact_cli_value_errors():
    cases = [
        (('stats','-f','html'), "error: unexpected argument '-f' found\n\n  tip: to pass '-f' as a value, use '-- -f'\n\nUsage: executable stats [OPTIONS] [DIRECTORY]\n\nFor more information, try '--help'.\n"),
        (('drill','-1'), "error: unexpected argument '-1' found\n\n  tip: to pass '-1' as a value, use '-- -1'\n\nUsage: executable drill [OPTIONS] [DIRECTORY]\n\nFor more information, try '--help'.\n"),
        (('drill','--port','wat'), "error: invalid value 'wat' for '--port <PORT>': invalid digit found in string\n\nFor more information, try '--help'.\n"),
        (('drill','--port','70000'), "error: invalid value '70000' for '--port <PORT>': 70000 is not in 0..=65535\n\nFor more information, try '--help'.\n"),
        (('stats','--format'), "error: a value is required for '--format <FORMAT>' but none was supplied\n  [possible values: html, json]\n\nFor more information, try '--help'.\n"),
        (('export','--output'), "error: a value is required for '--output <OUTPUT>' but none was supplied\n\nFor more information, try '--help'.\n"),
    ]
    for args, err in cases:
        p = run(*args)
        assert p.returncode == 2 and p.stdout == b'' and p.stderr.decode() == err


def test_missing_directory_diagnostic(tmp_path):
    p = run('check', tmp_path/'absent')
    assert p.returncode == 1 and p.stdout == b''
    assert p.stderr == b'hashcards: error: directory does not exist.'


def test_check_initializes_db_and_accepts_empty_collection(tmp_path):
    root = collection(tmp_path, {'notes.txt':'not a deck', 'UPPER.MD':'Q:x\nA:y\n'})
    p = run('check', root)
    assert (p.returncode, p.stdout, p.stderr) == (0, b'ok\n', b'')
    db = root/'hashcards.db'
    assert db.is_file() and os.stat(db).st_mode & 0o600 == 0o600
    con = sqlite3.connect(db)
    assert con.execute('select count(*) from cards').fetchone()[0] == 0
    con.close()


def test_json_stats_and_macro_line_rules(tmp_path):
    root = collection(tmp_path, {'one.md':'Q: q\nA: a\n', 'macros.tex':'% ignore\n\\RR \u007bR\u007d\nNoSpace\n   \n\n'})
    p = run('stats','--format','json',root)
    assert p.returncode == 0 and p.stderr == b''
    obj = json.loads(p.stdout)
    assert list(obj) == ['cardsInDeckCount','cardsInDbCount','texMacroCount','cardsReviewedTodayCount']
    assert obj['cardsInDeckCount'] == 1 and obj['cardsInDbCount'] == 0 and obj['texMacroCount'] == 2
    assert run('stats','--format=html',root).stderr == b'HTML output is not implemented yet.\n'
    assert run('stats',root).stdout == b''


def test_collection_loads_hidden_recursive_unicode_and_deduplicates(tmp_path):
    root = collection(tmp_path, {'sub/é space.name.md':'Q: q\nA: a\n', '.hidden.md':'Q: q\nA: a\n', '.gitignore':'*.md\n', 'ignored.Md':'Q: x\nA: y\n'})
    p = run('stats','--format','json',root)
    assert p.returncode == 0
    assert json.loads(p.stdout)['cardsInDeckCount'] == 1


def test_frontmatter_name_and_source_lines_export(tmp_path):
    root = collection(tmp_path, {'multi.part-é.md':'---\nname = "A Name"\nother = 5\n---\nQ: q\nA: a'})
    data = json.loads(run('export',root).stdout)
    assert len(data['cards']) == 1
    c = data['cards'][0]
    assert c['deckName'] == 'A Name'
    assert c['location']['lineStart'] == 0 and c['location']['lineEnd'] == 1
    assert c['location']['filePath'] == str((root/'multi.part-é.md').resolve())


def test_frontmatter_errors_and_leading_blank_is_not_frontmatter(tmp_path):
    root = collection(tmp_path, {'bad.md':'---\nname = "x"\nQ: q\nA: a\n'})
    p = run('check',root)
    assert p.returncode == 1 and b"Frontmatter opening '---' found but no closing '---'" in p.stderr
    (root/'bad.md').write_text('---\nname: Test\n---\nQ: q\nA: a\n')
    p = run('check',root)
    assert p.returncode == 1 and b'Failed to parse TOML frontmatter:' in p.stderr
    (root/'bad.md').write_text('\n---\nname = "x"\n---\nQ: q\nA: a\n')
    assert run('check',root).returncode == 0


def test_card_language_transitions_and_empty_values(tmp_path):
    root = collection(tmp_path, {'cards.md':'heading\n---\nQ:  \nA:\n---\n---\nQ: q\nA: a\nC: [x]\nQ: end\nA: z'})
    p = run('export',root)
    assert p.returncode == 0, p.stderr
    cards = json.loads(p.stdout)['cards']
    assert len(cards) == 3
    basics = [x['content']['basic'] for x in cards if 'basic' in x['content']]
    assert {'question':'','answer':''} in basics
    assert {'question':'end','answer':'z'} in basics


def test_parse_error_reasons_have_location_and_no_partial_stdout(tmp_path):
    cases = [
        ('A: orphan\n','Found answer tag without a question.'),
        ('Q: q\nQ: next\n','New question without answer.'),
        ('Q: q\nC: [x]\n','Found cloze tag while reading a question.'),
        ('Q: q\n---\n','Found flashcard separator while reading a question.'),
        ('Q: q','File ended while reading a question without an answer.'),
        ('Q: q\nA: a\nA: b\n','Found answer tag while reading an answer.'),
        ('C: no deletion\n','Cloze card must contain at least one cloze deletion.'),
    ]
    for i,(body,reason) in enumerate(cases):
        root=collection(tmp_path/str(i), {'deck.md':body})
        p=run('check',root)
        assert p.returncode==1 and p.stdout==b'' and reason.encode() in p.stderr
        assert str((root/'deck.md').resolve()).encode() in p.stderr and b'Location:' in p.stderr


def test_cloze_offsets_hash_shape_and_family(tmp_path):
    root=collection(tmp_path, {'c.md':'C: Foo [bar] baz [quux].\n'})
    cards=json.loads(run('export',root).stdout)['cards']
    assert len(cards)==2
    assert all(len(c['hash'])==64 and re.fullmatch('[0-9a-f]{64}',c['hash']) for c in cards)
    assert all(c['familyHash']==cards[0]['familyHash'] for c in cards)
    contents=sorted((c['content']['cloze']['start'],c['content']['cloze']['end'],c['content']['cloze']['text']) for c in cards)
    assert contents==[(4,6,'Foo bar baz quux.'),(12,15,'Foo bar baz quux.')]


def test_cloze_escapes_images_and_unicode_byte_offsets(tmp_path):
    root=collection(tmp_path, {'c.md':'C: é \\[lit\\] ![alt](image.png) [x]\n', 'image.png':b'img'})
    p=run('export',root)
    assert p.returncode==0, p.stderr
    c=json.loads(p.stdout)['cards'][0]['content']['cloze']
    assert c['text']=='é [lit] ![alt](missing.png) x'
    assert c['start']==len('é [lit] ![alt](missing.png) '.encode())


def test_missing_media_validation_and_url_decode(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: ![a](missing%20file.png)\nA: ![b](@/gone.png)\n'})
    p=run('check',root)
    assert p.returncode==1 and p.stdout==b''
    err=p.stderr.decode()
    assert err.startswith('hashcards: error: Missing media files referenced in cards:')
    assert 'missing file.png' in err and '@/gone.png' in err
    assert err.index('@/gone.png') < err.index('missing file.png')


def test_ordinary_markdown_link_does_not_require_file(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: [link](missing)\nA: answer\n'})
    assert run('check',root).stdout==b'ok\n'


def test_export_shape_order_and_output_file(tmp_path):
    root=collection(tmp_path, {'z.md':'Q: z\nA: a\n','a.md':'Q: a\nA: b\n'})
    p=run('export',root)
    obj=json.loads(p.stdout)
    assert list(obj)==['cards','sessions'] and len(obj['cards'])==2
    assert [c['hash'] for c in obj['cards']]==sorted(c['hash'] for c in obj['cards'])
    output=tmp_path/'out.json'
    q=run('export',root,'--output',output)
    assert q.returncode==0 and q.stdout==b'' and json.loads(output.read_text())==obj
    assert run('export',root,'--output',tmp_path/'absent'/'out').returncode==1


def test_orphan_list_delete_cascades_and_preserves_sessions(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: present\nA: card\n'})
    assert run('check',root).returncode==0
    con=sqlite3.connect(root/'hashcards.db')
    con.execute('PRAGMA foreign_keys=ON')
    con.execute("insert into cards(card_hash,added_at,review_count) values ('orphan','2020-01-01T00:00:00.000',1)")
    sid=con.execute("insert into sessions(started_at,ended_at) values ('2020-01-01T00:00:00.000','2020-01-01T00:00:01.000')").lastrowid
    con.execute("insert into reviews(session_id,card_hash,reviewed_at,grade,stability,difficulty,interval_raw,interval_days,due_date) values (?,?,'2020-01-01T00:00:00.000','good',1,1,1,1,'2020-01-02')",(sid,'orphan'))
    con.commit();con.close()
    assert run('orphans','list',root).stdout==b'orphan\n'
    p=run('orphans','delete',root)
    assert p.stdout==b'orphan\n'
    con=sqlite3.connect(root/'hashcards.db')
    assert con.execute('select count(*) from reviews').fetchone()[0]==0
    assert con.execute('select count(*) from sessions').fetchone()[0]==1
    con.close()
    assert run('orphans','delete',root).stdout==b''


def test_read_only_commands_preserve_database_bytes(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: q\nA: a\n'})
    run('check',root)
    db=root/'hashcards.db'; before=db.read_bytes()
    for args in [('check',root),('stats','--format','json',root),('export',root),('orphans','list',root)]:
        assert run(*args).returncode==0
        assert db.read_bytes()==before


def test_corrupt_database_and_file_as_directory_are_clean_errors(tmp_path):
    root=collection(tmp_path)
    (root/'hashcards.db').write_bytes(b'not sqlite')
    p=run('check',root)
    assert p.returncode==1 and p.stderr.startswith(b'hashcards: error: rusqlite:') and b'NotADatabase' in p.stderr
    f=tmp_path/'ordinary'; f.write_text('x')
    p=run('check',f)
    assert p.returncode==1 and p.stderr.startswith(b'hashcards: error: rusqlite:') and b'CannotOpen' in p.stderr


def test_rust_log_debug_and_help_ignores_invalid_log_directive(tmp_path):
    root=collection(tmp_path)
    p=run('check',root,env={'RUST_LOG':'debug'})
    assert p.returncode==0 and b'debug' in p.stderr.lower() and p.stdout==b'ok\n'
    assert run('--help',env={'RUST_LOG':'this is invalid'}).returncode==0


def start_drill(root, port, extra=()):
    proc=subprocess.Popen([str(BIN),'drill','--host','127.0.0.1','--port',str(port),'--open-browser','false',*extra,str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    url=f'http://127.0.0.1:{port}'
    deadline=time.time()+8
    while time.time()<deadline:
        if proc.poll() is not None:
            out,err=proc.communicate(timeout=1)
            return proc,None,(out,err)
        try:
            return proc,urllib.request.urlopen(url,timeout=.4),None
        except Exception:
            time.sleep(.04)
    proc.kill(); raise AssertionError('drill server did not become ready')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def test_drill_no_due_cards_and_database_sync(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: q\nA: a\n'})
    p=run('drill','--open-browser','false',root,timeout=10)
    assert p.returncode==0 and p.stdout==b'No cards due today.\n'
    con=sqlite3.connect(root/'hashcards.db')
    assert con.execute('select count(*) from cards').fetchone()[0]==1
    con.close()


def test_drill_live_ui_reveal_grade_and_shutdown(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: question\nA: answer\n'})
    port=18761
    proc,resp,early=start_drill(root,port)
    assert early is None
    html=resp.read().decode(); resp.close()
    assert html.lower().startswith('<!doctype html') and '<title>hashcards</title>' in html
    assert '<div class="question rich-text">' in html and '<div class="answer rich-text"></div>' in html
    assert 'value="Reveal"' in html and 'value="Undo"' in html and 'disabled' in html
    req=urllib.request.Request(f'http://127.0.0.1:{port}/',data=b'action=Reveal',method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
    r=urllib.request.urlopen(req); assert r.status in (200,); r.read()
    req=urllib.request.Request(f'http://127.0.0.1:{port}/',data=b'action=Good',method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
    r=urllib.request.urlopen(req); r.read()
    req=urllib.request.Request(f'http://127.0.0.1:{port}/',data=b'action=Shutdown',method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
    try:
        urllib.request.build_opener(NoRedirect).open(req,timeout=2)
        assert False
    except urllib.error.HTTPError as e:
        assert e.code==303 and e.headers.get('Location')=='/' and e.read()==b''
    proc.wait(timeout=5)
    assert proc.returncode==0
    con=sqlite3.connect(root/'hashcards.db')
    assert con.execute('select count(*) from sessions').fetchone()[0]==1
    assert con.execute('select grade from reviews').fetchone()[0]=='good'
    con.close()


def test_static_resources_assets_and_fonts(tmp_path):
    root=collection(tmp_path, {'d.md':'Q: q\nA: a\n'})
    port=18762; proc,resp,early=start_drill(root,port)
    assert early is None; resp.read(); resp.close()
    try:
        checks={'/style.css':(100,'text/css'),'/script.js':(100,'javascript'),'/katex/katex.css':(20000,'text/css'),'/katex/katex.js':(270000,'javascript'),'/katex/mhchem.js':(30000,'javascript')}
        for path,(minimum,ctype) in checks.items():
            r=urllib.request.urlopen(f'http://127.0.0.1:{port}{path}'); b=r.read()
            assert r.status==200 and len(b)>minimum
            assert ctype in r.headers.get('Content-Type','').lower()
            if path!='/script.js': assert 'public, max-age=604800, immutable' in r.headers.get('Cache-Control','')
        for stem in ['KaTeX_AMS-Regular','KaTeX_Caligraphic-Bold','KaTeX_Caligraphic-Regular','KaTeX_Fraktur-Bold','KaTeX_Fraktur-Regular','KaTeX_Main-Bold','KaTeX_Main-BoldItalic','KaTeX_Main-Italic','KaTeX_Main-Regular','KaTeX_Math-BoldItalic','KaTeX_Math-Italic','KaTeX_SansSerif-Bold','KaTeX_SansSerif-Italic','KaTeX_SansSerif-Regular','KaTeX_Script-Regular','KaTeX_Size1-Regular','KaTeX_Size2-Regular','KaTeX_Size3-Regular','KaTeX_Size4-Regular','KaTeX_Typewriter-Regular']:
            r=urllib.request.urlopen(f'http://127.0.0.1:{port}/katex/fonts/{stem}.woff2'); b=r.read()
            assert b and 'font/woff2' in r.headers.get('Content-Type','')
            assert 'public, max-age=604800, immutable' in r.headers.get('Cache-Control','')
            if stem=='KaTeX_Main-Regular': assert 20000<len(b)<35000
        for path in ['/katex/fonts/nope.woff2','/katex/fonts/KaTeX_Main-Regular.ttf','/katex/../style.css']:
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}{path}'); assert False
            except urllib.error.HTTPError as e: assert e.code==404
    finally:
        req=urllib.request.Request(f'http://127.0.0.1:{port}/',data=b'action=Shutdown',method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
        try: urllib.request.urlopen(req,timeout=2).read()
        except Exception: pass
        proc.wait(timeout=5)


def test_file_route_containment_types_and_unknown_routes(tmp_path):
    outside=tmp_path/'outside.png'; outside.write_bytes(b'outside')
    root=collection(tmp_path, {'d.md':'Q: q\nA: a\n','nested/a.png':b'pngbytes','file.odd':b'xx','link.png':b'placeholder'})
    (root/'sym.png').symlink_to(outside)
    port=18763; proc,resp,early=start_drill(root,port)
    assert early is None; resp.read(); resp.close()
    try:
        for path,ct,body in [('/file/nested/a.png','image/png',b'pngbytes'),('/file/file.odd','application/octet-stream',b'xx')]:
            r=urllib.request.urlopen(f'http://127.0.0.1:{port}{path}'); assert ct in r.headers.get('Content-Type','') and r.read()==body
        for path in ['/file/../outside.png','/file/%2e%2e/outside.png','/file/sym.png','/file/nested','/file/missing','/unknown']:
            try: urllib.request.urlopen(f'http://127.0.0.1:{port}{path}'); assert False
            except urllib.error.HTTPError as e:
                assert e.code==404
                if path.startswith('/file/'): assert e.read()==b'Not Found'
    finally:
        req=urllib.request.Request(f'http://127.0.0.1:{port}/',data=b'action=Shutdown',method='POST',headers={'Content-Type':'application/x-www-form-urlencoded'})
        try: urllib.request.urlopen(req,timeout=2).read()
        except Exception: pass
        proc.wait(timeout=5)
