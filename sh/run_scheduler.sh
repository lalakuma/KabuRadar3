#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"
python "$ROOT_DIR/src/kaburadar3/scheduling/launcher.py" "$@"
