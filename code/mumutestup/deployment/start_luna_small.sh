#!/usr/bin/env bash
set -euo pipefail
source /root/Baxxhy/work2/reproductions/mumutestup/deployment/runtime-luna.sh

# Optional arguments are deliberately limited to inspection. A new experiment
# gets a new MUMU_LUNA_OUTPUT; resuming or changing the sample set is explicit work.
if [[ $# -gt 1 || ( $# -eq 1 && "$1" != "--preflight-only" ) ]]; then
    echo 'Usage: MUMU_LUNA_OUTPUT=/absolute/new/run bash start_luna_small.sh [--preflight-only]' >&2
    exit 2
fi
if [[ -e "$MUMU_LUNA_OUTPUT/status.json" ]]; then
    echo "Output already contains a run: $MUMU_LUNA_OUTPUT" >&2
    exit 2
fi
if [[ -e "$MUMU_LLM_FATAL_FILE" ]]; then
    echo "Bridge fatal marker exists; resolve the failure and use a new run directory: $MUMU_LLM_FATAL_FILE" >&2
    exit 2
fi

python "$MUMU_ROOT/deployment/patch_luna_backend.py" \
    --source "$MUMU_ROOT/upstream" \
    --target "$MUMU_LUNA_UPSTREAM"

python - <<'PY'
import os
import urllib.request

# This is only a local transport check. A successful model request is checked
# separately before the batch is launched, and is not implied by HTTP 200.
base = os.environ['MUMU_LUNA_BRIDGE_URL'].rstrip('/')
health = base.removesuffix('/v1') + '/health'
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
for label, url in [('chat adapter', health), ('CPU embeddings', 'http://127.0.0.1:8001/')]:
    with opener.open(url, timeout=10) as response:
        if response.status != 200:
            raise SystemExit(f'{label} is not healthy: HTTP {response.status}')
print('Local adapter and CPU embedding endpoints respond; this is not an inference validation.')
PY

exec python "$MUMU_ROOT/deployment/run_mumu_luna.py" \
    --upstream "$MUMU_LUNA_UPSTREAM" \
    --output "$MUMU_LUNA_OUTPUT" \
    --workers 2 --samples-per-project 2 --extra-sample apache/druid:2 "$@"
