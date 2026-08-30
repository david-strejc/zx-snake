#!/bin/bash
# Qwen3.8-27B-Uncensored on llama.cpp + DFlash2 speculative decoding.
# Restart-on-crash supervisor. Logs: /workspace/server.log
export LD_LIBRARY_PATH=/workspace/llama.cpp/build/bin:/usr/local/cuda-12.9/lib64:${LD_LIBRARY_PATH:-}
M=/workspace/models
while true; do
/workspace/llama.cpp/build/bin/llama-server \
  -m $M/Qwen3.8-27B-Uncensored-Q8_0.gguf \
  -md $M/Qwen3.8-27B-DFlash2-Q8_0.gguf \
  --mmproj $M/mmproj-Qwen3.8-27B-Uncensored-F16.gguf \
  --spec-type draft-dflash --spec-draft-n-max 8 -ngld 99 \
  -ngl 99 -fa on -c 262144 \
  --cache-type-k q8_0 --cache-type-v q8_0 \
  -np 1 -t 32 \
  --jinja --reasoning-effort low \
  --host 0.0.0.0 --port 8080 \
  --api-key "${LLM_API_KEY:?set LLM_API_KEY}" \
  --alias qwen3.8-27b-uncensored --metrics
  echo "[supervisor] llama-server exited $? — restarting in 5s" >&2
  sleep 5
done
