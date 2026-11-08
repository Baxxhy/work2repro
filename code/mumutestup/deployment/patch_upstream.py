#!/usr/bin/env python3
"""Apply auditable, idempotent local-backend adaptations to official MuMuTestUp.

No prompt, agent decision, coverage operator or mutation operator is replaced.
Original files are backed up once. Unknown source layouts fail before writing.
"""
import argparse
import hashlib
import json
from pathlib import Path


CONFIG = '''# Local deployment adaptation: environment-backed configuration.
config = Config()
from pathlib import Path as _DeploymentPath
_deployment_root = _DeploymentPath(os.getenv("MUMU_ROOT", str(_DeploymentPath(__file__).resolve().parent)))
config.java.repos_dir = os.getenv("MUMU_REPOS_DIR", str(_deployment_root / "repos"))
config.java.maven_home = os.getenv("MUMU_MAVEN_HOME", config.java.maven_home)
config.java.maven_repo_base = os.getenv("MUMU_MAVEN_REPO_BASE", str(_deployment_root / "maven-repositories"))
config.java.logs_base_dir = os.getenv("MUMU_LOGS_DIR", str(_deployment_root / "logs"))
config.java.reports_base_dir = os.getenv("MUMU_REPORTS_DIR", str(_deployment_root / "reports"))
config.java.test_timeout = int(os.getenv("MUMU_TEST_TIMEOUT", "6000"))
for _java_version in ("8", "11", "17", "21"):
    config.java.java_homes[_java_version] = os.getenv(
        "MUMU_JAVA_HOME_" + _java_version, config.java.java_homes[_java_version])
config.framework.max_iterations = int(os.getenv("MUMU_MAX_ITERATIONS", "4"))
config.framework.log_file = os.getenv("MUMU_FRAMEWORK_LOG", str(_deployment_root / "beam.log"))
'''


def replace_once(text, old, new, path):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError(f"{path}: expected exactly one known anchor; found {text.count(old)}")
    return text.replace(old, new, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    root = args.upstream.resolve()
    edits = {}

    def edit(path, old, new):
        full = root / path
        content = edits.get(full, full.read_text())
        edits[full] = replace_once(content, old, new, path)

    edit("config.py", "config = Config(llm=LLMConfig())", CONFIG.rstrip())
    edit("llm/llm_client.py", "import requests\n", "import requests\nimport os  # local deployment backend settings\n")
    edit("llm/llm_client.py",
         '        # Use custom API URL if provided, otherwise construct from base_url\n',
         '        # Local vLLM generation settings; preserve all agent prompts.\n'
         '        payload["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "8192"))\n'
         '        payload["chat_template_kwargs"] = {"enable_thinking": os.getenv("LLM_ENABLE_THINKING", "0").lower() in ("1", "true", "yes")}\n'
         '        # Use custom API URL if provided, otherwise construct from base_url\n')
    edit("index_retrieve_module_v3/pipeline/agent.py", "import logging\n", "import logging\nimport os  # local deployment backend settings\n")
    edit("index_retrieve_module_v3/pipeline/agent.py",
         '                response = self.client.chat.completions.create(**kwargs)\n',
         '                kwargs["max_tokens"] = int(os.getenv("LLM_MAX_TOKENS", "8192"))\n'
         '                kwargs["extra_body"] = {"chat_template_kwargs": {"enable_thinking": os.getenv("LLM_ENABLE_THINKING", "0").lower() in ("1", "true", "yes")}}\n'
         '                response = self.client.chat.completions.create(**kwargs)\n')
    edit("index_retrieve_module_v3/indexer/vector_store.py", "import chromadb\n", "import chromadb\nimport os  # local embedding service independent of chat backend\n")
    edit("index_retrieve_module_v3/indexer/vector_store.py",
         '        self.embeddings = OpenAIEmbeddings(\n            api_key=openai_api_key,\n            base_url=openai_base_url\n        )',
         '        self.embeddings = OpenAIEmbeddings(\n'
         '            api_key=os.getenv("MUMU_EMBEDDING_API_KEY", "local"),\n'
         '            base_url=os.environ["MUMU_EMBEDDING_BASE_URL"],\n'
         '            model=os.environ["MUMU_EMBEDDING_MODEL"],\n'
         '            check_embedding_ctx_length=False,\n'
         '        )')
    edit("agents/retrieval_agent.py",
         '        base_dir = Path(__file__).parent.parent / "index_data"',
         '        base_dir = Path(os.getenv("MUMU_INDEX_DIR", str(Path(__file__).parent.parent / "index_data")))')
    edit("agents/retrieval_agent.py",
         "                    result_id = result.get('id')",
         "                    result_id = result.get('id') or result.get('sqlite_id')  # VectorStore metadata key")
    edit("java_test_executor.py",
         '''        env['PATH'] = f"{self.java_home}\\\\bin;{env['PATH']}"''',
         '''        env['PATH'] = str(Path(self.java_home) / "bin") + os.pathsep + env['PATH']''')

    # Compile every resulting Python file before mutating any source.
    for path, text in edits.items():
        compile(text, str(path), "exec")
    records = []
    for path, text in edits.items():
        old = path.read_bytes()
        backup = path.with_name(path.name + ".pre-local-deploy")
        if not backup.exists():
            backup.write_bytes(old)
        path.write_text(text)
        records.append({"path": str(path.relative_to(root)),
                        "original_sha256": hashlib.sha256(backup.read_bytes()).hexdigest(),
                        "deployed_sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    manifest = root / "local-deployment-patches.json"
    manifest.write_text(json.dumps({"adaptation": "local Qwen chat and independent local embeddings; four iterations; runtime paths; RAG sqlite_id compatibility", "files": records}, indent=2) + "\n")
    print(json.dumps({"patched_files": len(records), "manifest": str(manifest)}))


if __name__ == "__main__":
    main()
