#!/usr/bin/env bash
set -euo pipefail

BRAIN_URL="${BRAIN_URL:-https://brain.bioinfo.pro}"
BRAIN_TOKEN_FILE="${BRAIN_TOKEN_FILE:-${HOME}/.config/brain/token}"
BRAIN_URL_FILE="${BRAIN_URL_FILE:-${HOME}/.config/brain/url}"
SKILL_DIR="${BRAIN_LOOP_SKILL_ROOT:-${HOME}/.local/share/brain-loop}"
CLIENT="${SKILL_DIR}/scripts/brain.py"
LOG_TAG="[brain-sync]"

log() { printf '%s %s %s\n' "$(date +%Y-%m-%d_%H:%M:%S)" "$LOG_TAG" "$1"; }
fetch() {
  local source="$1" destination="$2"
  local tmp="${destination}.tmp"
  mkdir -p "$(dirname "$destination")"
  curl -fsS --connect-timeout 30 --max-time 120 "$source" -o "$tmp"
  test -s "$tmp"
  mv "$tmp" "$destination"
}

if [[ -f "$BRAIN_URL_FILE" ]]; then
  BRAIN_URL="$(<"$BRAIN_URL_FILE")"
fi
export BRAIN_URL BRAIN_TOKEN_FILE

if [[ "${1:-}" == "propose-file" ]]; then
  proposal="${2:-}"
  if [[ -z "$proposal" || ! -f "$proposal" ]]; then
    log "ERROR: canonical JSON proposal file is required"
    exit 1
  fi
  if [[ ! -f "$CLIENT" ]]; then
    log "ERROR: canonical Brain client not found at $CLIENT"
    exit 1
  fi
  log "Submitting canonical proposal: $proposal"
  python3 "$CLIENT" propose "$proposal" --wait --timeout 90
  exit $?
fi

log "Syncing Brain exports"
fetch "${BRAIN_URL}/exports/global/codex-instructions.md" "${HOME}/.codex/instructions.md"
fetch "${BRAIN_URL}/exports/global/memory-header.md" "${HOME}/.codex/memories/MEMORY.md"
fetch "${BRAIN_URL}/exports/global/CLAUDE.md" "${HOME}/.claude/CLAUDE.md"
fetch "${BRAIN_URL}/exports/global/KNOWLEDGE.md" "${HOME}/hermes-sync/exports/global/KNOWLEDGE.md"
fetch "${BRAIN_URL}/exports/global/brain-context.md" "${HOME}/.hermes/brain-context.md"
log "Done"

# Usage: brain-sync-hpc.sh propose-file /path/to/lesson.json
