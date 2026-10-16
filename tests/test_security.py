"""Security regression tests.

Each test asserts the SECURE behaviour for one ground-truth entry (see the
`gt` marker). On the secure code they pass; once the corresponding flaw is
introduced they should fail; after a correct remediation they should pass again.

All payloads are inert: injection probes only try to echo a marker string,
SSRF probes only target the loopback mock server or a temp file the test creates.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from app.config import get_settings
from tests.conftest import INTERNAL_MARKER

PROJECT_ROOT = Path(__file__).resolve().parents[1]
INJECTION_MARKER = "VULNSHOP_INJECTION_MARKER"


# --- VULN-001: SQL injection in GET /products/search -------------------------

@pytest.mark.gt("VULN-001")
def test_search_treats_sql_syntax_as_literal_text(client):
    response = client.get("/products/search", params={"q": "zzz%' OR 1=1 --"})
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.gt("VULN-001")
def test_search_with_quote_does_not_error_or_leak_sql(client):
    response = client.get("/products/search", params={"q": "O'Brien"})
    assert response.status_code == 200
    assert response.json() == []
    assert "sqlite" not in response.text.lower()
    assert "syntax" not in response.text.lower()


@pytest.mark.gt("VULN-001")
def test_search_cannot_read_users_table(client):
    payload = "zzz%' UNION SELECT id, email, name, 1.0, 1 FROM users --"
    response = client.get("/products/search", params={"q": payload})
    assert "@shop.test" not in response.text


# --- VULN-002: command injection in GET /diagnostics/ping --------------------

@pytest.mark.gt("VULN-002")
@pytest.mark.parametrize(
    "host",
    [
        f"127.0.0.1; echo {INJECTION_MARKER}",
        f"127.0.0.1 && echo {INJECTION_MARKER}",
        f"127.0.0.1 | echo {INJECTION_MARKER}",
        f"$(echo {INJECTION_MARKER})",
        f"`echo {INJECTION_MARKER}`",
    ],
)
def test_ping_rejects_shell_metacharacters(client, host):
    response = client.get("/diagnostics/ping", params={"host": host})
    # A 422 validation error may echo the input back, so only the status is asserted here;
    # a vulnerable implementation returns 200 with the marker in its output.
    assert response.status_code in (400, 422)


@pytest.mark.gt("VULN-002")
def test_ping_rejects_option_injection(client):
    response = client.get("/diagnostics/ping", params={"host": "-w 1 127.0.0.1"})
    assert response.status_code in (400, 422)


# --- VULN-003: SSRF in POST /fetch-url ---------------------------------------

@pytest.mark.gt("VULN-003")
def test_fetch_url_blocks_loopback_service(client, mock_server_port):
    response = client.post("/fetch-url", json={"url": f"http://127.0.0.1:{mock_server_port}/internal"})
    assert response.status_code == 400
    assert INTERNAL_MARKER not in response.text


@pytest.mark.gt("VULN-003")
def test_fetch_url_blocks_hosts_not_on_allowlist(client, mock_server_port):
    response = client.post("/fetch-url", json={"url": f"http://localhost:{mock_server_port}/internal"})
    assert response.status_code == 400
    assert INTERNAL_MARKER not in response.text


@pytest.mark.gt("VULN-003")
def test_fetch_url_blocks_file_scheme(client, tmp_path):
    marker_file = tmp_path / "local.txt"
    marker_file.write_text(INTERNAL_MARKER)
    response = client.post("/fetch-url", json={"url": marker_file.as_uri()})
    assert response.status_code == 400
    assert INTERNAL_MARKER not in response.text


@pytest.mark.gt("VULN-003")
def test_fetch_url_does_not_follow_redirect_to_internal(client, monkeypatch, mock_server_port):
    monkeypatch.setenv("VULNSHOP_ALLOWED_FETCH_HOSTS", f"localhost:{mock_server_port}")
    response = client.post("/fetch-url", json={"url": f"http://localhost:{mock_server_port}/redirect"})
    assert INTERNAL_MARKER not in response.text


# --- VULN-004: hardcoded secret ----------------------------------------------

SECRET_NAME = r"[A-Za-z_]*(?:API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD)[A-Za-z_]*"
HARDCODED_ASSIGNMENT = re.compile(
    rf"(?i)\b{SECRET_NAME}\s*(?::\s*[\w\[\]| ]+)?=\s*[rbuf]?[\"'][^\"']{{8,}}[\"']"
)
HARDCODED_DEFAULT = re.compile(
    rf"(?i)getenv\(\s*[\"']{SECRET_NAME}[\"']\s*,\s*[\"'][^\"']{{8,}}[\"']"
)


@pytest.mark.gt("VULN-004")
def test_no_hardcoded_secrets_in_application_source():
    offenders = []
    for path in (PROJECT_ROOT / "app").rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if HARDCODED_ASSIGNMENT.search(line) or HARDCODED_DEFAULT.search(line):
                offenders.append(f"{path.relative_to(PROJECT_ROOT)}:{lineno}")
    assert offenders == [], f"Possible hardcoded secrets: {offenders}"


@pytest.mark.gt("VULN-004")
def test_demo_api_key_is_read_from_environment(monkeypatch):
    monkeypatch.delenv("VULNSHOP_DEMO_API_KEY", raising=False)
    assert get_settings().demo_api_key is None
    monkeypatch.setenv("VULNSHOP_DEMO_API_KEY", "value-from-env")
    assert get_settings().demo_api_key == "value-from-env"


# --- VULN-005: vulnerable dependency -----------------------------------------

REQUIREMENTS = PROJECT_ROOT / "requirements.txt"


def _requirement_lines():
    for raw in REQUIREMENTS.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            yield line


@pytest.mark.gt("VULN-005")
def test_all_requirements_are_pinned():
    unpinned = [line for line in _requirement_lines() if "==" not in line]
    assert unpinned == []


@pytest.mark.gt("VULN-005")
@pytest.mark.network
def test_requirements_have_no_known_vulnerabilities():
    if importlib.util.find_spec("pip_audit") is None:
        pytest.skip("pip-audit not installed (pip install -r requirements-dev.txt)")
    result = subprocess.run(
        [sys.executable, "-m", "pip_audit", "-r", str(REQUIREMENTS), "--no-deps",
         "--format", "json", "--progress-spinner", "off"],
        capture_output=True, text=True, timeout=600, check=False,
    )
    if result.returncode not in (0, 1):
        pytest.skip(f"pip-audit could not run (network?): {result.stderr.strip()[-300:]}")
    report = json.loads(result.stdout)
    vulnerable = {
        f"{dep['name']}=={dep['version']}": [v["id"] for v in dep["vulns"]]
        for dep in report["dependencies"]
        if dep.get("vulns")
    }
    assert vulnerable == {}, f"Known-vulnerable dependencies: {vulnerable}"
