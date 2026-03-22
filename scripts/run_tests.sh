#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=apps
export LOG_LEVEL=WARNING
exec python -m pytest tests "$@"
