#!/bin/zsh
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec arch -arm64 "$ROOT_DIR/.venv/bin/python3" "$@"
