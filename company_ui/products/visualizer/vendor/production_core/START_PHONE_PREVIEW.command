#!/bin/bash
cd "$(dirname "$0")"
PYTHON_BIN="$(command -v python3 || command -v python)"
if [ -z "$PYTHON_BIN" ]; then
  echo "Python 3 is required to run the local preview server."
  read -r -p "Press Enter to close..."
  exit 1
fi
exec "$PYTHON_BIN" PHONE_PREVIEW_SERVER.py
