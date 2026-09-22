#!/usr/bin/env bash
# one ComfyUI per GPU, all sharing the same model files
cd /workspace/ComfyUI
for p in $(pgrep -f "python3 main.py"); do kill $p; done; sleep 3
for g in 0 1 2 3; do
  CUDA_VISIBLE_DEVICES=$g nohup python3 main.py --listen 0.0.0.0 --port $((8188+g)) > /workspace/comfy_$g.log 2>&1 < /dev/null &
done
for g in 0 1 2 3; do for i in $(seq 1 60); do sleep 2; curl -s -m 2 http://127.0.0.1:$((8188+g))/system_stats >/dev/null && break; done; done
for g in 0 1 2 3; do curl -s http://127.0.0.1:$((8188+g))/system_stats | python3 -c "import json,sys;d=json.load(sys.stdin);print('port',$((8188+g)),d['devices'][0]['name'][:40])"; done
