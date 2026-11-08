#!/usr/bin/env python3
"""Loopback Chat Completions adapter for an official, persistent Codex app-server.

This is a Codex text adapter, not a bare-model/SIWC API reproduction. Each call
uses a separate ephemeral thread and the caller's unmodified system/user text.
No model fallback or tool execution is accepted. Fatal failures stop the bridge
and are also exposed through a marker checked by the experiment supervisor.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import re
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

MODEL = "gpt-6-luna"
ROUTE = "codex-app-server-text-adapter"
MAX_BODY = 8 * 1024 * 1024
DISABLED_FEATURES = (
    "shell_tool", "apps", "plugins", "multi_agent", "code_mode",
    "code_mode_host", "view_image", "image_generation", "browser_use",
    "computer_use", "skill_search", "hooks", "sleep_tool", "goals",
)


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def app_server_environment() -> dict[str, str]:
    # MuMu's OpenAI-compatible client points at this bridge. The official
    # app-server must not inherit that address, API credentials, or API account
    # selectors. Keep CODEX_HOME for cached ChatGPT login and proxy/CA settings
    # needed by the remote host; do not mutate the bridge/client environment.
    return {key: value for key, value in os.environ.items()
            if not key.startswith("OPENAI_") and key != "CODEX_API_KEY"}


def safe_error(value: Any) -> str:
    # Only error descriptions enter diagnostics, never request headers/tokens.
    text = str(value)
    text = re.sub(r"(?i)Bearer\s+\S+", "Bearer [redacted]", text)
    text = re.sub(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+", "[redacted-jwt]", text)
    text = re.sub(r"\b(?:sk-|rt_)[A-Za-z0-9_-]{12,}", "[redacted-secret]", text)
    text = re.sub(r"(?i)(access_token|refresh_token|id_token|api_key)([\"'\s:=]+)[^\s,}\"']+", r"\1\2[redacted]", text)
    return text[:1600]


class BridgeError(Exception):
    def __init__(self, code: str, message: str, status: int = 502):
        super().__init__(message)
        self.code, self.status = code, status


class Audit:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path, self.lock = path, threading.Lock()

    def write(self, event: str, **fields: Any) -> None:
        record = {"event": event, "timestamp": time.time(), "route": ROUTE, **fields}
        with self.lock, self.path.open("a", encoding="utf-8") as handle:
            handle.write(canonical(record) + "\n")
            handle.flush()


class CodexRPC:
    """Owns one stdio app-server, with correlated RPC and per-thread events."""

    def __init__(self, command: list[str], work_dir: Path, fatal_file: Path,
                 audit: Audit, timeout: float = 600):
        self.command, self.work_dir = command, work_dir
        self.fatal_file, self.audit, self.timeout = fatal_file, audit, timeout
        self.lock, self.write_lock = threading.RLock(), threading.Lock()
        self.pending: dict[int, queue.Queue] = {}
        self.events: dict[str, queue.Queue] = {}
        self.active_turns: dict[str, str] = {}
        self.next_id = 0
        self.fatal: dict[str, Any] | None = None
        self.closed = False
        self.process: subprocess.Popen | None = None
        self.readers: list[threading.Thread] = []

    def start(self) -> None:
        if self.fatal_file.exists():
            raise BridgeError("existing_fatal_marker", "Use a new run directory; its fatal marker already exists.", 503)
        self.work_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.process = subprocess.Popen(
            self.command, cwd=self.work_dir, env=app_server_environment(), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", bufsize=1, start_new_session=True,
        )
        self.readers = [threading.Thread(target=self._read, daemon=True),
                        threading.Thread(target=self._stderr, daemon=True)]
        for reader in self.readers:
            reader.start()
        try:
            self.call("initialize", {
                "clientInfo": {"name": "mumu_luna_text_bridge", "title": "MuMuTestUp Luna text adapter", "version": "1.0"},
                "capabilities": {"experimentalApi": True},
            }, timeout=45)
            self.send({"method": "initialized", "params": {}})
            account = self.call("account/read", {"refreshToken": False}, timeout=30)
            auth = account.get("account") or {}
            if auth.get("type") != "chatgpt":
                raise BridgeError("subscription_auth_required", "The app-server must be authenticated with ChatGPT.", 503)
            self.audit.write("started", model=MODEL, reasoning_effort="medium", service_tier="default",
                             auth_type=auth.get("type"), plan_type=auth.get("planType"),
                             app_server_pid=self.process.pid)
        except Exception as exc:
            self.fail(getattr(exc, "code", "startup_failed"), safe_error(exc))
            raise

    def send(self, message: dict) -> None:
        with self.write_lock:
            if self.process is None or self.process.poll() is not None:
                raise BridgeError("app_server_unavailable", "The app-server process is unavailable.", 503)
            assert self.process.stdin is not None
            self.process.stdin.write(canonical(message) + "\n")
            self.process.stdin.flush()

    def check(self) -> None:
        if self.fatal:
            raise BridgeError("bridge_fatal", self.fatal["code"] + ": " + self.fatal["message"], 503)
        if self.closed:
            raise BridgeError("bridge_closed", "The bridge is closed.", 503)

    def call(self, method: str, params: dict, timeout: float | None = None) -> dict:
        self.check()
        with self.lock:
            self.next_id += 1
            request_id = self.next_id
            response: queue.Queue = queue.Queue(maxsize=1)
            self.pending[request_id] = response
        try:
            self.send({"id": request_id, "method": method, "params": params})
            try:
                message = response.get(timeout=timeout or self.timeout)
            except queue.Empty:
                self.fail("rpc_timeout", "RPC timed out: " + method)
                raise BridgeError("rpc_timeout", "RPC timed out: " + method, 504)
            self.check()
            if "error" in message:
                error = message["error"]
                raise BridgeError("app_server_rpc_error", safe_error(error))
            result = message.get("result")
            if not isinstance(result, dict):
                raise BridgeError("invalid_rpc_result", "Expected an object result from " + method)
            return result
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def thread_queue(self, thread_id: str) -> queue.Queue:
        with self.lock:
            return self.events.setdefault(thread_id, queue.Queue())

    def fail(self, code: str, message: str, **fields: Any) -> None:
        with self.lock:
            if self.fatal:
                return
            self.fatal = {"fatal": True, "code": code, "message": safe_error(message),
                          "timestamp": time.time(), "model": MODEL, "route": ROUTE, **fields}
            self.fatal_file.parent.mkdir(parents=True, exist_ok=True)
            # Exclusive creation prevents an accidental restart overwriting evidence.
            try:
                with self.fatal_file.open("x", encoding="utf-8") as handle:
                    handle.write(canonical(self.fatal) + "\n")
            except FileExistsError:
                pass
            self.audit.write("fatal", **self.fatal)
            for response in self.pending.values():
                try:
                    response.put_nowait({"error": {"message": "Bridge fatal"}})
                except queue.Full:
                    pass
            for events in self.events.values():
                events.put({"method": "bridge/fatal", "params": {}})
            active = list(self.active_turns.items())
        # Do not wait for replies on the reader thread. Terminating the process
        # group also prevents a rejected tool event from continuing locally.
        for thread_id, turn_id in active:
            try:
                with self.lock:
                    self.next_id += 1
                    ident = self.next_id
                self.send({"id": ident, "method": "turn/interrupt", "params": {"threadId": thread_id, "turnId": turn_id}})
            except Exception:
                pass
        self._terminate()

    def _terminate(self) -> None:
        process = self.process
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass

    def _stderr(self) -> None:
        assert self.process and self.process.stderr
        # Raw diagnostics are intentionally not persisted. They can include
        # environment values. Retain a digest and byte count for provenance.
        for line in self.process.stderr:
            self.audit.write("app_server_stderr", sha256=digest(line), bytes=len(line.encode("utf-8")))

    def _read(self) -> None:
        assert self.process and self.process.stdout
        try:
            for line in self.process.stdout:
                try:
                    message = json.loads(line)
                except (ValueError, TypeError):
                    self.fail("invalid_rpc_json", "The app-server emitted invalid JSON.")
                    break
                if not isinstance(message, dict):
                    self.fail("invalid_rpc_message", "The app-server emitted a non-object message.")
                    break
                if "id" in message and "method" in message:
                    # This adapter never approves or executes server requests.
                    self.send({"id": message["id"], "error": {"code": -32601, "message": "Text adapter rejects tools, approvals, and server requests."}})
                    self.fail("unexpected_server_request", "Rejected server request: " + str(message["method"]))
                    break
                if "id" in message:
                    with self.lock:
                        target = self.pending.get(message["id"])
                    if target is not None:
                        try:
                            target.put_nowait(message)
                        except queue.Full:
                            self.fail("duplicate_rpc_response", "The app-server repeated an RPC response.")
                    continue
                self._notification(message)
                if self.fatal:
                    break
        except Exception as exc:
            if not self.closed:
                self.fail("rpc_reader_failed", safe_error(exc))
        finally:
            if not self.closed and not self.fatal:
                self.fail("app_server_exited", "The app-server stdout closed unexpectedly.")

    def _notification(self, message: dict) -> None:
        method, params = message.get("method"), message.get("params") or {}
        if not isinstance(method, str) or not isinstance(params, dict):
            self.fail("invalid_notification", "Malformed app-server notification.")
            return
        thread_id = params.get("threadId")
        if method.startswith(("item/commandExecution/", "item/fileChange/", "item/mcpToolCall/",
                              "item/dynamicToolCall/", "item/autoApprovalReview/")):
            self.fail("unexpected_tool_event", "Tool event rejected: " + method, thread_id=thread_id)
            return
        if method == "turn/started" and thread_id:
            turn_id = (params.get("turn") or {}).get("id")
            if turn_id:
                with self.lock:
                    self.active_turns[thread_id] = turn_id
        if method in {"item/started", "item/completed"}:
            item = params.get("item") or {}
            kind = item.get("type")
            if kind not in {"userMessage", "agentMessage", "reasoning"}:
                self.fail("unexpected_item", "Non-text item rejected: " + str(kind), thread_id=thread_id)
                return
        if method == "model/rerouted":
            self.fail("model_rerouted", "Model fallback is forbidden.", thread_id=thread_id,
                      from_model=params.get("fromModel"), to_model=params.get("toModel"))
            return
        if method == "error" and is_rate_limit(params.get("error")):
            with self.lock:
                self.throttle_count = getattr(self, "throttle_count", 0) + 1
                delay = min(120, 30 * 2 ** min(self.throttle_count - 1, 2))
                self.cooldown_until = max(getattr(self, "cooldown_until", 0), time.monotonic() + delay)
            self.audit.write("rate_limit_notification", thread_id=thread_id,
                             cooldown_seconds=delay, will_retry=params.get("willRetry"))
            return
        if method == "error" and is_network_error(params.get("error")):
            # Retry notifications are not terminal turn failures. The app-server
            # owns reconnects; only turn/completed determines final failure.
            self.audit.write("network_notification", thread_id=thread_id,
                             error=safe_error(params.get("error")),
                             will_retry=params.get("willRetry"))
            return
        if method == "error":
            self.fail("app_server_error", safe_error(params.get("error", "Unspecified app-server error")), thread_id=thread_id)
            return
        if method == "model/verification":
            self.fail("account_verification_required", "Account verification is required.", thread_id=thread_id)
            return
        if method == "thread/diff/updated" or method == "turn/diff/updated":
            if params.get("diff"):
                self.fail("unexpected_file_change", "The text adapter received a file-change diff.", thread_id=thread_id)
                return
        if method == "account/updated" and params.get("authMode") != "chatgpt":
            self.fail("authentication_changed", "ChatGPT subscription authentication was lost.")
            return
        if thread_id:
            self.thread_queue(thread_id).put(message)

    def close(self) -> None:
        self.closed = True
        self._terminate()
        if self.process:
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
            for reader in self.readers:
                if reader is not threading.current_thread():
                    reader.join(timeout=2)
            for pipe in (self.process.stdin, self.process.stdout, self.process.stderr):
                if pipe:
                    pipe.close()


def validate_request(payload: Any) -> dict:
    if not isinstance(payload, dict):
        raise BridgeError("invalid_request", "Request body must be a JSON object.", 400)
    allowed = {"model", "messages", "temperature", "response_format", "stream", "n"}
    unknown = set(payload) - allowed
    if unknown:
        raise BridgeError("unsupported_parameters", "Unsupported fields: " + ", ".join(sorted(unknown)), 400)
    if payload.get("model") != MODEL:
        raise BridgeError("model_not_allowed", "This bridge only serves " + MODEL, 400)
    if payload.get("stream", False) is not False or payload.get("n", 1) != 1:
        raise BridgeError("unsupported_mode", "Only non-streaming, single-choice Chat Completions are supported.", 400)
    messages = payload.get("messages")
    if not isinstance(messages, list) or len(messages) not in (1, 2):
        raise BridgeError("unsupported_messages", "Expected one user message, optionally preceded by one system message.", 400)
    expected = ["user"] if len(messages) == 1 else ["system", "user"]
    for message, role in zip(messages, expected):
        if not isinstance(message, dict) or set(message) != {"role", "content"} or message.get("role") != role or not isinstance(message.get("content"), str):
            raise BridgeError("unsupported_content", "Only exact system/user text messages are accepted.", 400)
    if not messages[-1]["content"].strip():
        raise BridgeError("empty_prompt", "User text must not be empty.", 400)
    temperature = payload.get("temperature")
    if temperature is not None and (isinstance(temperature, bool) or not isinstance(temperature, (int, float)) or not math.isfinite(temperature)):
        raise BridgeError("invalid_temperature", "temperature must be a finite number.", 400)
    output_schema = None
    fmt = payload.get("response_format")
    if fmt is None:
        fmt = {"type": "text"}
    if not isinstance(fmt, dict):
        raise BridgeError("invalid_response_format", "response_format must be an object.", 400)
    if fmt.get("type") in ("text", "json_object"):
        if set(fmt) != {"type"}:
            raise BridgeError("invalid_response_format", "Unsupported response_format fields.", 400)
    elif fmt.get("type") == "json_schema":
        schema = fmt.get("json_schema")
        if set(fmt) != {"type", "json_schema"} or not isinstance(schema, dict) or not isinstance(schema.get("schema"), dict):
            raise BridgeError("invalid_response_format", "Expected a json_schema.schema object.", 400)
        output_schema = schema["schema"]
    else:
        raise BridgeError("invalid_response_format", "Unsupported response_format type.", 400)
    return {"system": messages[0]["content"] if len(messages) == 2 else "",
            "user": messages[-1]["content"], "format": fmt["type"], "schema": output_schema,
            "ignored_temperature": temperature}


def is_rate_limit(error: Any) -> bool:
    text = str(error).lower()
    # Account/quota exhaustion is not assumed to be a transient throttle.
    if any(x in text for x in ("usage limit", "quota", "insufficient_quota")):
        return False
    return "429" in text or "too many requests" in text


def is_network_error(error: Any) -> bool:
    text = str(error).lower()
    return any(value in text for value in (
        "responsestreamdisconnected", "tls handshake", "stream disconnected",
        "connection reset", "connection refused", "connection closed",
        "network is unreachable", "error sending request", "connection timed out",
    ))


class LunaBridge:
    def __init__(self, rpc: CodexRPC, audit: Audit, concurrency: int = 2, timeout: float = 600):
        if not 1 <= concurrency <= 10:
            raise ValueError("Concurrency must be between 1 and 10.")
        self.rpc, self.audit, self.timeout = rpc, audit, timeout
        self.slots = threading.BoundedSemaphore(concurrency)

    def complete(self, payload: Any) -> dict:
        for attempt in range(3):
            try:
                return self._complete_once(payload)
            except BridgeError as exc:
                if exc.code not in {"network_request_failed", "rate_limit_request_failed"} or attempt == 2:
                    raise
                self.audit.write("request_retry", code=exc.code, attempt=attempt + 1,
                                 delay_seconds=2 ** (attempt + 1))
                time.sleep(2 ** (attempt + 1))

    def _wait_cooldown(self):
        while True:
            self.rpc.check()
            with self.rpc.lock:
                remaining = getattr(self.rpc, "cooldown_until", 0) - time.monotonic()
            if remaining <= 0:
                return
            time.sleep(min(remaining, 1))

    def _complete_once(self, payload: Any) -> dict:
        parsed = validate_request(payload)
        self.rpc.check()
        if not self.slots.acquire(timeout=self.timeout):
            raise BridgeError("bridge_busy", "The bridge concurrency slots are busy.", 429)
        request_id, started = "chatcmpl-" + uuid.uuid4().hex, time.monotonic()
        thread_id: str | None = None
        usage: dict = {}
        self.audit.write("request", request_id=request_id, model=MODEL,
                         request_sha256=digest(canonical(payload)),
                         system_sha256=digest(parsed["system"]), user_sha256=digest(parsed["user"]),
                         response_format=parsed["format"], ignored_temperature=parsed["ignored_temperature"],
                         json_mode="original-prompt-with-validation" if parsed["format"] == "json_object" else parsed["format"])
        try:
            self._wait_cooldown()
            self.rpc.check()
            thread = self.rpc.call("thread/start", {
                "model": MODEL, "modelProvider": "openai", "approvalPolicy": "never",
                "sandbox": "read-only", "cwd": str(self.rpc.work_dir), "ephemeral": True,
                "environments": [], "dynamicTools": [], "serviceTier": "default",
                "allowProviderModelFallback": False, "baseInstructions": parsed["system"],
                "developerInstructions": "", "config": {"model_reasoning_effort": "medium"},
            })
            thread_id = thread["thread"]["id"]
            if thread.get("model") != MODEL or thread.get("modelProvider") != "openai":
                raise BridgeError("wrong_model", "The app-server selected a different model/provider.")
            if thread.get("instructionSources"):
                raise BridgeError("unexpected_instructions", "The app-server loaded instruction files.")
            if thread.get("approvalPolicy") != "never" or thread.get("thread", {}).get("ephemeral") is not True:
                raise BridgeError("unexpected_thread_policy", "The thread did not retain the required isolation policy.")
            if thread.get("thread", {}).get("environments") not in (None, []):
                raise BridgeError("unexpected_environment", "The app-server selected an execution environment.")
            if thread.get("serviceTier") not in (None, "default"):
                raise BridgeError("wrong_service_tier", "The app-server did not select Standard speed.")
            turn_params: dict = {
                "threadId": thread_id, "model": MODEL, "effort": "medium", "environments": [],
                "approvalPolicy": "never", "serviceTierForTurn": "default",
                "input": [{"type": "text", "text": parsed["user"]}],
            }
            if parsed["schema"] is not None:
                turn_params["outputSchema"] = parsed["schema"]
            turn = self.rpc.call("turn/start", turn_params)
            turn_id = turn["turn"]["id"]
            with self.rpc.lock:
                self.rpc.active_turns[thread_id] = turn_id
            outputs: list[dict] = []
            events = self.rpc.thread_queue(thread_id)
            deadline = time.monotonic() + self.timeout
            while True:
                self.rpc.check()
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise BridgeError("inference_timeout", "The model response exceeded the request deadline.", 504)
                try:
                    event = events.get(timeout=min(remaining, 1))
                except queue.Empty:
                    continue
                method, params = event.get("method"), event.get("params") or {}
                if method == "thread/tokenUsage/updated":
                    usage = params.get("tokenUsage") or {}
                elif method == "item/completed":
                    item = params.get("item") or {}
                    if item.get("type") == "agentMessage":
                        if not isinstance(item.get("text"), str):
                            raise BridgeError("invalid_model_content", "The model returned non-text content.")
                        outputs.append(item)
                elif method == "turn/completed":
                    completed = params.get("turn") or {}
                    if completed.get("id") != turn_id:
                        raise BridgeError("wrong_turn", "Received completion for a different turn.")
                    if completed.get("status") != "completed":
                        raise BridgeError("rate_limit_request_failed" if is_rate_limit(completed.get("error")) else
                                          "network_request_failed" if is_network_error(completed.get("error")) else "turn_failed",
                                          safe_error(completed.get("error") or completed.get("status")))
                    break
            self.rpc.check()
            finals = [item for item in outputs if item.get("phase") == "final_answer"]
            candidates = finals or [item for item in outputs if item.get("phase") is None]
            if not candidates or not candidates[-1]["text"].strip():
                raise BridgeError("empty_model_output", "The completed turn has no final textual answer.")
            content = candidates[-1]["text"]
            valid_json = None
            if parsed["format"] != "text":
                try:
                    valid_json = isinstance(json.loads(content), dict)
                except ValueError:
                    valid_json = False
            total = usage.get("total") or usage.get("last") or {}
            normalized_usage = {
                "prompt_tokens": total.get("inputTokens", 0), "completion_tokens": total.get("outputTokens", 0),
                "total_tokens": total.get("totalTokens", 0),
                "prompt_tokens_details": {"cached_tokens": total.get("cachedInputTokens", 0)},
                "completion_tokens_details": {"reasoning_tokens": total.get("reasoningOutputTokens", 0)},
            }
            self.audit.write("response", request_id=request_id, model=MODEL, thread_id=thread_id, turn_id=turn_id,
                             response_sha256=digest(content), duration_seconds=round(time.monotonic() - started, 6),
                             token_usage=usage, token_usage_reported=bool(usage), json_valid=valid_json)
            return {"id": request_id, "object": "chat.completion", "created": int(time.time()), "model": MODEL,
                    "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
                    "usage": normalized_usage,
                    "bridge_metadata": {"route": ROUTE, "thread_id": thread_id,
                                        "temperature_applied": False, "json_valid": valid_json,
                                        "token_usage_reported": bool(usage)}}
        except Exception as exc:
            code = getattr(exc, "code", "bridge_internal_error")
            if code == "app_server_rpc_error" and is_network_error(exc):
                code = "network_request_failed"
            if code == "app_server_rpc_error" and is_rate_limit(exc):
                code = "rate_limit_request_failed"
            if code == "rate_limit_request_failed":
                with self.rpc.lock:
                    self.rpc.cooldown_until = max(getattr(self.rpc, "cooldown_until", 0), time.monotonic() + 30)
            if code not in {"network_request_failed", "rate_limit_request_failed"}:
                self.rpc.fail(code, safe_error(exc), thread_id=thread_id, request_id=request_id)
            self.audit.write("request_failed", request_id=request_id, model=MODEL, thread_id=thread_id,
                             code=code, duration_seconds=round(time.monotonic() - started, 6), token_usage=usage)
            raise BridgeError(code, safe_error(exc), getattr(exc, "status", 502)) from exc
        finally:
            if thread_id:
                with self.rpc.lock:
                    self.rpc.active_turns.pop(thread_id, None)
                if not self.rpc.fatal:
                    try:
                        self.rpc.call("thread/unsubscribe", {"threadId": thread_id}, timeout=15)
                    except Exception as exc:
                        self.rpc.fail("thread_cleanup_failed", safe_error(exc), thread_id=thread_id)
                with self.rpc.lock:
                    self.rpc.events.pop(thread_id, None)
            self.slots.release()
            self.rpc.check()


def handler_for(bridge: LunaBridge):
    class Handler(BaseHTTPRequestHandler):
        server_version = "MuMuLunaTextBridge/1.0"

        def log_message(self, *_args):
            pass

        def respond(self, status: int, body: dict) -> None:
            data = canonical(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            if self.path == "/health":
                fatal = bridge.rpc.fatal
                self.respond(503 if fatal else 200, {"ok": not bool(fatal), "model": MODEL, "route": ROUTE,
                                                   "fatal_code": fatal.get("code") if fatal else None})
            elif self.path == "/v1/models":
                self.respond(200, {"object": "list", "data": [{"id": MODEL, "object": "model", "owned_by": "openai"}]})
            else:
                self.respond(404, {"error": {"message": "Unknown endpoint", "type": "invalid_request_error"}})

        def do_POST(self):
            if self.path != "/v1/chat/completions":
                self.respond(404, {"error": {"message": "Unknown endpoint", "type": "invalid_request_error"}})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > MAX_BODY or self.headers.get("Transfer-Encoding"):
                    raise BridgeError("invalid_body_size", "Supply a JSON body of at most 8 MiB with Content-Length.", 400)
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                self.respond(200, bridge.complete(payload))
            except (ValueError, UnicodeDecodeError):
                self.respond(400, {"error": {"message": "Invalid JSON body", "type": "invalid_request_error"}})
            except BridgeError as exc:
                self.respond(exc.status, {"error": {"message": safe_error(exc), "type": exc.code, "code": exc.code}})
    return Handler


def app_server_command(codex: str) -> list[str]:
    command = [codex, "app-server", "--listen", "stdio://", "-c", 'web_search="disabled"',
               "-c", "project_doc_max_bytes=0", "-c", "mcp_servers={}",
               "-c", "features.skip_host_skill_discovery=true"]
    for feature in DISABLED_FEATURES:
        command.extend(["--disable", feature])
    return command


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--codex", default="codex")
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/mumutestup-luna-text-workspace"))
    parser.add_argument("--audit-file", type=Path, required=True)
    parser.add_argument("--fatal-file", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, choices=range(1, 11), default=2)
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args()
    audit = Audit(args.audit_file)
    rpc = CodexRPC(app_server_command(args.codex), args.work_dir.resolve(), args.fatal_file, audit, args.timeout)
    bridge = LunaBridge(rpc, audit, args.concurrency, args.timeout)
    server = None
    try:
        rpc.start()
        server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(bridge))
        server.daemon_threads = True
        server.timeout = 0.5
        def shutdown(_signum, _frame):
            rpc.closed = True
        signal.signal(signal.SIGTERM, shutdown)
        signal.signal(signal.SIGINT, shutdown)
        print(canonical({"ready": True, "model": MODEL, "port": args.port, "route": ROUTE}), flush=True)
        while not rpc.closed:
            server.handle_request()
    finally:
        if server:
            server.server_close()
        rpc.close()


if __name__ == "__main__":
    main()
