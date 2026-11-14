import os, re, subprocess, time, pty, select, signal
from pathlib import Path
import pytest

EXE = '/workspace/executable'
MODULES = 'ansible bootlog botnet bruteforce cargo cc composer cryptomining docker_build docker_image_rm download julia kernel_compile memdump mkinitcpio rkhunter simcity terraform uv weblog wpt'.split()

def run(*args, timeout=12, env=None):
    e=os.environ.copy(); e.update(env or {})
    try:
        p=subprocess.run([EXE,*map(str,args)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, env=e)
        return p.returncode,p.stdout.decode('utf-8','replace'),p.stderr.decode('utf-8','replace')
    except subprocess.TimeoutExpired as x:
        return 124,(x.stdout or b'').decode('utf8','replace'),(x.stderr or b'').decode('utf8','replace')

def clean(s):
    return re.sub(r'\x1b\[[0-?]*[ -/]*[@-~]', '', s).replace('\r','\n')

def terminal(*args, timeout=10, env=None):
    e=os.environ.copy(); e.update(env or {})
    master, slave=pty.openpty()
    p=subprocess.Popen([EXE,*map(str,args)],stdin=slave,stdout=slave,stderr=slave,env=e,close_fds=True)
    os.close(slave); out=bytearray(); end=time.monotonic()+timeout
    while time.monotonic()<end:
        ready,_,_=select.select([master],[],[],min(.1,max(0,end-time.monotonic())))
        if ready:
            try: out.extend(os.read(master,65536))
            except OSError: break
        if p.poll() is not None:
            # Drain bytes already written.
            while True:
                r,_,_=select.select([master],[],[],.02)
                if not r: break
                try: out.extend(os.read(master,65536))
                except OSError: break
            break
    if p.poll() is None: p.kill(); p.wait()
    os.close(master)
    return p.returncode,clean(out.decode('utf8','replace'))

def saved(s): assert 'Saving work to disk...' in s

def test_version_short_and_long():
    for opt in ('--version','-V'):
        rc,out,err=run(opt); assert (rc,out,err)==(0,'genact 1.5.1\n','')

def test_list_modules_order_and_precedence():
    rc,out,err=run('-l','-m','cc'); assert rc==0 and err==''
    assert out=='Available modules:\n'+''.join('  '+m+'\n' for m in MODULES)
    assert run('--list-modules')[1]==out

def test_help_width_80_and_alias():
    rc,a,err=run('--help',env={'COLUMNS':'80'}); rc2,b,err2=run('-h',env={'COLUMNS':'80'})
    assert rc==rc2==0 and err==err2=='' and a==b
    assert 'Usage: executable [OPTIONS]' in a and 'possible values: ansible, bootlog, botnet,' in a
    assert 'docker_image_rm, download, julia, kernel_compile, memdump, mkinitcpio,' in a

def test_help_width_120_wraps_values_differently():
    _,a,_=run('--help',env={'COLUMNS':'80'}); _,b,_=run('--help',env={'COLUMNS':'120'})
    assert a!=b and 'cargo, cc, composer,\n          cryptomining' in b

def test_valid_module_names_and_repeated_module_values():
    rc,out,err=run('-m','cc','-m','cc','-s','100000','--exit-after-modules','2',timeout=4)
    assert rc==0 and err=='' and len(re.findall(r'(?:gcc|clang) -c ',out))>=100
    saved(out)

def test_comma_value_is_not_split():
    rc,out,err=run('-m','cc,bootlog')
    assert rc!=0 and out=='' and "invalid value 'cc,bootlog'" in err

def test_speed_factor_validation():
    for v in ('0','0.005'):
        rc,out,err=run('--speed-factor',v)
        assert rc!=0 and out=='' and f"invalid value '{v}'" in err and 'Speed factor must be larger than 0.01' in err
    rc,out,err=run('--speed-factor','abc'); assert rc!=0 and out=='' and 'invalid float literal' in err

def test_integer_and_duration_validation():
    cases=[(('--instant-print-lines','abc'),'invalid digit found in string'),(('--exit-after-modules','xyz'),'invalid digit found in string'),(('--exit-after-modules','0'),'Must be larger than 0'),(('--exit-after-time','invalid'),'expected number at 0')]
    for args,part in cases:
        rc,out,err=run(*args); assert rc!=0 and out=='' and part in err

def test_missing_values_and_unknown_option():
    for opt in ('--speed-factor','--exit-after-time','--modules','--print-completions'):
        rc,out,err=run(opt); assert rc!=0 and out=='' and 'value is required' in err
    rc,out,err=run('--unknown-flag'); assert rc!=0 and out=='' and "unexpected argument '--unknown-flag'" in err

def test_invalid_module_and_completion_shell():
    rc,out,err=run('-m','kernel_compile,does_not_exist'); assert rc!=0 and out=='' and "invalid value 'kernel_compile,does_not_exist'" in err and "similar value exists: 'kernel_compile'" in err
    rc,out,err=run('--print-completions','tcsh'); assert rc==2 and out=='' and "similar value exists: 'zsh'" in err

@pytest.mark.parametrize('shell', ['bash','zsh','fish','elvish','powershell'], ids=['bash','zsh','fish','elvish','powershell'])
def test_completion_scripts(shell):
    rc,out,err=run('--print-completions',shell)
    assert rc==0 and err=='' and out
    assert 'genact' in out and ('ansible' in out or shell in ('elvish','powershell'))
    assert out.endswith('\n')

def test_manpage():
    rc,out,err=run('--print-manpage'); assert rc==0 and err==''
    for marker in ('.TH genact 1', '.SH NAME', '.SH SYNOPSIS', '.SH OPTIONS', 'docker_image_rm', '.SH AUTHORS'):
        assert marker in out

def test_zero_time_exit_and_save():
    rc,out,err=run('-m','cc','--exit-after-time','0s',timeout=3)
    assert rc==0 and err==''; saved(out)

def test_instant_print_lines_are_immediate():
    start=time.monotonic(); rc,out,err=run('-m','cc','-s','0.01','-i','50','--exit-after-time','100ms',timeout=2)
    elapsed=time.monotonic()-start
    assert rc==0 and err=='' and len(re.findall(r'(?:gcc|clang) -c ',out))>=51 and elapsed<2

def test_cc_compile_command_shape():
    rc,out,err=run('-m','cc','-s','999999999','--exit-after-modules','1',timeout=5)
    assert rc==0 and err==''; lines=[x for x in out.splitlines() if re.match(r'(?:gcc|clang) -c ',x)]
    assert len(lines)>=100
    for line in lines:
        assert line.count(' -c ')==1 and line.count(' -o ')==1 and line.endswith('.o')
    first=lines[:30]
    assert all(re.search(r'-I(?:drivers|arch|sound|net|fs|kernel|lib|security|tools)/',x) for x in first)
    assert len(set(re.findall(r' -o ((?:drivers|sound|net|fs|lib|kernel|tools)/)', '\n'.join(lines))))>=3
    saved(out)

def test_bootlog_records_and_ansi():
    rc,out=terminal('-m','bootlog','-s','100','--exit-after-modules','1',timeout=12)
    s=out; records=[x for x in s.splitlines() if x.strip()]
    assert rc==0 and 50<=len(records)<=200 and '\x1b[' in out
    assert sum(t in s for t in ('ACPI','CPU','kernel','zone','memory','PCI','IRQ'))>=3
    assert len(re.findall(r'0x[0-9a-fA-F]+',s))>=5; saved(s)

def test_memdump_structure():
    rc,out=terminal('-m','memdump','-s','10000','--exit-after-modules','1',timeout=5); s=out
    pat=re.compile(r'^([0-9a-f]{16})  ((?:[0-9a-f]{2} ){8}) ((?:[0-9a-f]{2} ){8})\|(.{16})\|$')
    rows=[pat.match(x) for x in s.splitlines()]; rows=[x for x in rows if x]
    assert rc==0 and len(rows)>=50
    addresses=[int(x.group(1),16) for x in rows]
    assert all(a%16==0 for a in addresses) and all(b-a==16 for a,b in zip(addresses,addresses[1:]))
    assert any(re.search(r'[A-Za-z0-9]',x.group(4)) for x in rows); saved(s)

def test_weblog_records():
    rc,out=terminal('-m','weblog','-s','10000','--exit-after-modules','1',timeout=5); s=out
    rows=[x for x in s.splitlines() if re.match(r'\S+ - - \[',x)]
    assert rc==0 and len(rows)>=10
    for x in rows:
        assert re.match(r'[^ ]+ - - \[[^]]+\] "GET /[^ ]+ HTTP/1\.0" (200|201|400|401|403|404|500|502|503) \d+ "[^"]*" ".+"$',x)
    assert sum(bool(re.search(r'\.(?:html|php|jpg|png|css|js|txt|gif|ico|xml)',x)) for x in rows)>=5; saved(s)

def test_cargo_phases_ansi():
    rc,out=terminal('-m','cargo','-s','10000','--exit-after-modules','1',timeout=8); s=clean(out)
    downloads=re.findall(r'Downloading ([\w.-]+) v(\d+\.\d+\.\d+)',s)
    compiles=re.findall(r'Compiling ([\w.-]+) v(\d+\.\d+\.\d+)',s)
    assert rc==0 and len(downloads)>=10 and downloads==compiles
    assert 'Finished release [optimized] target(s) in ' in s and '\x1b[1;32m' in out; saved(s)

def test_composer_packages_and_order():
    rc,out=terminal('-m','composer','-s','10000','--exit-after-modules','1',timeout=8); s=clean(out)
    assert rc==0 and 'Loading composer repositories with package information' in s and 'Updating dependencies (including require-dev)' in s
    lines=re.findall(r'^  - Installing ([a-z0-9._-]+/[a-z0-9._-]+) \((\d+\.\d+\.\d+)\): Loading from cache$',s,re.M)
    assert 10<=len(lines)<=100 and len(set(x[0] for x in lines))==len(lines)
    assert s.index('Writing lock file')>s.index(lines[-1][0]) if lines else False
    assert 'Generating autoload files' in s and '\x1b[32m' in out and '\x1b[33m' in out; saved(s)

def test_kernel_compile_layout():
    rc,out=terminal('-m','kernel_compile','-s','100000','--exit-after-modules','1',timeout=6); s=out
    paths=re.findall(r'\b((?:drivers|kernel|fs|arch|net|mm|security|crypto|sound)/[^\s]+\.o)',s)
    assert rc==0 and len(paths)>=10 and len(set(x.split('/')[0] for x in paths))>=2
    assert re.search(r'^  CC      \S+\.o$',s,re.M)
    assert re.search(r'^BUILD   arch/\w+/boot/bzImage\n\nSetup is \d+ bytes \(padded to \d+ bytes\)\.\nSystem is \d+ kB\nCRC [0-9a-f]+\nKernel: arch/\w+/boot/bzImage is ready \(#1\)$',s,re.M); saved(s)

def test_mkinitcpio_ordered_hooks():
    rc,out=terminal('-m','mkinitcpio','-s','10000','--exit-after-modules','1',timeout=6); s=out
    hooks=['base','udev','autodetect','modconf','block','fsck','filesystems']
    assert rc==0 and all(f'[{x}]' in s for x in hooks)
    assert [s.index(f'[{x}]') for x in hooks]==sorted(s.index(f'[{x}]') for x in hooks)
    assert 'Generating module dependencies' in s and 'Image generation successful' in s; saved(s)

def test_terraform_normal_two_invocations():
    rc,out=terminal('-m','terraform','-s','10000','-i','999999999','--exit-after-modules','2',timeout=8); s=out
    assert rc==0 and s.count('Acquiring state lock.')==2 and 'Apply complete!' not in s and s.count('Saving work to disk...')==1
    assert len(re.findall(r'\b(?:aws|azurerm|google)_[a-z0-9_]+\.\w+',s))>=5

def test_terraform_time_interruption_summary():
    rc,out=terminal('-m','terraform','-s','10000','--exit-after-time','100ms',timeout=5); s=out
    assert rc==0 and re.search(r'Apply complete! Resources: \d+ added, \d+ changed, \d+ destroyed\.',s); saved(s)

def test_bruteforce_hash_matches_and_rainbow():
    rc,out=terminal('-m','bruteforce','-s','10000','--exit-after-modules','1',timeout=8); s=out
    assert rc==0 and '=> Hashes to decrypt' in s and '=> Match found' in s
    hashes=re.findall(r'^  ([0-9a-f]{64})$',s,re.M); results=re.findall(r'^  ([0-9a-f]{64}):[a-z]+\d{2}$',s,re.M)
    assert 2<=len(hashes)<=10 and results==hashes
    assert len(re.findall(r'=> Extracting Rainbow Table \[.*=+.*\]',s))>=3 and '\x1b[38;5;' in out; saved(s)

def test_botnet_clusters_and_counter_total():
    rc,out=terminal('-m','botnet','-s','10000','--exit-after-modules','1',timeout=8); s=out
    boot=re.findall(r'^  Cluster #(\d{2}) \((\d{3}) nodes\) \[booting\]$',s,re.M)
    online=re.findall(r'^  Cluster #(\d{2}) \((\d{3}) nodes\) \[online\]$',s,re.M)
    assert rc==0 and 8<=len(boot)<=16 and len(online)==len(boot)
    total=sum(int(n) for _,n in boot); assert re.search(rf'Establishing connections: {total}/{total}',s)
    assert all(x in s for x in ('+ Synchronizing clocks... [done]','+ Sending login information... [done]','+ Sending command... [done]','>> Botnet update complete.')); saved(s)

def test_cryptomining_line_format():
    rc,out=terminal('-m','cryptomining','-s','10000','--exit-after-modules','1',timeout=8); s=out
    pat=r'^  m  (?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d\|cryptominer  Speed  (?:\d+(?:\.\d+)?) Mh/s    gpu/\d+ \d+(?:\.\d+)?   \[\d+\+\d+:\d+\+\d+:\d+\] Time: [0-5]\d:[0-5]\d$'
    assert rc==0 and len(re.findall(pat,s,re.M))>=5 and len(s.splitlines())>=100; saved(s)

def test_docker_image_deletions():
    rc,out=terminal('-m','docker_image_rm','-s','10000','--exit-after-modules','1',timeout=8); s=out
    assert rc==0 and len(re.findall(r'^Untagged: [a-z0-9_/-]+:[a-z0-9_.-]+$',s,re.M))>=20
    deletions=re.findall(r'^Deleted: sha256:([0-9a-f]{64})$',s,re.M); assert len(deletions)>=100
    assert any(x in s for x in ('nginx','alpine','ubuntu','redis','postgres')); saved(s)

def test_julia_workflow():
    rc,out=terminal('-m','julia','-s','10000','--exit-after-modules','1',timeout=8); s=out
    for x in ('Documentation: https://docs.julialang.org','Type "?" for help, "]?" for Pkg help.','Fedora 35 build','Resolving package versions...','Precompiling project...','already precompiled','Project.toml','Manifest.toml'):
        assert x in s
    assert re.search(r'Version \d+\.\d+\.\d+ \(\d{4}-\d{2}-\d{2}\)',s) and s.count('Progress')>=2; saved(s)

def test_uv_resolve_prepare_install():
    rc,out=terminal('-m','uv','-s','10000','--exit-after-modules','1',timeout=8); s=out
    assert rc==0 and re.search(r'Using CPython \d+\.\d+\.\d+',s) and 'Creating virtualenv at: .venv' in s
    assert len(re.findall(r'^[a-z][a-z0-9_-]*==\d+\.\d+\.\d+$',s,re.M))>=10
    assert re.search(r'Resolved (?:[5-9]\d|\d{3,}) packages in ',s) and 'Prepared ' in s and 'Installed ' in s; saved(s)

def test_rkhunter_identity_and_checks():
    rc,out=terminal('-m','rkhunter','-s','10000','--exit-after-modules','1',timeout=8); s=out
    assert rc==0 and re.search(r'Running Rootkit Hunter version \d+\.\d+\.\d+ on localhost',s)
    assert re.search(r'Found O/S name: Ubuntu \d+\.\d+\.\d+',s)
    assert "Info: Using configuration file '/etc/rkhunter.conf'" in s and 'checks' in s
    assert len(re.findall(r'^Checking for ',s,re.M))>=2 and re.search(r'\[ (?:Not found|Found|Skipped) \]',s); saved(s)

def test_simcity_task_updates():
    rc,out=terminal('-m','simcity','-s','10000','--exit-after-modules','1',timeout=12); s=out
    rows=re.findall(r'^\[o\] (.+?) (OK|SUCCESS|YES|FAIL)$',s,re.M)
    assert rc==0 and len(rows)>=5 and len(s)>500
    assert len({d for d,_ in rows})>=5
    assert len(set(d.split()[0] for d,_ in rows)&set('Reticulating Adding Adjusting Generating Polyfilling Pixelating Populating Hiding Applying Removing'.split()))>=3; saved(s)

def test_wpt_high_volume_records_and_failures():
    rc,out=terminal('-m','wpt','-s','10000','--exit-after-modules','1',timeout=10); s=out
    assert rc==0 and re.search(r'Running (?:[5-9]\d{3}|[12]\d{4}|30000) tests in web-platform-tests',s)
    paths=re.findall(r'/(?:css|html|dom|fetch|encoding|workers|webdriver)/[a-z0-9/-]+/test-\d+\.html',s)
    assert len(paths)>=10 and len(s)>1000 and s.count('/')>=100
    assert all(x in s for x in ('PASS','FAIL','ERROR','TIMEOUT','assert_equals: expected','assert_true: expected','http://web-platform.test:8000/resources/testharness.js'))
    assert len(re.findall(r'^    [│└]   at ',s,re.M))>=10

def test_inhibit_warning_before_activity():
    rc,out=terminal('-m','bootlog','--inhibit','-s','10000','--exit-after-modules','1',timeout=8); s=out
    warning='WARN: failed to set up idle inhibition: system: I/O error: No such file or directory (os error 2)'
    assert rc==0 and warning in s and s.index(warning)<s.index('Saving work to disk...')

def test_download_terminal_progress():
    rc,out=terminal('-m','download','-s','50','--exit-after-modules','1',timeout=6); s=out
    completed=[x for x in s.splitlines() if '100%[================' in x]
    assert rc==0 and len(completed)>=2
    assert all(re.search(r'100%\[=+\].*(?:B/s|KiB/s|MiB/s).*eta [0-9]+s',x) for x in completed)
    assert any(re.search(r'\d+(?:\.\d+)?MiB/s',x) for x in completed); saved(s)

def test_docker_build_terminal_progress():
    rc,out=terminal('-m','docker_build','-s','10000','--exit-after-modules','1',timeout=10); s=out
    assert rc==0 and re.search(r'Step \d+/\d+',s) and ('Successfully built' in s or 'Successfully tagged' in s)
    saved(s)

def test_ansible_tasks_and_hosts():
    rc,out=terminal('-m','ansible','-s','100','--exit-after-modules','1',timeout=6); s=out
    assert rc==0 and len(re.findall(r'^TASK \[\w+ : .+\] \*{10,}$',s,re.M))>=1
    hosts=re.findall(r'^(?:ok|changed|failed|skipping): \[([0-9a-fA-F:.]+)\]',s,re.M)
    assert len(set(hosts))>=5 and len(re.findall(r'^ok: \[',s,re.M))>=5
    assert re.search(r'^(?:changed|failed|skipping): \[',s,re.M)

def test_bruteforce_time_limited_partial_output():
    rc,out=terminal('-m','bruteforce','-s','100','--exit-after-time','200ms',timeout=3); s=out
    assert rc==0 and '=> Hashes to decrypt' in s and '=> Extracting Rainbow Table' in s
    assert re.search(r'  [0-9a-f]{64}',s); saved(s)

def test_terraform_resources_have_provider_and_operations():
    rc,out=terminal('-m','terraform','-s','10000','--exit-after-modules','1',timeout=8); s=out
    assert rc==0 and s.startswith('Acquiring state lock.')
    types=re.findall(r'\b(?:aws|azurerm|google)_[a-z0-9_]+\.\w+',s)
    assert len(set(types))>=5
    ops=['Creating...','Still creating...','Creation complete after','Modifying...','Still modifying...','Modifications complete after','Destroying...','Destruction complete after','Refreshing state...']
    assert sum(op in s for op in ops)>=2 and len(re.findall(r'(?:after \d+s|\[\d+s elapsed\])',s))>=2
    assert re.search(r'\[id=\w+\]',s) and 'Apply complete!' not in s; saved(s)
