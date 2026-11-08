#!/usr/bin/env python3
"""Protocol tests; uses a fake subprocess, never invokes Codex or a model."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from codex_luna_bridge import (
    Audit, BridgeError, CodexRPC, LunaBridge, MODEL, ThreadingHTTPServer,
    app_server_command, handler_for, validate_request,
)


def fake_server(scenario):
    """Echo prompts and emit interleaved events using the real RPC wire shape."""
    if scenario == "isolated_environment":
        assert not any(key.startswith("OPENAI_") for key in os.environ)
        assert "CODEX_API_KEY" not in os.environ
        assert os.environ["HTTPS_PROXY"] == "http://127.0.0.1:7894"
        assert os.environ["NO_PROXY"] == "localhost,127.0.0.1"
        assert os.environ["CODEX_HOME"].endswith("/test-codex-login-location")
        assert os.environ["SSL_CERT_FILE"].endswith("/test-ca.pem")
    lock = threading.Lock()
    threads = {}

    def emit(row):
        with lock:
            print(json.dumps(row), flush=True)

    def notify(method, tid, **params):
        emit({"method": method, "params": {"threadId": tid, **params}})

    def finish(tid, turn_id, prompt):
        # Includes a fast-before-RPC-response case; both must be buffered.
        if scenario == "parallel":
            time.sleep(0.04 if prompt == "first" else 0.01)
        notify("turn/started", tid, turn={"id": turn_id, "status": "inProgress"})
        if scenario == "tool":
            notify("item/started", tid, item={"id": "bad", "type": "commandExecution"})
            return
        if scenario == "tool_delta":
            notify("item/commandExecution/outputDelta", tid, delta="forbidden")
            return
        if scenario == "reroute":
            notify("model/rerouted", tid, fromModel=MODEL, toModel="other")
            return
        if scenario == "approval":
            emit({"id": "approval-1", "method": "item/commandExecution/requestApproval", "params": {"threadId": tid}})
            return
        if scenario == "quota":
            notify("error", tid, error={"message": "Usage limit reached"})
            return
        if scenario in ("reconnect", "network_retry", "network_exhausted"):
            error = {"message": "Reconnecting... 2/5", "codexErrorInfo": {"responseStreamDisconnected": {"httpStatusCode": None}}, "additionalDetails": "tls handshake eof"}
            notify("error", tid, error=error, willRetry=True)
            if scenario == "network_exhausted" or (scenario == "network_retry" and tid == "thread-1"):
                notify("turn/completed", tid, turn={"id": turn_id, "status": "failed", "error": error})
                return
        if scenario in ("rate_retry", "rate_exhausted"):
            if scenario == "rate_exhausted" or tid == "thread-1":
                error = {"message": "exceeded retry limit, last status: 429 Too Many Requests", "codexErrorInfo": {"responseTooManyFailedAttempts": {"httpStatusCode": 429}}}
                notify("error", tid, error=error, willRetry=False)
                notify("turn/completed", tid, turn={"id": turn_id, "status": "failed", "error": error})
                return
        if scenario == "timeout":
            return
        if scenario != "empty":
            notify("item/completed", tid, item={"id": "answer", "type": "agentMessage", "phase": "final_answer", "text": prompt})
        notify("thread/tokenUsage/updated", tid, tokenUsage={"total": {"inputTokens": 11, "outputTokens": 3,
               "cachedInputTokens": 2, "reasoningOutputTokens": 1, "totalTokens": 14}})
        notify("turn/completed", tid, turn={"id": turn_id, "status": "completed", "error": None})

    for line in sys.stdin:
        row = json.loads(line)
        method, params, rid = row.get("method"), row.get("params", {}), row.get("id")
        if method in ("initialized", None):
            continue
        result = {}
        if method == "account/read":
            result = {"account": {"type": "apiKey" if scenario == "api_key" else "chatgpt", "planType": "pro"}}
        elif method == "thread/start":
            assert params["model"] == MODEL and params["modelProvider"] == "openai"
            assert params["approvalPolicy"] == "never" and params["sandbox"] == "read-only"
            assert params["ephemeral"] and params["environments"] == [] and params["dynamicTools"] == []
            assert params["allowProviderModelFallback"] is False and params["serviceTier"] == "default"
            assert params["baseInstructions"] == "original system\n中文" and params["developerInstructions"] == ""
            tid = "thread-" + str(len(threads) + 1)
            threads[tid] = params
            result = {"thread": {"id": tid, "ephemeral": True, "environments": []},
                      "model": "other" if scenario == "wrong_model" else MODEL, "modelProvider": "openai",
                      "approvalPolicy": "never", "instructionSources": [], "serviceTier": "default"}
        elif method == "turn/start":
            tid, turn_id = params["threadId"], "turn-" + params["threadId"]
            assert params["model"] == MODEL and params["effort"] == "medium"
            assert params["environments"] == [] and params["serviceTierForTurn"] == "default"
            assert params["approvalPolicy"] == "never"
            assert len(params["input"]) == 1 and params["input"][0]["type"] == "text"
            assert "outputSchema" not in params  # json_object must preserve the original method prompt.
            prompt = params["input"][0]["text"]
            result = {"turn": {"id": turn_id, "status": "inProgress"}}
            if scenario == "parallel":
                threading.Thread(target=finish, args=(tid, turn_id, prompt), daemon=True).start()
            else:
                finish(tid, turn_id, prompt)
        elif method == "thread/unsubscribe":
            result = {"status": "unsubscribed"}
        elif method == "turn/interrupt":
            result = {}
        elif method != "initialize":
            raise AssertionError("Unexpected RPC " + str(method))
        emit({"id": rid, "result": result})


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.audit = Audit(self.root / "audit.jsonl")

    def bridge(self, scenario="success", timeout=2):
        rpc = CodexRPC([sys.executable, str(Path(__file__).resolve()), "--fake-server", scenario],
                       self.root / "empty", self.root / "fatal.json", self.audit, timeout)
        self.addCleanup(rpc.close)
        rpc.start()
        return LunaBridge(rpc, self.audit, timeout=timeout)

    @staticmethod
    def payload(text="original user\n中文", **extra):
        return {"model": MODEL, "messages": [{"role": "system", "content": "original system\n中文"},
                {"role": "user", "content": text}], "temperature": 0.1, **extra}

    def test_prompts_preserved_ephemeral_threads_usage_and_hash_only_audit(self):
        bridge = self.bridge()
        first = bridge.complete(self.payload())
        second = bridge.complete(self.payload("second"))
        self.assertEqual(first["choices"][0]["message"]["content"], "original user\n中文")
        self.assertNotEqual(first["bridge_metadata"]["thread_id"], second["bridge_metadata"]["thread_id"])
        self.assertEqual(first["usage"]["total_tokens"], 14)
        self.assertFalse(first["bridge_metadata"]["temperature_applied"])
        raw = (self.root / "audit.jsonl").read_text()
        self.assertNotIn("original user", raw)
        self.assertNotIn("original system", raw)
        rows = [json.loads(line) for line in raw.splitlines()]
        self.assertEqual(len([row for row in rows if row["event"] == "response"]), 2)
        self.assertFalse((self.root / "fatal.json").exists())

    def test_concurrent_responses_correlated(self):
        bridge = self.bridge("parallel")
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda text: bridge.complete(self.payload(text)), ["first", "second"]))
        self.assertEqual([result["choices"][0]["message"]["content"] for result in results], ["first", "second"])
        self.assertEqual(len({result["bridge_metadata"]["thread_id"] for result in results}), 2)

    def test_reconnect_notification_does_not_abort(self):
        bridge = self.bridge("reconnect")
        self.assertEqual(bridge.complete(self.payload())["model"], MODEL)
        self.assertFalse((self.root / "fatal.json").exists())

    def test_terminal_network_failure_retries_fresh_thread(self):
        bridge = self.bridge("network_retry")
        with patch("codex_luna_bridge.time.sleep"):
            result = bridge.complete(self.payload())
        self.assertEqual(result["bridge_metadata"]["thread_id"], "thread-2")
        self.assertFalse((self.root / "fatal.json").exists())

    def test_exhausted_network_retries_do_not_poison_bridge(self):
        bridge = self.bridge("network_exhausted")
        with patch("codex_luna_bridge.time.sleep"), self.assertRaises(BridgeError) as raised:
            bridge.complete(self.payload())
        self.assertEqual(raised.exception.code, "network_request_failed")
        self.assertFalse((self.root / "fatal.json").exists())
        bridge.rpc.check()

    def test_rate_limit_retries_and_sets_shared_cooldown(self):
        bridge = self.bridge("rate_retry")
        with patch.object(bridge, "_wait_cooldown"), patch("codex_luna_bridge.time.sleep"):
            result = bridge.complete(self.payload())
        self.assertEqual(result["bridge_metadata"]["thread_id"], "thread-2")
        self.assertGreater(bridge.rpc.cooldown_until, time.monotonic())
        self.assertFalse((self.root / "fatal.json").exists())

    def test_rate_limit_exhaustion_preserves_other_requests(self):
        bridge = self.bridge("rate_exhausted")
        with patch.object(bridge, "_wait_cooldown"), patch("codex_luna_bridge.time.sleep"), self.assertRaises(BridgeError) as raised:
            bridge.complete(self.payload())
        self.assertEqual(raised.exception.code, "rate_limit_request_failed")
        self.assertFalse((self.root / "fatal.json").exists())
        bridge.rpc.check()

    def test_json_mode_does_not_change_prompt_or_strip_invalid_output(self):
        bridge = self.bridge()
        result = bridge.complete(self.payload('{"answer": 1}', response_format={"type": "json_object"}))
        self.assertTrue(result["bridge_metadata"]["json_valid"])
        result = bridge.complete(self.payload("```json\n{}\n```", response_format={"type": "json_object"}))
        self.assertFalse(result["bridge_metadata"]["json_valid"])
        self.assertEqual(result["choices"][0]["message"]["content"], "```json\n{}\n```")
        self.assertFalse((self.root / "fatal.json").exists())

    def test_reject_unknown_models_content_and_tools_before_inference(self):
        invalid = [self.payload(model="other"), self.payload(tools=[]), self.payload(stream=True),
                   {"model": MODEL, "messages": [{"role": "user", "content": [{"type": "text", "text": "hi"}]}]}]
        for payload in invalid:
            with self.subTest(payload=payload), self.assertRaises(BridgeError) as raised:
                validate_request(payload)
            self.assertEqual(raised.exception.status, 400)

    def test_no_api_key_auth(self):
        with self.assertRaises(BridgeError):
            self.bridge("api_key")
        self.assertEqual(json.loads((self.root / "fatal.json").read_text())["code"], "subscription_auth_required")

    def test_client_environment_cannot_redirect_app_server(self):
        runtime = {"OPENAI_BASE_URL": "http://127.0.0.1:8012/v1",
                   "OPENAI_API_BASE": "http://127.0.0.1:8012/v1",
                   "OPENAI_API_KEY": "test-placeholder", "CODEX_API_KEY": "test-placeholder",
                   "OPENAI_PROJECT_ID": "test-project", "OPENAI_ORG_ID": "test-org",
                   "HTTPS_PROXY": "http://127.0.0.1:7894", "NO_PROXY": "localhost,127.0.0.1",
                   "CODEX_HOME": str(self.root / "test-codex-login-location"),
                   "SSL_CERT_FILE": str(self.root / "test-ca.pem")}
        with patch.dict(os.environ, runtime):
            bridge = self.bridge("isolated_environment")
            result = bridge.complete(self.payload())
            self.assertEqual(result["model"], MODEL)
            # Filtering only affects Popen: MuMu's own client remains usable.
            for key, value in runtime.items():
                self.assertEqual(os.environ[key], value)
        self.assertFalse((self.root / "fatal.json").exists())

    def test_fail_closed_for_tools_rerouting_quota_approval_empty_and_wrong_model(self):
        for scenario in ("tool", "tool_delta", "reroute", "quota", "approval", "empty", "wrong_model"):
            with self.subTest(scenario=scenario):
                marker = self.root / "fatal.json"
                marker.unlink(missing_ok=True)
                bridge = self.bridge(scenario)
                with self.assertRaises(BridgeError):
                    bridge.complete(self.payload())
                self.assertTrue(marker.exists())
                self.assertTrue(json.loads(marker.read_text())["fatal"])
                with self.assertRaises(BridgeError):
                    bridge.complete(self.payload())
                bridge.rpc.close()

    def test_inference_timeout_writes_fatal_marker(self):
        bridge = self.bridge("timeout", timeout=0.15)
        with self.assertRaises(BridgeError):
            bridge.complete(self.payload())
        self.assertEqual(json.loads((self.root / "fatal.json").read_text())["code"], "inference_timeout")

    def test_existing_marker_prevents_restart(self):
        (self.root / "fatal.json").write_text('{"fatal": true}')
        with self.assertRaises(BridgeError) as raised:
            self.bridge()
        self.assertEqual(raised.exception.code, "existing_fatal_marker")

    def test_http_endpoints_and_nonempty_error(self):
        bridge = self.bridge()
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(bridge))
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        base = "http://127.0.0.1:" + str(server.server_port)
        with urlopen(base + "/health") as response:
            self.assertTrue(json.load(response)["ok"])
        with urlopen(base + "/v1/models") as response:
            self.assertEqual(json.load(response)["data"][0]["id"], MODEL)
        request = Request(base + "/v1/chat/completions", data=json.dumps(self.payload()).encode(),
                          headers={"Content-Type": "application/json"})
        with urlopen(request) as response:
            self.assertEqual(json.load(response)["choices"][0]["message"]["content"], "original user\n中文")
        request.data = b'{"model":"other"}'
        with self.assertRaises(HTTPError) as raised:
            urlopen(request)
        self.assertEqual(raised.exception.code, 400)
        self.assertTrue(json.load(raised.exception)["error"]["message"])

    def test_command_disables_tools_and_environment_sources(self):
        command = app_server_command("codex")
        for required in ('web_search="disabled"', "project_doc_max_bytes=0", "mcp_servers={}",
                         "features.skip_host_skill_discovery=true", "shell_tool", "plugins", "multi_agent"):
            self.assertIn(required, command)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--fake-server":
        fake_server(sys.argv[2])
    else:
        unittest.main()
