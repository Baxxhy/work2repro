import http.client
import pathlib
import socket
import subprocess
import time
import urllib.error
import urllib.request

import pytest

from conftest import EXECUTABLE, make_book, run_mdbook


def wait_for_port(host, port, proc, timeout=12):
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            raise AssertionError("serve exited early")
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.1)
    raise AssertionError("serve did not listen")


def test_serve_delivers_html_assets_head_and_range(tmp_path):
    root = make_book(tmp_path / "book")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([str(EXECUTABLE), "serve", "--hostname", "127.0.0.1", "--port", str(port), str(root)],
                            cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_for_port("127.0.0.1", port, proc)
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        conn.request("GET", "/")
        response = conn.getresponse(); body = response.read()
        assert response.status == 200 and response.getheader("Content-Type").startswith("text/html")
        assert b"Hello world" in body
        conn.request("HEAD", "/")
        head = conn.getresponse(); assert head.status == 200 and head.read() == b""
        conn.request("GET", "/index.html", headers={"Range": "bytes=0-99"})
        ranged = conn.getresponse(); data = ranged.read()
        assert ranged.status == 206 and len(data) == 100
        assert ranged.getheader("Content-Range", "").startswith("bytes 0-99/")
        assert ranged.getheader("Accept-Ranges") == "bytes"
        conn.close()
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()


def test_serve_missing_path_returns_404(tmp_path):
    root = make_book(tmp_path / "book")
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]
    proc = subprocess.Popen([str(EXECUTABLE), "serve", "-n", "127.0.0.1", "-p", str(port), str(root)],
                            cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        wait_for_port("127.0.0.1", port, proc)
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/absent") as response:
            assert response.status == 404
    except urllib.error.HTTPError as error:
        assert error.code == 404
        assert error.read()
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()


def test_watch_waits_without_initial_output_then_rebuilds(tmp_path):
    root = make_book(tmp_path / "book")
    proc = subprocess.Popen([str(EXECUTABLE), "watch", str(root)], cwd=tmp_path,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        # Allow startup polling without imposing a strict timing threshold.
        time.sleep(1.5)
        assert not (root / "book").exists()
        (root / "src" / "chapter_1.md").write_text("# Chapter 1\n\nUpdated by watch.\n")
        deadline = time.time() + 15
        while time.time() < deadline:
            if (root / "book" / "index.html").exists() and "Updated by watch" in (root / "book" / "index.html").read_text():
                break
            if proc.poll() is not None:
                raise AssertionError("watch exited early")
            time.sleep(0.25)
        else:
            raise AssertionError("watch did not rebuild after source change")
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait()


def test_serve_invalid_port_is_operational_error(tmp_path):
    root = make_book(tmp_path / "book")
    p = run_mdbook("serve", "--port", "70000", root, timeout=20)
    assert p.returncode != 0 and "invalid port value" in p.stderr

