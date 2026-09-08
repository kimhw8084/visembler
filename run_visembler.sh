#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"

if [[ -n "${VISSEMBLER_PYTHON:-}" ]]; then
  PY="$(command -v "$VISSEMBLER_PYTHON" 2>/dev/null || true)"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PY="$ROOT/.venv/bin/python"
else
  PY="$(command -v python3 || true)"
fi

if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "ERROR: Python 3.11–3.13 was not found. Set VISSEMBLER_PYTHON or create .venv."
  exit 1
fi

if ! "$PY" - <<'PY'
import sys
if not (3, 11) <= sys.version_info[:2] < (3, 14):
    raise SystemExit('Python 3.11, 3.12, or 3.13 is required.')
PY
then
  echo "ERROR: unsupported Python runtime: $("$PY" --version 2>&1)"
  exit 1
fi

if ! "$PY" -c 'import nicegui' >/dev/null 2>&1; then
  echo "ERROR: NiceGUI is not installed in $PY."
  echo "Install the company-approved runtime with: $PY -m pip install -r $ROOT/requirements.txt"
  exit 1
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
export COMPANY_UI_ENVIRONMENT="${COMPANY_UI_ENVIRONMENT:-dev}"
export COMPANY_UI_HOST="${COMPANY_UI_HOST:-127.0.0.1}"
export COMPANY_UI_PORT="${COMPANY_UI_PORT:-${PORT:-8080}}"
export COMPANY_UI_VISUALIZER_DATA_DIR="${COMPANY_UI_VISUALIZER_DATA_DIR:-$HOME/.company_ui/visualizer}"

echo "Starting Visembler"
echo "  URL: http://127.0.0.1:${COMPANY_UI_PORT}/visualizer"
echo "  host: ${COMPANY_UI_HOST}"
echo "  data: ${COMPANY_UI_VISUALIZER_DATA_DIR}"
exec "$PY" -m company_ui.products.visualizer.cli
