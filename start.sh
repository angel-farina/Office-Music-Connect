#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  printf 'Se creó .env desde .env.example. Configura APP_ACCESS_TOKEN y APP_SECRET_KEY y vuelve a ejecutar start.sh.\n' >&2
  exit 1
fi

PYTHON="$ROOT_DIR/.venv/Scripts/python.exe"
if [[ ! -x "$PYTHON" ]]; then
  if command -v py >/dev/null 2>&1; then
    py -3.12 -m venv "$ROOT_DIR/.venv"
  elif command -v python >/dev/null 2>&1; then
    python -m venv "$ROOT_DIR/.venv"
  else
    printf 'No se encontró Python. Instala Python 3.12 y vuelve a ejecutar start.sh.\n' >&2
    exit 1
  fi
fi

if ! "$PYTHON" -c 'import fastapi, playwright, uvicorn' >/dev/null 2>&1; then
  "$PYTHON" -m pip install -r "$ROOT_DIR/requirements.txt"
fi

exec "$PYTHON" -c 'from app.core.config import get_settings; import uvicorn; settings = get_settings(); uvicorn.run("app.main:app", host=settings.app_host, port=settings.app_port)'
