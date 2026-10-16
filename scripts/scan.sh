#!/usr/bin/env bash
# Run Trivy against the repository: dependencies, secrets and misconfigurations.
# Usage: scripts/scan.sh [output-dir]   (default: scan-results)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT_DIR="${1:-$ROOT/scan-results}"
mkdir -p "$OUT_DIR"

if ! command -v trivy >/dev/null 2>&1; then
  echo "trivy not found. Install it: https://trivy.dev/latest/getting-started/installation/" >&2
  echo "  macOS:   brew install trivy" >&2
  echo "  Windows: winget install AquaSecurity.Trivy  (or: choco install trivy)" >&2
  echo "  Linux:   see the install page (apt/yum repos or release binaries)" >&2
  exit 127
fi

trivy --version

ARGS=(--scanners vuln,secret,misconfig --skip-dirs "$ROOT/.venv" --skip-dirs "$OUT_DIR")

# JSON for the normalizer, SARIF for GitHub code scanning, table for humans.
trivy fs "${ARGS[@]}" --format json  --output "$OUT_DIR/trivy-results.json"  "$ROOT"
trivy fs "${ARGS[@]}" --format sarif --output "$OUT_DIR/trivy-results.sarif" "$ROOT"
trivy fs "${ARGS[@]}" --format table "$ROOT"

echo "Results written to $OUT_DIR"
