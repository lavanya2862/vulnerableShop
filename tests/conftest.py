"""Shared fixtures: an isolated database per test and a loopback-only mock HTTP server."""

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
from fastapi.testclient import TestClient

from app.main import app

PUBLIC_MARKER = "PUBLIC_MOCK_CONTENT"
INTERNAL_MARKER = "INTERNAL_ONLY_MOCK_MARKER"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VULNSHOP_DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("VULNSHOP_ALLOWED_FETCH_HOSTS", "example.test")
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


class _MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        port = self.server.server_address[1]
        if self.path == "/public":
            self._send(200, PUBLIC_MARKER)
        elif self.path == "/internal":
            self._send(200, INTERNAL_MARKER)
        elif self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", f"http://127.0.0.1:{port}/internal")
            self.end_headers()
        else:
            self._send(404, "not found")

    def _send(self, code, body):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="session")
def mock_server_port():
    """Mock service bound to 127.0.0.1 only; stands in for both an allowed and an internal service."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _MockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
