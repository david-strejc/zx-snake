#!/usr/bin/env bash
# Suspend the H3 pod: podStop keeps the 200 GB /workspace volume (ComfyUI + 105 GB of models),
# only the 60 GB container disk resets. podTerminate would destroy the volume - not this script.
set -euo pipefail
cd "$(dirname "$0")/.."; set -a; . ./.env; set +a
curl -s "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" -H 'Content-Type: application/json' \
  -d '{"query":"mutation{ podStop(input:{podId:\"g9erukbixehoip\"}){ id desiredStatus } }"}'
echo
