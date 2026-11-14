import os
import subprocess
from pathlib import Path
import pytest

EVAL = Path(__file__).resolve().parent
EXECUTABLE = Path(os.environ.get('GIT_TRIM_EXECUTABLE', '/workspace/executable'))

@pytest.fixture
def repo(tmp_path):
    class Repo:
        path = tmp_path / 'repo'
        def git(self, *args, check=True, input=None):
            p = subprocess.run(['git', *map(str,args)], cwd=self.path, text=True, input=input, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if check and p.returncode:
                raise AssertionError(f'git {args} failed: {p.stderr}')
            return p
        def init(self, bare=False):
            self.path.mkdir(parents=True, exist_ok=True)
            self.git('init', '--bare' if bare else '-q', check=False)
            if not bare:
                self.git('config','user.email','test@example.invalid')
                self.git('config','user.name','Test User')
            return self
        def config(self,*args): return self.git('config',*args)
        def commit(self, name='file', content='x', subject='commit'):
            p=self.path/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(content)
            self.git('add','--',name); self.git('commit','-m',subject)
            return self.git('rev-parse','HEAD').stdout.strip()
        def run(self,*args,input=None):
            return subprocess.run([str(EXECUTABLE),*args],cwd=self.path,text=True,input=input,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return Repo()

@pytest.fixture
def outside(tmp_path):
    return tmp_path

@pytest.fixture(autouse=True)
def isolated_git_config(monkeypatch, tmp_path):
    monkeypatch.setenv('GIT_CONFIG_NOSYSTEM','1')
    monkeypatch.setenv('GIT_CONFIG_GLOBAL',str(tmp_path/'global.gitconfig'))
    monkeypatch.setenv('GIT_TERMINAL_PROMPT','0')
