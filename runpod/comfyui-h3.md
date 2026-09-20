# MiniMax H3-Base on RunPod (RTX PRO 6000 Blackwell) via ComfyUI

Verified live 2026-09-20: local H3-Base image-to-video (FL2VA), 1344×768, 24fps,
H.264 + AAC stereo, generated end to end on the pod. One 5.2s clip in **97s** (8-step turbo).

> **Licensing:** the MiniMax H3 Community License excludes EU/UK/South Korea/US territory for
> hosting the open weights. This was a capability test on a scratch pod; production use from the
> EU needs MiniMax authorization or the hosted API. Not legal advice — read the model card LICENSE.

> **Local ≠ full pipeline.** Open weights are H3-Base only: 768p FL2VA/Ref2VA. The 2K output,
> Context-IR and Regenerate-2K stages are API-only. Confirmed at the node level — ComfyUI exposes
> `MiniMaxH3ImageToVideo`/`MiniMaxH3ReferenceToVideo` (local) alongside
> `MinimaxHailuo03ContextIRNode`/`RegenerateNode` (cloud/API).

## Pod

| | |
|---|---|
| GPU | `NVIDIA RTX PRO 6000 Blackwell Server Edition` — 96 GB, sm_120 |
| Image | `runpod/pytorch:1.1.0-cu1290-torch291-ubuntu2404` (actually ships torch **2.14.0+cu130**) |
| Disk | 60 GB container + 200 GB volume at `/workspace` |
| Ports | `8188/http` (ComfyUI), `22/tcp`, `startSsh: true` |

Deploy: GraphQL `podFindAndDeployOnDemand`, same as the Qwen recipe (`runpod/README.md`).

## Bootstrap

```bash
# ComfyUI (0.36.0 has native H3; 0.30.0 is the floor)
git clone --depth 1 https://github.com/comfyanonymous/ComfyUI
# install reqs WITHOUT clobbering the image's cu130 torch stack:
grep -viE '^torch(vision|audio)?([=<>! ]|$)' requirements.txt > /tmp/req.txt
pip install --break-system-packages -r /tmp/req.txt "huggingface_hub[hf_transfer]"
```

**torchaudio ABI trap:** the image's bundled torchaudio is built against an older c10 —
`libtorchaudio.so: undefined symbol: _ZN3c104cuda29c10_cuda_check_implementation...`. ComfyUI
imports torchaudio at startup (audio VAE), so it won't boot. Fix:

```bash
pip install --break-system-packages --force-reinstall --no-deps \
  --index-url https://download.pytorch.org/whl/cu130 torchaudio     # -> 2.11.0+cu130, loads clean
```

## Weights — `Comfy-Org/MiniMax-H3` (ComfyUI-repackaged)

The repo tree mirrors `ComfyUI/models/` layout, so `hf download ... --local-dir ComfyUI/models`
places files in the right subfolders. Picked the **unpruned int8_convrot** set (full model, the
precision the official templates are tuned for, faster than fp8) plus extras — ~118 GB:

| folder | file | GB |
|---|---|---|
| `diffusion_models/` | `minimax_h3_fl2va_int8_convrot.safetensors` | 34 |
| `diffusion_models/` | `minimax_h3_ref2va_int8_convrot.safetensors` | 34 |
| `text_encoders/` | `qwen3vl_32b_minimax_h3_int8_convrot.safetensors` | 27 |
| `vae/` | `minimax_h3_video_vae_fp16.safetensors` + `..._int8_convrot` | 8 |
| `vae/` | `minimax_h3_audio_vae_fp32.safetensors` | 0.6 |
| `loras/` | 3× turbo (fl2v 4/8-step, ref2v 4-step) | 6 |
| `embeddings/` | 10× effect embeddings (bullet_time, fire_breath, …) | tiny |
| `model_patches/` | `minimax_h3_fun_controlnet_union_pruned_int8_convrot` | 2.3 |

Precision tiers (whole stack): full BF16 ~66 GB · pruned BF16 ~40 · unpruned INT8 ~34 ·
pruned FP8/INT8 ~21. On 96 GB there is no reason to go below unpruned int8.

## Run (headless, via the /prompt API)

The official template ships as a **subgraph-wrapped UI blueprint** at
`ComfyUI/blueprints/Image to Video (MiniMax H3).json` — not API format. Its defaults point at the
*pruned* diffusion + *nvfp4* encoder. Flatten the subgraph to API format and swap in the unpruned
int8 files (see `scratchpad/h3_gen.py` in-session). The compute chain:

```
UNETLoader ─┬─(turbo)→ LoraLoaderModelOnly(fl2v_turbo_8step) ─┐
            └──────────────────────────────────────── ComfySwitchNode → model
CLIPLoader(type=minimax) ┐
VAELoader(video fp16)    ├→ MiniMaxH3ImageToVideo(first_frame, prompt, 1344×768, length)
LoadImage(start frame) ──┘        → (positive CONDITIONING, AV LATENT)
BasicGuider + KSamplerSelect(res_multistep) + BasicScheduler(simple, 8 steps)
  → SamplerCustomAdvanced → VAEDecode(video) + VAEDecodeAudio(audio)
  → CreateVideo(24fps) → SaveVideo(format=auto)
```

`length` = `max(5, round(dur*24))` padded to the model's 17-frame block. `first_frame`/`last_frame`
are both optional → first-frame-only is a clean FL2VA run.

## Measured

| shot | res | frames | wall | VRAM peak |
|---|---|---|---|---|
| 5.2 s landscape | 1344×768 | 124 | 97 s | 64 GB |
| 6.6 s vertical | 768×1344 | 158 | ~2 min | 64 GB |
| **15.1 s vertical** | 768×1344 | **362** | **8.5 min** | **77 GB** |

Portrait 9:16 needs no retune (both dims /16). 15 s in **one shot** fits 96 GB with headroom —
no clip chaining needed, and identity/lighting hold across the whole take. Multi-beat prompts
land: "lowers hand → lifts cup → sips → tucks hair" played out in order over the 15 s.
- Output: H.264 1344×768, 5.17 s, AAC stereo 32 kHz — audio generated jointly (H3 AV latent).

## Teardown

`podTerminate` (disk too) or `podStop` (keep volume). Same GraphQL as `runpod/README.md`.
