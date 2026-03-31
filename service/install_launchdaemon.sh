#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

if [ "${EUID}" -ne 0 ]; then
    echo "Run this script with sudo: sudo $0"
    exit 1
fi

mkdir -p "$NANODLNA_LOG_DIR" "$SCRIPT_DIR/generated"

render_template() {
    local template_path="$1"
    local output_path="$2"

    sed \
        -e "s#__ROOT_DIR__#$NANODLNA_ROOT_DIR#g" \
        -e "s#__LOG_DIR__#$NANODLNA_LOG_DIR#g" \
        -e "s#__SERVICE_LABEL__#$NANODLNA_SERVICE_LABEL#g" \
        "$template_path" > "$output_path"
}

DAEMON_TEMPLATE="$SCRIPT_DIR/com.nanodlna.dashboard.daemon.plist.template"
DAEMON_RENDERED="$SCRIPT_DIR/generated/${NANODLNA_SERVICE_LABEL}.daemon.plist"
DAEMON_TARGET="/Library/LaunchDaemons/${NANODLNA_SERVICE_LABEL}.plist"

service_target="system/${NANODLNA_SERVICE_LABEL}"

service_is_loaded() {
    launchctl print "$service_target" >/dev/null 2>&1
}

bootout_best_effort() {
    launchctl bootout "$service_target" 2>/dev/null || true
    launchctl bootout system "$DAEMON_TARGET" 2>/dev/null || true
}

render_template "$DAEMON_TEMPLATE" "$DAEMON_RENDERED"
cp "$DAEMON_RENDERED" "$DAEMON_TARGET"
chown root:wheel "$DAEMON_TARGET"
chmod 644 "$DAEMON_TARGET"

# Stop old user LaunchAgent if present (best effort)
if [ -n "${SUDO_UID:-}" ]; then
    launchctl bootout "gui/${SUDO_UID}/${NANODLNA_SERVICE_LABEL}" 2>/dev/null || true
fi

# Reload system daemon
bootout_best_effort

if ! launchctl bootstrap system "$DAEMON_TARGET"; then
    if service_is_loaded; then
        echo "LaunchDaemon already loaded; reusing existing job and forcing restart."
    else
        echo "Error: failed to bootstrap $service_target"
        echo "Try checking:"
        echo "  sudo launchctl print $service_target"
        echo "  tail -n 80 $NANODLNA_LOG_DIR/launchd-dashboard.err.log"
        exit 1
    fi
fi

launchctl enable "$service_target" 2>/dev/null || true
launchctl kickstart -k "$service_target"

echo "Installed and started system LaunchDaemon:"
echo "  $DAEMON_TARGET"
echo ""
echo "Manage it with:"
echo "  sudo ./service/dashboard_service.sh restart"
echo "  sudo ./service/dashboard_service.sh status"
