# VulnerableShop

A small FastAPI + SQLite shop API used as a **test target** for a security scanning and
AI-remediation pipeline. All users, products, orders and keys are fictional.

> **Do not deploy.** This project exists to have security flaws introduced into it and then
> removed by an automated pipeline. Run it only on `127.0.0.1` in an isolated environment.

## Current state

The code in this repository is the **secure baseline**. The five ground-truth flaws in
[`security/ground_truth.json`](security/ground_truth.json) are **not yet introduced**
(`"status": "not_introduced"`). See *Introducing the test flaws* below.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| GET | `/health` | Health status |
| GET | `/products` | List products |
| GET | `/products/search?q=phone` | Search name/description |
| GET | `/products/{product_id}` | One product |
| POST | `/products` | Create product (`name`, `description`, `price`, `stock`) |
| GET | `/users/{user_id}/orders` | Orders for a user |
| POST | `/fetch-url` | `{"url": "..."}`; host must be in `VULNSHOP_ALLOWED_FETCH_HOSTS` |
| GET | `/diagnostics/ping?host=127.0.0.1` | Single ping to a validated host |

Interactive docs: http://127.0.0.1:8000/docs

## Configuration (environment variables)

| Variable | Default | Purpose |
|---|---|---|
| `VULNSHOP_DB_PATH` | `vulnerable_shop.db` | SQLite file (created and seeded on startup) |
| `VULNSHOP_ALLOWED_FETCH_HOSTS` | `example.test` | Comma-separated `host` or `host:port` allowlist for `/fetch-url` |
| `VULNSHOP_DEMO_API_KEY` | unset | Fictional key, read from env only |
| `VULNSHOP_FETCH_TIMEOUT` | `5` | Seconds |
| `VULNSHOP_MAX_FETCH_BYTES` | `65536` | Response body cap |

## Install and run

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1
```

## Tests

```bash
pip install -r requirements-dev.txt   # adds pip-audit for the dependency test
pytest -v                             # everything
pytest tests/test_app.py              # functional tests (must always pass)
pytest tests/test_security.py         # security regression tests
pytest -m "not network"               # skip the pip-audit test (needs internet)
```

- `tests/test_app.py`: functional behaviour. Must pass before and after remediation.
- `tests/test_security.py`: asserts the **secure** behaviour for each ground-truth entry
  (linked with `@pytest.mark.gt("VULN-00X")`). They pass on the secure baseline, should
  **fail once a flaw is introduced**, and should **pass again after a correct fix**.
- SSRF tests use a mock HTTP server bound to `127.0.0.1` on a random port; injection probes
  only attempt to echo a marker string. Nothing touches external hosts (except pip-audit,
  which queries the PyPI/OSV advisory databases).

## Trivy

Install: https://trivy.dev/latest/getting-started/installation/
(`brew install trivy`, `winget install AquaSecurity.Trivy`, or a release binary).

```bash
bash scripts/scan.sh            # writes scan-results/trivy-results.{json,sarif}
```

Equivalent single command:

```bash
trivy fs --scanners vuln,secret,misconfig --skip-dirs .venv --format json --output trivy-results.json .
```

Note: Trivy reads `requirements.txt` as written and does not resolve transitive
dependencies, which is why every package is pinned there.

## CodeQL (GitHub Actions)

`.github/workflows/codeql.yml` analyses Python with the `security-extended` suite on pushes
and PRs to `main`, and on manual dispatch. It uploads results to the repository's
**Security → Code scanning** tab and also saves the SARIF as the `codeql-sarif` artifact.

1. Push this folder as the root of a GitHub repository (`.github/` must be at the repo root).
2. Public repos: code scanning is free. Private repos need GitHub Code Security
   (Advanced Security); without it the upload step fails, but the SARIF artifact is still saved.
3. Run it from **Actions → CodeQL → Run workflow**, or push to `main`.

It cannot be run locally as a workflow. The local alternative is the
[CodeQL CLI](https://github.com/github/codeql-cli-binaries):

```bash
codeql database create codeql-db --language=python --source-root .
codeql database analyze codeql-db codeql/python-queries:codeql-suites/python-security-extended.qls \
  --format=sarif-latest --output=codeql-results.sarif --download
```

## Introducing the test flaws

`security/ground_truth.json` lists each flaw's file, function, current line, the
regression tests that cover it and the expected remediation. After you modify the code:

1. Update `status` to `"introduced"` and correct `line`. For VULN-005, fill in
   `dependency`, `advisory_id` and `fixed_version` from an authoritative advisory (OSV.dev / GHSA).
2. Run `pytest tests/test_security.py -v` and confirm the linked tests now fail.
3. Run `pytest tests/test_app.py` and confirm functional tests still pass.

The ground-truth file is for **evaluating** the pipeline. Do not give it to the remediation agent.
