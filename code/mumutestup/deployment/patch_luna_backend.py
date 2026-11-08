#!/usr/bin/env python3
"""Copy the MuMu source into an isolated tree and adapt its two chat clients.

Never edits the source tree or old results. The existing deployment patch is
applied only inside the new copy to retain Java, environment, and RAG fixes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


GUARD = '''"""Stop a batch when its local model adapter has a terminal failure."""
import os
from pathlib import Path


class LunaBackendFatal(BaseException):
    # Intentional control-flow exception: upstream catches Exception and otherwise
    # turns model-service failures into empty generated tests.
    pass


def check_luna_fatal():
    marker = os.getenv("MUMU_LLM_FATAL_FILE")
    if marker and Path(marker).is_file():
        raise LunaBackendFatal("Model adapter is unavailable; see the run's backend fatal marker")
'''


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(text, old, new, path):
    count = text.count(old)
    if count != 1:
        raise ValueError(f'{path}: expected one known patch anchor, found {count}')
    return text.replace(old, new, 1)


def source_ignore(source):
    def ignore(directory, names):
        ignored = {n for n in names if n in {
            '__pycache__', '.pytest_cache', '.mypy_cache', '.venv', 'venv',
            'node_modules', '.local-run.lock', '.env', 'auth.json',
        } or n.endswith(('.pyc', '.log'))}
        if Path(directory) == source:
            ignored.update(n for n in names if n == '.git' or n in {'runs', 'repos'}
                           or n.startswith(('logs', 'reports', 'index_data')))
        return ignored
    return ignore


def patch_files(root):
    config = root / 'config.py'
    text = config.read_text()
    text += '\n# Luna adapter accepts no temperature parameter. Record actual behavior.\nconfig.llm.temperature = None\n'
    config.write_text(text)

    main = root / 'llm/llm_client.py'
    text = main.read_text()
    text = replace_once(text, 'import requests\n',
                        'import requests\nfrom _luna_runtime_guard import check_luna_fatal\n', main)
    qwen = (
        '        # Local vLLM generation settings; preserve all agent prompts.\n'
        '        payload["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "8192"))\n'
        '        payload["chat_template_kwargs"] = {"enable_thinking": os.getenv("LLM_ENABLE_THINKING", "0").lower() in ("1", "true", "yes")}\n'
    )
    text = replace_once(text, qwen,
                        '        # Luna requests are handled by a persistent local Codex text adapter.\n', main)
    text = replace_once(text,
                        '        for attempt in range(self.max_retries + 1):\n',
                        '        for attempt in range(self.max_retries + 1):\n            check_luna_fatal()\n', main)
    text = replace_once(text, '        messages = []\n',
                        '        check_luna_fatal()\n        messages = []\n', main)
    text = replace_once(text,
                        '                    "messages": messages,\n                    "temperature": self.temperature\n',
                        '                    "messages": messages\n', main)
    text = replace_once(text,
                        '        except Exception as e:\n            self.logger.error(f"Generation failed: {e}")',
                        '        except Exception as e:\n            check_luna_fatal()\n            self.logger.error(f"Generation failed: {e}")', main)
    main.write_text(text)

    retrieval = root / 'index_retrieve_module_v3/pipeline/agent.py'
    text = retrieval.read_text()
    text = replace_once(text, 'import logging\n',
                        'import logging\nfrom _luna_runtime_guard import check_luna_fatal\n', retrieval)
    qwen = (
        '                kwargs["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "8192"))\n'
        '                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": os.getenv("LLM_ENABLE_THINKING", "0").lower() in ("1", "true", "yes")}}\n'
    )
    text = replace_once(text, qwen, '', retrieval)
    text = replace_once(text,
                        '            base_url=base_url,\n            timeout=timeout\n',
                        '            base_url=base_url,\n            timeout=timeout,\n            max_retries=0\n', retrieval)
    text = replace_once(text,
                        '        for attempt in range(self.max_retries):\n',
                        '        for attempt in range(self.max_retries):\n            check_luna_fatal()\n', retrieval)
    text = replace_once(text,
                        '                    "messages": messages,\n                    "temperature": self.temperature\n',
                        '                    "messages": messages\n', retrieval)
    text = replace_once(text,
                        '            except Exception as e:\n                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")',
                        '            except Exception as e:\n                check_luna_fatal()\n                logger.warning(f"LLM call attempt {attempt + 1} failed: {e}")', retrieval)
    retrieval.write_text(text)
    (root / '_luna_runtime_guard.py').write_text(GUARD)

    paths = [config, main, retrieval, root / '_luna_runtime_guard.py']
    for path in paths:
        compile(path.read_text(), str(path), 'exec')
    for path in (main, retrieval):
        if 'chat_template_kwargs' in path.read_text() or 'LLM_MAX_TOKENS' in path.read_text():
            raise ValueError(f'Qwen-specific transport remains in {path}')
    return paths


def prepare(source, target):
    source, target = source.resolve(), target.resolve()
    if source == target or source in target.parents or target in source.parents:
        raise ValueError('Source and target must be separate, non-nested directories')
    if not (source / 'config.py').is_file() or not (source / 'dataset').is_dir():
        raise ValueError(f'Source is not a complete MuMuTestUp checkout: {source}')
    if target.exists():
        manifest_path = target / 'luna-backend-patches.json'
        if not manifest_path.is_file():
            raise ValueError(f'Refusing to alter an existing unmarked target: {target}')
        manifest = json.loads(manifest_path.read_text())
        if manifest.get('source') != str(source) or manifest.get('adapter') != 'codex-app-server-text-adapter':
            raise ValueError('Existing isolated source has different provenance')
        for entry in manifest['patched_files']:
            path = target / entry['path']
            if not path.is_file() or digest(path) != entry['sha256']:
                raise ValueError(f'Existing Luna source has changed: {path}')
        # In this repository models/ contains Python dataclasses, not LLM weights.
        # Repair copies prepared by the earlier overly broad artifact filter.
        models_source, models_target = source / 'models', target / 'models'
        if not (models_target / '__init__.py').exists():
            if models_target.exists() or not (models_source / '__init__.py').is_file():
                raise ValueError('Unexpected or incomplete MuMu models source directory')
            shutil.copytree(models_source, models_target, ignore=source_ignore(source))
            manifest['restored_source_modules'] = [
                {'path': str(p.relative_to(target)), 'sha256': digest(p)}
                for p in sorted(models_target.rglob('*.py'))
            ]
            manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        print(json.dumps({'state': 'already_prepared', 'target': str(target)}))
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=target.name + '.preparing-', dir=target.parent))
    try:
        shutil.copytree(source, stage, dirs_exist_ok=True, ignore=source_ignore(source))
        original_paths = ['config.py', 'llm/llm_client.py', 'index_retrieve_module_v3/pipeline/agent.py']
        before = {name: digest(source / name) for name in original_paths}
        helper = Path(__file__).with_name('patch_upstream.py')
        subprocess.run([sys.executable, str(helper), str(stage)], check=True, capture_output=True, text=True)
        patched = patch_files(stage)
        sha = (subprocess.run(['git', '-C', str(source), 'rev-parse', 'HEAD'], capture_output=True, text=True)
               if (source / '.git').exists() else None)
        manifest = {
            'created_at': datetime.now(timezone.utc).isoformat(),
            'source': str(source),
            'target': str(target),
            'source_commit': sha.stdout.strip() if sha is not None and sha.returncode == 0 else None,
            'source_file_sha256': before,
            'adapter': 'codex-app-server-text-adapter',
            'model': 'gpt-6-luna',
            'temperature': None,
            'reasoning_effort': 'medium',
            'speed': 'standard',
            'embedding': 'Existing independent CPU all-MiniLM-L6-v2; remains enabled.',
            'protocol': 'Original method-level update inside new-version test class.',
            'patched_files': [{'path': str(p.relative_to(stage)), 'sha256': digest(p)} for p in patched],
            'validation': 'Python syntax checked; successful inference and Java execution are separate validations.',
        }
        (stage / 'luna-backend-patches.json').write_text(json.dumps(manifest, indent=2) + '\n')
        stage.rename(target)
        print(json.dumps({'state': 'prepared', 'target': str(target), 'manifest': str(target / 'luna-backend-patches.json')}))
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--target', type=Path, required=True)
    args = parser.parse_args()
    prepare(args.source, args.target)


if __name__ == '__main__':
    main()
