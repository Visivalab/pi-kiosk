#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$ROOT/src"

if [[ "${EUID}" -ne 0 ]]; then
  exec sudo PYTHONPATH="$ROOT/src" python3 -m pi_kiosk "$@"
fi

exec python3 -m pi_kiosk "$@"
