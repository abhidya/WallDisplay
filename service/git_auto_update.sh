#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/../scripts/common_env.sh"

mkdir -p "$NANODLNA_LOG_DIR"
UPDATE_LOG="$NANODLNA_LOG_DIR/git-updater.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$UPDATE_LOG"
}

if [ "$NANODLNA_GIT_AUTO_UPDATE" != "1" ]; then
    log "Git auto-update disabled"
    exit 0
fi

cd "$NANODLNA_ROOT_DIR"

if ! git diff --quiet || ! git diff --cached --quiet; then
    log "Skipping update because the worktree has local changes"
    exit 0
fi

git fetch "$NANODLNA_GIT_REMOTE" "$NANODLNA_GIT_BRANCH" >> "$UPDATE_LOG" 2>&1

LOCAL_SHA="$(git rev-parse HEAD)"
REMOTE_SHA="$(git rev-parse "$NANODLNA_GIT_REMOTE/$NANODLNA_GIT_BRANCH")"

if [ "$LOCAL_SHA" = "$REMOTE_SHA" ]; then
    log "No remote changes detected"
    exit 0
fi

if ! git merge-base --is-ancestor "$LOCAL_SHA" "$REMOTE_SHA"; then
    log "Skipping update because fast-forward is not possible"
    exit 0
fi

log "Applying fast-forward update from $LOCAL_SHA to $REMOTE_SHA"
git pull --ff-only "$NANODLNA_GIT_REMOTE" "$NANODLNA_GIT_BRANCH" >> "$UPDATE_LOG" 2>&1
/bin/launchctl kickstart -k "gui/${UID}/${NANODLNA_SERVICE_LABEL}" >> "$UPDATE_LOG" 2>&1
log "Restarted $NANODLNA_SERVICE_LABEL after update"
