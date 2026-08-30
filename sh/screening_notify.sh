#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"
bash "$(dirname "$0")/update_prices.sh" --menu 6
python "$ROOT_DIR/src/kaburadar3/cli/screening.py" --skip-update --notify
echo "Completed: screening_notify.sh"
