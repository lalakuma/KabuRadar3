#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/_env.sh"
bash "$(dirname "$0")/update_prices.sh" --menu auto
bash "$(dirname "$0")/analyze.sh"
echo "Completed: screening.sh"
