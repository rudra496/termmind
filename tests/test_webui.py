"""Integration tests for TermMind Web UI endpoints."""

import socket
import threading
import time
from socketserver import ThreadingTCPServer

import httpx

from termmind.webui import WebUIRequestHandler


def get_free_port() -> int:
    """Find a free TCP port."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_webui_server_and_endpoints():
    """Test web server starting and all GET/POST API endpoints."""
    port = get_free_port()

    # Start local test server on background thread
    ThreadingTCPServer.allow_reuse_address = True
    server = ThreadingTCPServer(("127.0.0.1", port), WebUIRequestHandler)

    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    # Give the server a moment to spin up
    time.sleep(0.3)

    try:
        # 1. Test HTML loading
        resp = httpx.get(f"http://127.0.0.1:{port}/", timeout=5.0)
        assert resp.status_code == 200
        assert "TermMind — Workspace Console" in resp.text

        # 2. Test GET /api/status
        resp = httpx.get(f"http://127.0.0.1:{port}/api/status", timeout=5.0)
        assert resp.status_code == 200
        data = resp.json()
        assert "config" in data
        assert "presets" in data
        assert "workspace" in data

        # 3. Test GET /api/agents
        resp = httpx.get(f"http://127.0.0.1:{port}/api/agents", timeout=5.0)
        assert resp.status_code == 200
        agents = resp.json()
        assert len(agents) == 5
        assert agents[0]["name"] == "researcher"

        # 4. Test POST /api/config
        config_payload = {"provider": "ollama", "temperature": 0.4}
        resp = httpx.post(f"http://127.0.0.1:{port}/api/config", json=config_payload, timeout=5.0)
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"

        # 5. Test POST /api/command
        cmd_payload = {"command": "/help"}
        resp = httpx.post(f"http://127.0.0.1:{port}/api/command", json=cmd_payload, timeout=5.0)
        assert resp.status_code == 200
        assert "output" in resp.json()

    finally:
        # Shutdown server clean
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2.0)
