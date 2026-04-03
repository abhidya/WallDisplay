#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

SERVICE_TARGET="system/${NANODLNA_SERVICE_LABEL}"
DAEMON_TARGET="/Library/LaunchDaemons/${NANODLNA_SERVICE_LABEL}.plist"

require_root() {
    if [ "${EUID}" -ne 0 ]; then
        echo "Run this command with sudo: sudo $0 $*"
        exit 1
    fi
}

print_usage() {
    cat <<EOF
Usage: sudo ./service/dashboard_service.sh <command>

Commands:
  install    Install or refresh the LaunchDaemon plist and start it
  restart    Restart the loaded LaunchDaemon
  start      Start the LaunchDaemon if installed
  stop       Stop the LaunchDaemon
  status     Print launchd status for the service
  logs       Tail recent launchd and dashboard logs
EOF
}

cmd="${1:-status}"

case "$cmd" in
    install)
        require_root "$cmd"
        exec "$SCRIPT_DIR/install_launchdaemon.sh"
        ;;
    restart)
        require_root "$cmd"
        if [ ! -f "$DAEMON_TARGET" ]; then
            echo "LaunchDaemon plist not installed yet: $DAEMON_TARGET"
            echo "Run: sudo ./service/dashboard_service.sh install"
            exit 1
        fi
        launchctl enable "$SERVICE_TARGET" 2>/dev/null || true
        launchctl kickstart -k "$SERVICE_TARGET"
        echo "Restarted $SERVICE_TARGET"
        ;;
    start)
        require_root "$cmd"
        if [ ! -f "$DAEMON_TARGET" ]; then
            echo "LaunchDaemon plist not installed yet: $DAEMON_TARGET"
            echo "Run: sudo ./service/dashboard_service.sh install"
            exit 1
        fi
        if ! launchctl print "$SERVICE_TARGET" >/dev/null 2>&1; then
            launchctl bootstrap system "$DAEMON_TARGET"
        fi
        launchctl enable "$SERVICE_TARGET" 2>/dev/null || true
        launchctl kickstart -k "$SERVICE_TARGET"
        echo "Started $SERVICE_TARGET"
        ;;
    stop)
        require_root "$cmd"
        launchctl bootout "$SERVICE_TARGET" 2>/dev/null || launchctl bootout system "$DAEMON_TARGET" 2>/dev/null || true
        echo "Stopped $SERVICE_TARGET"
        ;;
    status)
        require_root "$cmd"
        launchctl print "$SERVICE_TARGET"
        ;;
    logs)
        tail -n 80 \
            "$NANODLNA_LOG_DIR/launchd-dashboard.err.log" \
            "$NANODLNA_LOG_DIR/launchd-dashboard.out.log" \
            "$NANODLNA_LOG_DIR/dashboard_run.log" 2>/dev/null || true
        ;;
    *)
        print_usage
        exit 1
        ;;
esac
