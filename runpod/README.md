# Qwen3.8-27B-Uncensored on RunPod (RTX PRO 6000 Blackwell)

Verified live 2026-08-30. OpenAI-compatible endpoint, vision + 262K context,
speculative decoding via DFlash2.

## Pod

| | |
|---|---|
| GPU | `NVIDIA RTX PRO 6000 Blackwell Server Edition` — 96 GB, sm_120 |
| Image | `runpod/pytorch:1.1.0-cu1290-torch291-ubuntu2404` (ships CUDA 12.9 toolkit at `/usr/local/cuda-12.9`, no `nvcc` on PATH) |
| Disk | 40 GB container + 100 GB volume at `/workspace` |
| Ports | `8080/http,22/tcp`, `startSsh: true` |

Deploy with the GraphQL `podFindAndDeployOnDemand` mutation; `POST https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY`.
The REST path `/v1/gputypes` does not exist — GraphQL `gpuTypes` is the working query.

## Build (once, into /workspace so it survives pod restart)

The image already has the CUDA toolkit. Two gotchas:

```bash
rm -f /etc/apt/sources.list.d/cuda.list   # duplicate repo, breaks apt-get update with a Signed-By conflict
apt-get update -qq && apt-get install -y ninja-build libcurl4-openssl-dev
export PATH=/usr/local/cuda-12.9/bin:$PATH
cd /workspace && git clone --depth 1 https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -G Ninja -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_CURL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 64 --target llama-server llama-cli llama-bench
```

`pip install` needs `--break-system-packages` (Ubuntu 24.04 PEP 668).

## Weights

```bash
export HF_HUB_ENABLE_HF_TRANSFER=1 HF_HOME=/workspace/hf
hf download JonathanColetti/Qwen3.8-27B-Uncensored-GGUF \
  Qwen3.8-27B-Uncensored-Q8_0.gguf mmproj-Qwen3.8-27B-Uncensored-F16.gguf --local-dir /workspace/models
hf download z-lab/Qwen3.8-27B-DFlash2-GGUF Qwen3.8-27B-DFlash2-Q8_0.gguf --local-dir /workspace/models
```

Q8_0 (29 GB) + mmproj + drafter + 262K q8_0 KV = **42 GB of 96 GB**. Room to spare; no reason
to go below Q8_0 on this card.

## Serve

`serve.sh` — set `LLM_API_KEY` first. The RunPod HTTP proxy is public, so the API key is the
only thing in front of the endpoint.

```bash
setsid nohup bash /workspace/serve.sh </dev/null >/workspace/server.log 2>&1 &
```

## Measured (600-token generation, Q8_0, c=32768)

| spec-decode | gen tok/s | draft accepted |
|---|---|---|
| none | 46.3 | — |
| `draft-mtp` n_max=4 | 90.9 | 390/830 |
| `draft-mtp` n_max=8 | 75.7 | 412/1483 |
| **`draft-dflash` n_max=8** | **96.0** | 405/1343 |
| `draft-simple` (repo's own draft-Q8_0) | segfault | — |

DFlash2 clamps to its trained block size 7, so n_max above 8 changes nothing (12 and 16 measured
identical). MTP gets *worse* past n_max=4. Live at full 262K context: **~99 tok/s**, prompt ~172–272 tok/s.

That is 2.1× over no speculation, matching z-lab's claim.

## llama.cpp flag drift

Recent llama.cpp renamed the speculative flags. `-cd` and `--draft-max` are gone:

| old | new |
|---|---|
| `--draft-max` | `--spec-draft-n-max` |
| `--draft-min` | `--spec-draft-n-min` |
| `-cd` | removed |
| — | `--spec-type none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,draft-dspark,ngram-*` |

`--spec-type draft-mtp` uses the MTP head inside the main GGUF — no second model needed.

## Verified behaviour

- Vision: reads text off a PNG through `image_url` data-URI. ✅
- Refusals: answers prompts base Qwen3.8 declines. ✅
- `--reasoning-effort low` still emits a reasoning trace into `reasoning_content`; budget
  `max_tokens` for it or the visible answer can come back empty on tight caps.

## Stop the pod

```bash
curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"query":"mutation { podStop(input:{podId:\"<POD_ID>\"}) { id desiredStatus } }"}'
```
`podStop` keeps the volume (rebuild survives). `podTerminate` throws it away.
