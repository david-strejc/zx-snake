# Qwen-Image-2.1 on RunPod (RTX PRO 6000 Blackwell) via ComfyUI

Deployed and measured 2026-09-22, pod `wik6lfaird6ss3` (RTX PRO 6000 Server, 96 GB, 100 GB volume).
The previous H3 pod could not resume - its host had no free GPU and a pod volume is pinned to its
host - so it was terminated and this one built fresh.

> **Licence: Qwen Research License - non-commercial (research/evaluation) only.** Commercial use
> needs a separate licence from Alibaba. Fine for testing; not for shipping AutoERP/client material.

## Stack
ComfyUI **0.37.0** (native `TextEncodeQwenImage21`; 0.36.0 predates it). `Comfy-Org/Qwen-Image-2.1`:
`qwen_image_2.1_{bf16 14.2 GB, int8_convrot 7.3 GB}` + `qwen3vl_8b_{bf16 17.5, int8 9.4}` +
`qwen_image_2.1_vae_bf16` 0.7. Graph (official template): UNETLoader + CLIPLoader(type `qwen_image`)
+ VAELoader -> TextEncodeQwenImage21 (prompt, negative, up to 16 reference images) -> EmptyLatentImage
-> KSampler 25 steps, **cfg 1.0**, euler/simple -> VAEDecode. Output is RGBA.

`qi_boot.sh`: pod to serving in **5m22s** (setup 63 s, 33 GB download 244 s). Gotcha: a multi-pattern
`hf download --include` silently skipped the bf16 diffusion file; fetch it by exact path.

## Measured (25 steps, `qi_bench.py`)
| run | res | wall |
|---|---|---|
| int8, cold (loads weights) | 1024x1024 | 27.1 s |
| **int8, warm** | 1024x1024 | **3.4 s** |
| bf16, cold (swap from int8) | 1024x1024 | 97.4 s |
| bf16, warm | 1024x1024 | 5.2 s |
| bf16, warm | 2048x2048 | 27.7 s |
| bf16, warm | **1536x2752 (9:16 2K)** | 28.3 s |
| **int8, warm** | **1536x2752 (9:16 2K)** | **21.1 s** |

VRAM with both precisions resident: 43.8 GB. int8 and bf16 are visually near-identical at the same
seed -> **use int8** (25% faster at 2K, half the VRAM). Czech diacritics in signage render correctly.

## Parallel generation: no gain on one card (measured)
| | 1024x1024 | 1536x2752 (9:16 2K) |
|---|---|---|
| single job | 3.62 s/img | 21.4 s/img |
| batch 2 / 4 / 8 (one job) | 3.65 / 3.67 / 3.70 s/img | 21.9 / 21.7 s/img |
| 2 ComfyUI instances, different jobs at once | 3.96 s/img | 22.5 s/img |

One image already saturates the GPU, so batching is exactly linear and concurrent instances are
slightly *slower* (they time-share and pay the switching). Same result as H3. Parallelism scales
with GPUs, not processes: a multi-GPU pod with one ComfyUI per GPU (`CUDA_VISIBLE_DEVICES`) is the
only real N x. One card = ~1,000 images/h at 1K or ~170/h at 9:16 2K (int8, 25 steps).
Trap met: ComfyUI caches identical graph+seed, so a repeated benchmark job returns in 0.3 s - vary
the seed per run or the numbers are fiction (`qi_par.py`).

## GPU comparison and 4-GPU scaling (measured 2026-09-22, int8, 25 steps, warm)
| card | 1024x1024 | 1536x2752 (9:16 2K) |
|---|---|---|
| RTX PRO 6000 Blackwell (96 GB) | 3.62 s | 21.1 s |
| RTX PRO 4500 Blackwell (32 GB) | 8.66 s | 49.9 s |
| RTX 4090 (24 GB) | 12.15 s | 92.6 s |
| **4x RTX PRO 4500, one ComfyUI per GPU** | **2.06 s effective (1,749 img/h)** | **13.0 s effective (277 img/h)** |

- **Multi-GPU scales linearly** (4 cards = 4.2x at 1K, 3.8x at 2K). Multiple instances on ONE card
  do not (see above); one instance per card via `CUDA_VISIBLE_DEVICES` does. `quad_start.sh`.
- **GeForce loses on this model far more than its compute suggests.** The 4090 is 3.4x slower than the
  PRO 6000: GeForce runs FP16-with-FP32-accumulate at half rate, and the `int8_convrot` weights have no
  fast path on Ada (bf16 on the 4090 was slower still, 27 s at 1K). Prefer RTX PRO Blackwell cards.
  `--highvram --disable-dynamic-vram` changed nothing (12.15 s), so it is compute, not weight streaming.
- **Best price/performance measured: RTX PRO 4500 Blackwell**, on both community and secure cloud.
- Traps met: a 30 GB pod volume cannot fetch a 14 GB file (xet reconstructs a full temp copy next to
  it - needs ~2x free); a community 3090 host spent 17+ min in `pip` on a slow network - abandon slow
  hosts early; `pkill -f main.py` inside `ssh '...'` kills the SSH shell itself - run it from a script.
