#!/usr/bin/env python3
"""Exercise official production-only embedding and semantic search on an existing index."""
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time
import traceback


def stamp():
    return datetime.now(timezone.utc).isoformat()


def main():
    root = Path(os.environ.get("MUMU_ROOT", "/root/Baxxhy/work2/reproductions/mumutestup"))
    upstream = root / "upstream"
    repo = root / "repos/j256/ormlite-core"
    run = root / "runs/smoke-ormlite-proxyfix-20261030"
    index = run / "index_data/j256_ormlite-core/6d183bb4"
    destination = root / "deployment/retrieval-verification.json"
    log_path = root / "deployment/retrieval-verification.log"
    os.environ["MUMU_INDEX_DIR"] = str(run / "index_data")
    os.environ["MUMU_FRAMEWORK_LOG"] = str(log_path)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    sys.dont_write_bytecode = True
    os.chdir(upstream)
    sys.path.insert(0, str(upstream))
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    def repo_state():
        env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
        head = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, env=env).strip()
        diff = subprocess.check_output(["git", "-C", str(repo), "diff", "--binary", "HEAD"], env=env)
        status = subprocess.check_output(["git", "-C", str(repo), "status", "--porcelain", "--untracked-files=no"], text=True, env=env)
        return {"head": head, "tracked_status": status, "tracked_diff_sha256": hashlib.sha256(diff).hexdigest()}

    result = {"started_at": stamp(), "index_directory": str(index), "repository": str(repo),
              "query": "Build an SQL UPDATE statement and assign a new value to a named column, escaping the value when necessary.",
              "embedding_model": os.environ.get("MUMU_EMBEDDING_MODEL"),
              "embedding_endpoint": os.environ.get("MUMU_EMBEDDING_BASE_URL"),
              "scope": "Official module enumeration, incremental production-method embedding, and semantic search only; no sample run."}
    started = time.monotonic()
    result["repository_before"] = repo_state()
    try:
        with sqlite3.connect("file:" + str(index / "assets.db") + "?mode=ro", uri=True) as conn:
            method_rows = list(conn.execute("SELECT id,module_name,is_test,class_name,method_name FROM methods"))
        production_ids = {row[0] for row in method_rows if not row[2]}
        test_ids = {row[0] for row in method_rows if row[2]}
        result["sqlite_production_method_count"] = len(production_ids)
        result["sqlite_test_method_count"] = len(test_ids)
        from agents.retrieval_agent import RetrievalAgent
        from indexer.vector_store import VectorStore
        agent = RetrievalAgent(str(repo), "j256/ormlite-core", "6d183bb4")
        if agent.index_dir != index:
            raise RuntimeError(f"Unexpected official index directory: {agent.index_dir}")
        result["available_modules"] = agent.index_builder.get_available_modules()
        if result["available_modules"] != ["root"]:
            raise RuntimeError(f"Unexpected module enumeration: {result['available_modules']}")
        result["incremental_embedding_success"] = agent.index_builder.build_incremental_module_embedding("root", verbose=True)
        if not result["incremental_embedding_success"]:
            raise RuntimeError("Official incremental embedding builder returned False")
        vector_store = VectorStore(chroma_path=index / "chroma_db", collection_name="java_methods",
                                   openai_api_key="local", openai_base_url=os.environ["OPENAI_BASE_URL"])
        collection = vector_store.vector_store._collection
        stored = collection.get(include=["metadatas"])
        vector_ids = set(stored["ids"])
        result["vector_method_count"] = collection.count()
        result["vector_test_id_count"] = len(vector_ids & test_ids)
        result["vector_unknown_id_count"] = len(vector_ids - production_ids - test_ids)
        result["vector_missing_production_count"] = len(production_ids - vector_ids)
        result["vector_metadata_test_values"] = sorted({str(m.get("is_test")) for m in stored["metadatas"]})
        if vector_ids != production_ids:
            raise RuntimeError("Vector collection IDs do not exactly match SQLite production-method IDs")
        matches = agent._search_collection(index / "chroma_db", "java_methods", result["query"], 8)
        result["results"] = matches
        result["result_count"] = len(matches)
        result["all_results_are_production_methods"] = bool(matches) and all((m.get("id") or m.get("sqlite_id")) in production_ids for m in matches)
        if not result["all_results_are_production_methods"]:
            raise RuntimeError("Official semantic search returned no results or included a non-production method")
        enriched = agent._enrich_with_bodies(index / "assets.db", matches)
        result["enriched_result_count"] = len(enriched)
        result["all_results_have_method_bodies"] = bool(enriched) and all(bool(m.get("body")) for m in enriched)
        if len(enriched) != len(matches) or not result["all_results_have_method_bodies"]:
            raise RuntimeError("Official method-body enrichment dropped semantic matches or returned empty bodies")
        parsed_methods, parsed_fields = agent._parse_rag_results(enriched)
        result["parsed_method_count"] = len(parsed_methods)
        result["parsed_field_count"] = len(parsed_fields)
        if len(parsed_methods) != len(matches):
            raise RuntimeError("Official RAG result parser dropped semantic method matches")
        result["success"] = True
    except Exception:
        result["success"] = False
        result["traceback"] = traceback.format_exc()
    finally:
        result["repository_after"] = repo_state()
        result["repository_tracked_state_unchanged"] = result["repository_before"] == result["repository_after"]
        if not result["repository_tracked_state_unchanged"]:
            result["success"] = False
        result["finished_at"] = stamp()
        result["elapsed_seconds"] = round(time.monotonic() - started, 3)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
