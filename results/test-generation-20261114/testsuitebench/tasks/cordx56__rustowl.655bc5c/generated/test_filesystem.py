import os
import re
import subprocess
from pathlib import Path

EXE = Path('/workspace/executable')
NIGHTLY = 'nightly-2025-06-20-x86_64-unknown-linux-gnu'

def invoke(*args, cwd, home, timeout=20):
    env = os.environ.copy()
    env.update({'HOME':str(home), 'RUST_LOG':'off'})
    return subprocess.run([str(EXE),*args],cwd=cwd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)

def put(path, data=b'x'):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(data)

def test_clean_removes_only_owl_deep_tree(tmp_path):
    project=tmp_path/'project'; home=tmp_path/'home'
    put(project/'Cargo.toml',b'[package]\nname="p"\nversion="0.1.0"\n')
    put(project/'src/lib.rs',b'pub fn f() {}')
    put(project/'target/owl/a/b/deep',b'delete')
    put(project/'target/debug/keep',b'debug')
    put(project/'target/release/keep',b'release')
    p=invoke('clean',cwd=project,home=home)
    assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'')
    assert not (project/'target/owl').exists()
    assert (project/'target/debug/keep').read_bytes()==b'debug'
    assert (project/'target/release/keep').read_bytes()==b'release'
    assert (project/'Cargo.toml').exists() and (project/'src/lib.rs').exists()
    assert invoke('clean',cwd=project,home=home).returncode==0

def test_clean_manifest_without_source_is_noop(tmp_path):
    project=tmp_path/'p'; put(project/'Cargo.toml',b'[package]\nname="p"\nversion="0.1.0"\n'); put(project/'target/owl/keep')
    p=invoke('clean',cwd=project,home=tmp_path/'home')
    assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'')
    assert (project/'target/owl/keep').exists()

def test_clean_without_manifest_is_noop(tmp_path):
    project=tmp_path/'p'; put(project/'target/owl/keep')
    p=invoke('clean',cwd=project,home=tmp_path/'home')
    assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'') and (project/'target/owl/keep').exists()

def test_uninstall_absent_is_silent_and_idempotent(tmp_path):
    home=tmp_path/'home'; home.mkdir()
    for _ in range(2):
        p=invoke('toolchain','uninstall',cwd=tmp_path,home=home)
        assert (p.returncode,p.stdout,p.stderr)==(0,b'',b'')

def test_uninstall_removes_managed_tree_with_log_even_quiet(tmp_path):
    home=tmp_path/'home'; root=home/'.rustowl/sysroot'/NIGHTLY
    put(root/'lib/rustlib/nested/file')
    p=invoke('-qqq','toolchain','uninstall',cwd=tmp_path,home=home)
    assert p.returncode==0 and p.stdout==b''
    assert not root.exists()
    assert re.fullmatch(rb'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z INFO  \[rustowl::toolchain\] remove sysroot: '+re.escape(str(root).encode())+b'\n',p.stderr)
    again=invoke('toolchain','uninstall',cwd=tmp_path,home=home)
    assert (again.returncode,again.stdout,again.stderr)==(0,b'',b'')

def test_check_invalid_file_runtime_error_survives_quiet(tmp_path):
    home=tmp_path/'home'; sysroot=home/'.rustowl/sysroot'/NIGHTLY; sysroot.mkdir(parents=True)
    target=tmp_path/'plain.rs'; target.write_text('fn main() {}')
    p=invoke('-q','check',str(target),cwd=tmp_path,home=home)
    assert p.returncode==1 and p.stdout==b''
    assert b'Invalid analysis target:' in p.stderr and str(target).encode() in p.stderr and b'Analyze failed' in p.stderr

def test_check_after_double_dash_treats_help_as_path(tmp_path):
    home=tmp_path/'home'; (home/'.rustowl/sysroot'/NIGHTLY).mkdir(parents=True)
    p=invoke('check','--','--help',cwd=tmp_path,home=home)
    assert p.returncode==1 and p.stdout==b''
    assert b'Invalid analysis target: --help' in p.stderr and b'Analyze failed' in p.stderr

def test_install_existing_regular_file_is_runtime_error(tmp_path):
    home=tmp_path/'home'; target=tmp_path/'not-dir'; target.write_bytes(b'preserve')
    p=invoke('toolchain','install','--path',str(target),cwd=tmp_path,home=home)
    assert p.returncode==1 and p.stdout==b'' and target.read_bytes()==b'preserve'
    assert re.fullmatch(rb'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z '+(Path('/workspace/exact-output/errors/toolchain/error_install_invalid_path.golden').read_bytes()),p.stderr)
