#!/bin/bash
# sandbells_git.sh — start git daemon for LAN clones/pulls
# Serves repos under BASE_PATH (e.g. git://sanddisp.local/Sanddisp)

set -e

BASE_PATH="${HOME}/Code"
PORT=9418
LOGTAG="sandbells-git"

log() { echo "[$LOGTAG] $*"; }

if ss -ltn | grep -q ":${PORT} "; then
    log "already listening on port ${PORT}"
    ss -ltnp | grep ":${PORT}" || true
    exit 0
fi

log "starting git daemon (base-path=${BASE_PATH}, port=${PORT})"
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
    log "clone/pull example:  git clone git://$(hostname -s).local/Sanddisp"
    exit 0
else
    log "FAILED — nothing listening on ${PORT}"
    exit 1
fi
