import os
import re
import subprocess
import zipfile
from pathlib import Path
import pytest

HELP = """Find the password of protected ZIP files

Usage: executable [OPTIONS] --inputFile <inputFile>

Options:
  -i, --inputFile <inputFile>                    path to zip input file
  -w, --workers <workers>                        number of workers
  -p, --passwordDictionary <passwordDictionary>  path to a password dictionary file
  -c, --charset <charset>                        charset to use to generate password [default: lud]
      --charsetFile <charsetFile>                path to a charset file
      --minPasswordLen <minPasswordLen>          minimum password length [default: 1]
      --maxPasswordLen <maxPasswordLen>          maximum password length [default: 10]
      --fileNumber <fileNumber>                  file number in the zip archive [default: 0]
  -s, --startingPassword <startingPassword>      password to start from
  -h, --help                                     Print help
  -V, --version                                  Print version
"""

def run(exe,*args,env=None,timeout=10):
    return subprocess.run([str(exe),*map(str,args)],capture_output=True,env=env,timeout=timeout)

@pytest.mark.parametrize('flag', ['--help','-h'],ids=['long-help','short-help'])
def test_help(exe,flag):
    p=run(exe,flag); assert p.returncode==0 and p.stdout.decode()==HELP and p.stderr==b''

@pytest.mark.parametrize('flag', ['--version','-V'],ids=['long-version','short-version'])
def test_version(exe,flag):
    p=run(exe,flag); assert p.returncode==0 and p.stdout==b'zip-password-finder 0.10.3\n' and p.stderr==b''

def test_missing_input_exact_and_home_independent(exe,tmp_path):
    expected=("error: the following required arguments were not provided:\n  --inputFile <inputFile>\n\n"
              "Usage: executable --inputFile <inputFile>\n\nFor more information, try '--help'.\n").encode()
    for home in ('/missing/home/a',str(tmp_path)):
        env=os.environ.copy(); env.update(HOME=home,XDG_CONFIG_HOME=home,XDG_DATA_HOME=home,XDG_CACHE_HOME=home,INPUT_FILE='/tmp/a')
        p=run(exe,env=env); assert p.returncode==2 and p.stdout==b'' and p.stderr==expected

def test_required_input_usage_with_other_option(exe):
    p=run(exe,'--workers','2'); assert p.returncode==2 and p.stdout==b''
    assert b'Usage: executable --inputFile <inputFile> --workers <workers>' in p.stderr

@pytest.mark.parametrize('bad', ['--notARealOption','--config','add'],ids=['unknown','config','positional'])
def test_reject_unknown_and_positionals(exe,tmp_path,bad):
    pth=tmp_path/'a'; pth.write_bytes(b'x'); p=run(exe,'--inputFile',pth,bad)
    assert p.returncode==2 and p.stdout==b'' and f"unexpected argument '{bad}'".encode() in p.stderr

def test_unknown_option_without_input_has_options_synopsis(exe):
    p=run(exe,'--config'); assert p.returncode==2 and b'Usage: executable [OPTIONS] --inputFile <inputFile>' in p.stderr

def test_missing_values_and_negative_start(exe,tmp_path):
    a=tmp_path/'a'; a.write_bytes(b'x')
    for opt in ('--inputFile','--workers','--passwordDictionary','--charset','--charsetFile','--minPasswordLen','--maxPasswordLen','--fileNumber','--startingPassword'):
        p=run(exe,opt); assert p.returncode==2 and b'a value is required for' in p.stderr and opt.encode() in p.stderr
    p=run(exe,'--inputFile',a,'--startingPassword','-x'); assert p.returncode==2 and p.stdout==b''

def test_integer_syntax_and_duplicate_option(exe,tmp_path):
    a=tmp_path/'a'; a.write_bytes(b'x')
    p=run(exe,'--inputFile',a,'--workers','foo'); assert p.returncode==2 and b"invalid value 'foo' for '--workers <workers>'" in p.stderr and b'invalid digit found in string' in p.stderr
    p=run(exe,'--inputFile',a,'--workers','9999999999999999999999999999'); assert p.returncode==2 and b'number too large to fit in target type' in p.stderr
    p=run(exe,'--inputFile',a,'--charset','l','--charset','d'); assert p.returncode==2 and b'--charset' in p.stderr and b'cannot be used multiple times' in p.stderr

@pytest.mark.parametrize('option,message', [
 ('--inputFile',"'inputFile' does not exist"),('--passwordDictionary',"'passwordDictionary' does not exist"),('--charsetFile',"'charsetFile' does not exist")],ids=['input','dictionary','charset-file'])
def test_missing_paths(exe,tmp_path,option,message):
    a=tmp_path/'valid.zip'; a.write_bytes(b'bad'); p=run(exe,'--inputFile',a,option,tmp_path/'missing')
    assert p.returncode==1 and p.stdout==b'' and p.stderr.decode()==f'CLI argument error - "{message}"\n'

def test_empty_path_and_directory_rejected(exe,tmp_path):
    for value in ('',tmp_path):
        p=run(exe,'--inputFile',value); assert p.returncode==1 and b"'inputFile' does not exist" in p.stderr and p.stdout==b''

@pytest.mark.parametrize('args,message', [
 (['--workers','0'],"'workers' must be positive"),(['--minPasswordLen','0'],"'minPasswordLen' must be positive"),
 (['--maxPasswordLen','0'],"'maxPasswordLen' must be positive"),(['--minPasswordLen','3','--maxPasswordLen','2'],"'maxPasswordLen' must be equal or greater than 'minPasswordLen'")],ids=['workers-zero','min-zero','max-zero','inverted-range'])
def test_numeric_semantic_validation(exe,tmp_path,args,message):
    a=tmp_path/'valid.zip'; a.write_bytes(b'bad'); p=run(exe,'--inputFile',a,*args)
    assert p.returncode==1 and p.stdout==b'' and p.stderr.decode()==f'CLI argument error - "{message}"\n'

def test_zip_structure_and_unencrypted_member(exe,tmp_path):
    for data in (b'plain text',b'',b'PK\x03\x04truncated'):
        pth=tmp_path/'bad.zip'; pth.write_bytes(data); p=run(exe,'--inputFile',pth)
        assert p.returncode==1 and p.stdout==b'' and p.stderr.decode()== 'Invalid zip file error - invalid Zip archive: Could not find EOCD\n'
    pth=tmp_path/'normal';
    with zipfile.ZipFile(pth,'w') as z: z.writestr('ordinary.txt','hello')
    p=run(exe,'--inputFile',pth)
    assert p.returncode==1 and p.stderr.decode()=='Invalid zip file error - the selected file in the archive is not encrypted (file_number:0 file_name:ordinary.txt)\n'

@pytest.mark.parametrize('index', [0,1,99,999],ids=['first','second','99','999'])
def test_member_index_validation(exe,tmp_path,index):
    pth=tmp_path/'empty.zip'
    with zipfile.ZipFile(pth,'w'): pass
    p=run(exe,'--inputFile',pth,'--fileNumber',index)
    assert p.returncode==1 and p.stdout==b'' and p.stderr.decode()==f"File number not found within archive error - '{index}'\n"

def test_equals_options_relative_and_space_path(exe,tmp_path):
    pth=tmp_path/'file with spaces.zip'
    with zipfile.ZipFile(pth,'w') as z: z.writestr('x','x')
    for form in ('--inputFile='+str(pth),'-i='+str(pth)):
        p=run(exe,form); assert p.returncode==1 and b'not encrypted' in p.stderr

def assert_search_output(p,expected):
    assert p.returncode==0 and p.stderr==b''
    lines=p.stdout.decode().splitlines()
    assert len(lines)==2 and re.fullmatch(r'Time elapsed: (?:[0-9]+(?:h|m|s|ms|us|ns))(?: [0-9]+(?:h|m|s|ms|us|ns))*',lines[0])
    assert lines[1]==expected

def test_dictionary_finds_exact_password_and_preserves_spaces(exe,zip_factory,tmp_path):
    archive=zip_factory([('secret','payload',True)],password=' pass ')
    d=tmp_path/'words'; d.write_text('wrong\n pass \nlast',encoding='utf8')
    p=run(exe,'--inputFile',archive,'--passwordDictionary',d,'--workers','4')
    assert_search_output(p,'Password found: pass ')

def test_dictionary_final_line_without_newline_and_long_entry(exe,zip_factory,tmp_path):
    target='z'*120
    archive=zip_factory([('secret','',True)],password=target)
    d=tmp_path/'words'; d.write_text('wrong\n'+target,encoding='utf8')
    p=run(exe,'--inputFile',archive,'--passwordDictionary',d,'--workers','8','--maxPasswordLen','1')
    assert_search_output(p,'Password found:'+target)

def test_dictionary_empty_and_exhaustion(exe,zip_factory,tmp_path):
    archive=zip_factory([('secret','payload',True)],password='yes')
    d=tmp_path/'empty'; d.write_bytes(b'')
    p=run(exe,'--inputFile',archive,'--passwordDictionary',d,'--workers','4')
    assert_search_output(p,'Password not found')

def test_bruteforce_order_charset_dedup_and_workers(exe,zip_factory,tmp_path):
    archive=zip_factory([('secret','payload',True)],password='ba')
    for workers in ('1','4','100'):
        p=run(exe,'--inputFile',archive,'--workers',workers,'--charset','baab','--minPasswordLen','2','--maxPasswordLen','2')
        assert_search_output(p,'Password found:ba')

def test_custom_charset_sorted_and_start_inclusive(exe,zip_factory,tmp_path):
    archive=zip_factory([('secret','payload',True)],password='cab')
    cs=tmp_path/'charset'; cs.write_text('cba',encoding='utf8')
    p=run(exe,'--inputFile',archive,'--charsetFile',cs,'--charset','x','--workers','4','--minPasswordLen','3','--maxPasswordLen','3','--startingPassword','cab')
    assert_search_output(p,'Password found:cab')

def test_start_after_target_exhausts(exe,zip_factory):
    archive=zip_factory([('secret','payload',True)],password='ab')
    p=run(exe,'--inputFile',archive,'--workers','4','--charset','ab','--minPasswordLen','2','--maxPasswordLen','2','--startingPassword','ba')
    assert_search_output(p,'Password not found')

@pytest.mark.parametrize('args,message', [
 (['--startingPassword','a'],"'startingPassword' cannot be used with a dictionary file"),
 (['--startingPassword','z'],"'startingPassword' uses characters out of the generation charset"),
 (['--startingPassword','aa','--minPasswordLen','1','--maxPasswordLen','1'],"'startingPassword' does not respect 'max_password_len' or 'min_password_len' configuration")],ids=['dictionary-conflict','charset-membership','length'])
def test_starting_password_validation(exe,zip_factory,tmp_path,args,message):
    archive=zip_factory([('secret','payload',True)],password='a')
    d=tmp_path/'d'; d.write_text('a')
    if args[1]=='a': opts=['--passwordDictionary',d]
    else: opts=['--charset','a']
    p=run(exe,'--inputFile',archive,*opts,*args)
    assert p.returncode==1 and p.stdout==b'' and p.stderr.decode()==f'CLI argument error - "{message}"\n'

def test_invalid_preset_and_empty_custom_charset(exe,zip_factory,tmp_path):
    archive=zip_factory([('secret','payload',True)],password='a')
    p=run(exe,'--inputFile',archive,'--charset','lx'); assert p.returncode==1 and b"Unknown charset option 'x'" in p.stderr
    cs=tmp_path/'empty'; cs.write_bytes(b'')
    p=run(exe,'--inputFile',archive,'--charsetFile',cs,'--workers','2','--maxPasswordLen','2')
    assert p.returncode==0 and b'panicked' in p.stderr and b'charset non empty' in p.stderr
