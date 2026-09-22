#!/usr/bin/env bash
set -e
T0=$(date +%s)
cd /workspace
[ -d ComfyUI ] || git clone -q --depth 1 https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
grep -viE '^torch(vision|audio)?([=<>! ]|$)' requirements.txt > /tmp/req.txt
pip install -q --break-system-packages -r /tmp/req.txt "huggingface_hub[hf_transfer]" 2>&1 | tail -2
# the image's bundled torchaudio is ABI-broken against its torch 2.14+cu130; ComfyUI imports it at start
python3 -c "import torchaudio" 2>/dev/null || pip install -q --break-system-packages --force-reinstall --no-deps --index-url https://download.pytorch.org/whl/cu130 torchaudio 2>&1 | tail -1
echo "SETUP $(( $(date +%s) - T0 ))s"
T1=$(date +%s)
export HF_HUB_ENABLE_HF_TRANSFER=1
hf download Comfy-Org/Qwen-Image-2.1 --local-dir models \
  --include "diffusion_models/qwen_image_2.1_bf16.safetensors" "diffusion_models/qwen_image_2.1_int8_convrot.safetensors" \
            "text_encoders/qwen3vl_8b_bf16.safetensors" "text_encoders/qwen3vl_8b_int8_convrot.safetensors" \
            "vae/qwen_image_2.1_vae_bf16.safetensors" 2>&1 | tail -2
echo "DOWNLOAD $(( $(date +%s) - T1 ))s  $(du -sh models | cut -f1)"
nohup python3 main.py --listen 0.0.0.0 --port 8188 > /workspace/comfy.log 2>&1 < /dev/null &
for i in $(seq 1 60); do sleep 3; curl -s -m 3 http://127.0.0.1:8188/system_stats >/dev/null && { echo "COMFY UP $(( $(date +%s) - T0 ))s total"; break; }; done
python3 -c "import json,urllib.request;d=json.load(urllib.request.urlopen('http://127.0.0.1:8188/system_stats'));print('comfyui',d['system']['comfyui_version'])"
