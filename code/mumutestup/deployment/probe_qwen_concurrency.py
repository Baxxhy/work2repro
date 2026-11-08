#!/usr/bin/env python3
"""Verify the local full model with concurrent real chat requests, not benchmarks."""
import concurrent.futures
import json
import os
from pathlib import Path
import time
import urllib.request
import sys

BASE = "http://127.0.0.1:8000"
OUT = Path(os.getenv("QWEN_PROBE_OUTPUT", "/root/Baxxhy/work2/reproductions/mumutestup/deployment/qwen-concurrency-verification.json"))
CONCURRENCY = int(os.getenv("QWEN_PROBE_CONCURRENCY", "16"))
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def request(path, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"})
    with opener.open(req, timeout=300) as response:
        body = response.read()
        return json.loads(body) if body else {"status": response.status}

def chat(index):
    start = time.monotonic()
    try:
        result = request("/v1/chat/completions", {
            "model": "qwen3.5-27b", "temperature": 0, "max_tokens": 160,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content":
                f"Case {index}: A Java API renamed setInjectHtml(boolean) to setInjectHtmlEnabled(boolean). "
                "Update only this test code, preserving the boolean false and the assertion. "
                "Return only the two updated Java statements. "
                "config.setInjectHtml(false); assertFalse(config.isInjectHtml());"}]
        })
        content = result["choices"][0]["message"].get("content") or ""
        return {"index": index, "ok": "setInjectHtmlEnabled(false)" in content and "assertFalse" in content,
                "seconds": time.monotonic()-start, "usage": result.get("usage"),
                "finish_reason": result["choices"][0].get("finish_reason"), "content": content}
    except Exception as exc:
        return {"index": index, "ok": False, "seconds": time.monotonic()-start, "error": str(exc)}

if "--wait-ready" in sys.argv:
    deadline = time.monotonic() + 2400
    while True:
        try:
            with opener.open(BASE + "/health", timeout=2) as response:
                if response.status == 200:
                    break
        except Exception:
            pass
        if time.monotonic() >= deadline:
            raise TimeoutError("Model service did not become ready within 40 minutes; it was not restarted.")
        time.sleep(10)

report = {"timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
          "endpoint": BASE + "/v1", "model": request("/v1/models"), "health": request("/health"),
          "scope": "Real API concurrency check on illustrative prompts; not PRBench results."}
report["single_request"] = chat(0)
json_result = request("/v1/chat/completions", {
    "model": "qwen3.5-27b", "temperature": 0, "max_tokens": 160,
    "chat_template_kwargs": {"enable_thinking": False},
    "response_format": {"type": "json_object"},
    "messages": [{"role": "user", "content":
        "Return a JSON object with keys method and explanation. The Java method setInjectHtml(boolean) "
        "was renamed to setInjectHtmlEnabled(boolean). method must be the new method name. "
        "explanation must be a short Chinese sentence explaining the rename."}]
})
json_content = json_result["choices"][0]["message"]["content"]
json_parsed = json.loads(json_content)
report["json_object_request"] = {"ok": json_parsed.get("method") == "setInjectHtmlEnabled",
                                 "content": json_parsed, "usage": json_result.get("usage")}
start = time.monotonic()
with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
    report["concurrent_requests"] = list(pool.map(chat, range(1, CONCURRENCY + 1)))
elapsed = time.monotonic()-start
total_tokens = sum((r.get("usage") or {}).get("completion_tokens", 0) for r in report["concurrent_requests"])
report.update({"client_concurrency": CONCURRENCY, "concurrent_wall_seconds": elapsed,
               "completion_tokens": total_tokens, "aggregate_completion_tokens_per_second": total_tokens/elapsed,
               "all_passed": report["single_request"]["ok"] and report["json_object_request"]["ok"]
                             and all(r["ok"] for r in report["concurrent_requests"])})
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({k: report[k] for k in ["all_passed", "client_concurrency", "concurrent_wall_seconds", "completion_tokens", "aggregate_completion_tokens_per_second"]}))
raise SystemExit(0 if report["all_passed"] else 1)
