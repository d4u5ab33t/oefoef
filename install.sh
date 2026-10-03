#!/usr/bin/env bash
# OIDASHEIM Quick Installer — forwards to setup_and_fix.sh
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
bash "$DIR/setup_and_fix.sh" "$@"
