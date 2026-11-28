#!/usr/bin/env bash
set -euo pipefail

BRAIN_URL="${BRAIN_URL:-http://127.0.0.1:8083}"
BRAIN_TOKEN_FILE="${BRAIN_TOKEN_FILE:-${HOME}/.config/brain/token}"
BRAIN_URL_FILE="${BRAIN_URL_FILE:-${HOME}/.config/brain/url}"
SKILL_DIR="${BRAIN_LOOP_SKILL_ROOT:-${HOME}/.local/share/brain-loop}"
CLIENT="${SKILL_DIR}/scripts/brain.py"
LOG_TAG="[brain-sync]"
log() { printf '%s %s %s\n' "$(date +%Y-%m-%d_%H:%M:%S)" "$LOG_TAG" "$1"; }
if [[ -f "$BRAIN_URL_FILE" ]]; then BRAIN_URL="$(<"$BRAIN_URL_FILE")"; fi
export BRAIN_URL BRAIN_TOKEN_FILE

if [[ "${1:-}" == "propose-file" ]]; then
  proposal="${2:-}"
  if [[ -z "$proposal" || ! -f "$proposal" ]]; then log "ERROR: canonical JSON proposal file is required"; exit 1; fi
  if [[ ! -f "$CLIENT" ]]; then log "ERROR: canonical Brain client not found at $CLIENT"; exit 1; fi
  python3 "$CLIENT" propose "$proposal" --wait --timeout 90
  exit $?
fi

log "Syncing authenticated client and shared exports"
# Read credentials from the existing private token file. They never enter argv.
# Prepare every download before replacing any installed file.
python3 - "$SKILL_DIR" <<'PY'
from pathlib import Path
import os,ssl,sys,tempfile,urllib.request,urllib.parse
root=Path(sys.argv[1]).expanduser()
origin=os.environ['BRAIN_URL'].rstrip('/')
u=urllib.parse.urlparse(origin)
if u.scheme not in ('http','https') or (u.scheme=='http' and u.hostname not in ('localhost','127.0.0.1','::1')) or u.username or u.password or u.path or u.query or u.fragment:
    raise SystemExit('BRAIN_URL must be an HTTPS origin or loopback HTTP')
token=Path(os.environ['BRAIN_TOKEN_FILE']).expanduser().read_text().strip()
if not token:raise SystemExit('Brain token file is empty')
headers={'Authorization':'Bearer '+token,'User-Agent':'brain-sync/1.4.2'}
ctx=None
ca=os.environ.get('BRAIN_CA_BUNDLE','')
if not ca:
    ca_file=Path.home()/'.config/brain/ca-bundle'
    if ca_file.is_file():ca=ca_file.read_text().strip()
if u.scheme=='https' and ca:ctx=ssl.create_default_context(cafile=ca)
items={
 '/skills/brain-loop/scripts/brain.py':root/'scripts/brain.py',
 '/skills/brain-loop/scripts/brain-sync-hpc.sh':root/'scripts/brain-sync-hpc.sh',
 '/skills/brain-loop/templates/proposal.json':root/'templates/proposal.json',
 '/skills/brain-loop/SKILL.md':root/'SKILL.md',
 '/skills/brain-loop/references/protocol.md':root/'references/protocol.md',
 '/skills/brain-loop/references/codex-workflow.md':root/'references/codex-workflow.md',
 '/exports/global/CLAUDE.md':Path.home()/'.claude/CLAUDE.md',
 '/exports/global/KNOWLEDGE.md':Path.home()/'hermes-sync/exports/global/KNOWLEDGE.md',
 '/exports/global/brain-context.md':Path.home()/'.hermes/brain-context.md',
}
pending=[]
try:
    for source,destination in items.items():
        req=urllib.request.Request(origin+source,headers=headers)
        with urllib.request.urlopen(req,timeout=30,context=ctx) as response:data=response.read()
        if not data:raise RuntimeError('Empty Brain asset')
        destination.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=destination.parent,delete=False) as f:
            f.write(data);pending.append((Path(f.name),destination))
    for temporary,destination in pending:
        temporary.chmod(0o755 if destination.suffix=='.sh' else 0o644);temporary.replace(destination)
    import shutil
    instructions=Path.home()/'.codex/instructions.md'
    instructions.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(root/'references/codex-workflow.md',instructions)
    for installed in [Path.home()/'.agents/skills/brain-loop',Path.home()/'.codex/skills/brain-loop',Path.home()/'.claude/skills/brain-loop']:
        if installed.is_dir() and installed.resolve()!=root.resolve():
            shutil.copytree(root,installed,dirs_exist_ok=True)
finally:
    for temporary,_ in pending:temporary.unlink(missing_ok=True)
PY
python3 "$CLIENT" context-export --output "${HOME}/hermes-sync/exports/environment.md"
log "Done; reconnect persistent clients to load updated tool schemas"
# Usage: brain-sync-hpc.sh propose-file /path/to/lesson.json
