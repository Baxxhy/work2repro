import os
import subprocess
from pathlib import Path

import pytest


EXE = Path('/workspace/executable')


@pytest.fixture
def envbox(tmp_path):
    """Isolated HOME/config and helpers for exercising the installed CLI."""
    home = tmp_path / 'home'
    home.mkdir()
    root = tmp_path / 'sheets'
    root.mkdir()
    conf = tmp_path / 'conf.yml'
    state = {'home': home, 'root': root, 'conf': conf}

    def config(paths=None, **extra):
        paths = paths if paths is not None else [('test', root, False, [])]
        lines = ['---', 'editor: /bin/true', 'colorize: false', 'style: bw',
                 'formatter: terminal', 'pager: ""', 'cheatpaths:']
        for name, path, readonly, tags in paths:
            lines += [f'  - name: {name}', f'    path: {path}',
                      f'    readonly: {str(readonly).lower()}']
            if tags:
                lines.append('    tags: [' + ', '.join(str(x) for x in tags) + ']')
        for key, value in extra.items():
            lines.append(f'{key}: {value}')
        conf.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        return conf

    def run(*args, input=None, cwd=None, overrides=None):
        e = os.environ.copy()
        for k in ('CHEAT_CONFIG_PATH', 'XDG_CONFIG_HOME', 'VISUAL', 'EDITOR', 'PAGER'):
            e.pop(k, None)
        e.update({'HOME': str(home), 'CHEAT_CONFIG_PATH': str(conf)})
        if overrides:
            e.update({k: str(v) for k, v in overrides.items()})
        return subprocess.run([str(EXE), *map(str, args)], input=input,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              cwd=cwd or tmp_path, env=e, timeout=15)

    state.update(config=config, run=run)
    return state


def sheet(path, title, body, front=None):
    target = Path(path) / title
    target.parent.mkdir(parents=True, exist_ok=True)
    data = body
    if front is not None:
        data = b'---\n' + front + b'\n---\n' + body
    target.write_bytes(data if isinstance(data, bytes) else data.encode('utf-8'))
    return target
