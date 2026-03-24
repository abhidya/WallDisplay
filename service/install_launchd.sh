#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

mkdir -p "$NANODLNA_LOG_DIR" "$SCRIPT_DIR/generated" "$HOME/Library/LaunchAgents"

render_template() {
    local template_path="$1"
    local output_path="$2"

    sed \
        -e "s#__ROOT_DIR__#$NANODLNA_ROOT_DIR#g" \
        -e "s#__LOG_DIR__#$NANODLNA_LOG_DIR#g" \
        -e "s#__SERVICE_LABEL__#$NANODLNA_SERVICE_LABEL#g" \
        "$template_path" > "$output_path"
}

DASHBOARD_PLIST="$SCRIPT_DIR/generated/${NANODLNA_SERVICE_LABEL}.plist"
UPDATER_PLIST="$SCRIPT_DIR/generated/${NANODLNA_SERVICE_LABEL}.git-updater.plist"

render_template "$SCRIPT_DIR/com.nanodlna.dashboard.plist.template" "$DASHBOARD_PLIST"
render_template "$SCRIPT_DIR/com.nanodlna.dashboard.git-updater.plist.template" "$UPDATER_PLIST"

cp "$DASHBOARD_PLIST" "$HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.plist"
cp "$UPDATER_PLIST" "$HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.git-updater.plist"

/bin/launchctl bootout "gui/${UID}/${NANODLNA_SERVICE_LABEL}" 2>/dev/null || true
/bin/launchctl bootout "gui/${UID}/${NANODLNA_SERVICE_LABEL}.git-updater" 2>/dev/null || true
/bin/launchctl bootstrap "gui/${UID}" "$HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.plist"
/bin/launchctl bootstrap "gui/${UID}" "$HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.git-updater.plist"

echo "Installed launchd agents:"
echo "  $HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.plist"
echo "  $HOME/Library/LaunchAgents/${NANODLNA_SERVICE_LABEL}.git-updater.plist"
echo ""
echo "Manage them with:"
echo "  launchctl kickstart -k gui/${UID}/${NANODLNA_SERVICE_LABEL}"
echo "  launchctl print gui/${UID}/${NANODLNA_SERVICE_LABEL}"
