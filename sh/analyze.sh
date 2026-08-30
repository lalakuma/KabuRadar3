#!/usr/bin/env bash
set -euo pipefail
# shellcheck source=_env.sh
source "$(dirname "$0")/_env.sh"
python "$ROOT_DIR/src/kaburadar3/cli/analyze.py" "$@"
echo "Completed: analyze.sh"
