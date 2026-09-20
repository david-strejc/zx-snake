#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
until [ "$(ls -1 clips/ | wc -l)" -ge 12 ]; do sleep 30; done
echo "== all 12 clips at $(date +%H:%M:%S) =="
python3 assemble.py edl.json autoerp_30s.mp4
PLAIN=1 python3 assemble.py edl.json autoerp_30s_plain.mp4
./style_grid.sh
echo "== assembly done $(date +%H:%M:%S) =="
