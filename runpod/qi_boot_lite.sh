#!/usr/bin/env bash
# int8 stack only (17.4 GB) - enough for the throughput benchmark on a 24 GB card
set -e; T0=$(date +%s); cd /workspace
[ -d ComfyUI ] || git clone -q --depth 1 https://github.com/comfyanonymous/ComfyUI
cd ComfyUI
grep -viE '^torch(vision|audio)?([=<>! ]|$)' requirements.txt > /tmp/req.txt
pip install -q --break-system-packages -r /tmp/req.txt huggingface_hub 2>&1 | grep -vE "WARNING|incompatible" | tail -1
python3 -c "import torchaudio" 2>/dev/null || pip install -q --break-system-packages --force-reinstall --no-deps --index-url https://download.pytorch.org/whl/cu130 torchaudio 2>&1 | tail -1
for f in diffusion_models/qwen_image_2.1_int8_convrot.safetensors text_encoders/qwen3vl_8b_int8_convrot.safetensors vae/qwen_image_2.1_vae_bf16.safetensors; do
  hf download Comfy-Org/Qwen-Image-2.1 "$f" --local-dir models >/dev/null 2>&1; done
echo "READY $(( $(date +%s)-T0 ))s $(du -sh models | cut -f1)"
nohup python3 main.py --listen 0.0.0.0 --port 8188 > /workspace/comfy.log 2>&1 < /dev/null &
for i in $(seq 1 60); do sleep 3; curl -s -m 3 http://127.0.0.1:8188/system_stats >/dev/null && break; done
python3 -c "import torch;print('gpu',torch.cuda.get_device_name(0),'torch',torch.__version__)"
