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
