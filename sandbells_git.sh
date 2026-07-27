#!/bin/bash
# =============================================================================
# sandbells_git.sh
#
# Programme:  sandbells_git
# Family:     Sandbells shared / generic host tooling
#
# Purpose
#   Start a read-only git daemon so other machines on the LAN can
#   git clone / git pull over the git:// protocol without SSH.
#
#   This is intentionally host-agnostic: the same script is meant to
#   live on sanddisp, sandbells2, or any other Sandbells-related box.
#   Paths and advertised URLs are derived from the current account and
#   hostname, not hard-coded machine names.
#
# Serves
#   All git repos under:  ${HOME}/Code
#   Example URL:          git://$(hostname -s).local/<RepoName>
#   Port:                 9418 (git protocol)
#
# Behaviour
#   - If something is already listening on PORT, report and exit 0
#   - Otherwise start: git daemon --export-all --detach
#   - Confirm with ss(1); non-zero exit if the port never opens
#
# Usage
#   ./sandbells_git.sh
#   # from another host:
#   git clone git://$(hostname -s).local/Sanddisp
#
# Notes
#   Daemon only serves commits that exist on disk; commit locally first.
#   Firewall: allow TCP 9418 if ufw/iptables is enabled.
#   Prefer SSH remotes for everyday push; this is for convenient LAN pull.
# =============================================================================

set -e

BASE_PATH="${HOME}/Code"
PORT=9418
LOGTAG="sandbells-git"
HOST_SHORT="$(hostname -s 2>/dev/null || hostname)"

log() { echo "[$LOGTAG] $*"; }

if ss -ltn | grep -q ":${PORT} "; then
    log "already listening on port ${PORT} (user=${USER} host=${HOST_SHORT})"
    ss -ltnp | grep ":${PORT}" || true
    exit 0
fi

log "starting git daemon (user=${USER} host=${HOST_SHORT})"
log "  base-path=${BASE_PATH}  port=${PORT}"

git daemon --reuseaddr \
  --base-path="${BASE_PATH}" \
  --export-all \
  --verbose \
  --listen=0.0.0.0 \
  --port="${PORT}" \
  --detach

sleep 0.5

if ss -ltn | grep -q ":${PORT} "; then
    log "OK — git daemon is running"
    ss -ltnp | grep ":${PORT}" || true
    log "clone/pull example:  git clone git://${HOST_SHORT}.local/<RepoName>"
    log "repos are those under ${BASE_PATH}/<RepoName>"
    exit 0
else
    log "FAILED — nothing listening on ${PORT}"
    exit 1
fi
