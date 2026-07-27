#!/bin/bash
# =============================================================================
# sanddisp_env.sh
#
# Programme:  sanddisp_env
# Family:     Sanddisp / Sandbells host tooling
#
# Purpose
#   Enter the Sanddisp project directory, activate the Python venv, ensure
#   the LAN git daemon is up (via sandbells_git.sh), then drop into an
#   interactive Python prompt for development.
#
# Usage (must be sourced so the venv stays in your shell)
#   source ~/Code/Sanddisp/sanddisp_env.sh
#   # or from the project dir:
#   source ./sanddisp_env.sh
#
# Notes
#   If you execute this file instead of sourcing it, the venv activates only
#   for the script process and is lost when it exits.
# =============================================================================

ROOT="${HOME}/Code/Sanddisp"
cd "$ROOT" || {
  echo "sanddisp_env: cannot cd to $ROOT" >&2
  return 1 2>/dev/null || exit 1
}

if [ -f "$ROOT/venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source "$ROOT/venv/bin/activate"
else
  echo "sanddisp_env: no venv at $ROOT/venv — create it first" >&2
  return 1 2>/dev/null || exit 1
fi

if [ -x "$ROOT/sandbells_git.sh" ]; then
  "$ROOT/sandbells_git.sh" || echo "sanddisp_env: sandbells_git.sh reported a problem (continuing)" >&2
elif [ -f "$ROOT/sandbells_git.sh" ]; then
  bash "$ROOT/sandbells_git.sh" || echo "sanddisp_env: sandbells_git.sh reported a problem (continuing)" >&2
else
  echo "sanddisp_env: sandbells_git.sh not found — skip git daemon" >&2
fi

echo "sanddisp_env: $(pwd)  venv=${VIRTUAL_ENV:-?}  host=$(hostname -s)"
