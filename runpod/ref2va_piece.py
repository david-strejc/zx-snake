"""Render one narrated piece as a chain of Ref2VA segments on the pod.

This is the model's intended mode for a narrated spot, mirroring what videomaker does on H3 Max:
each segment is ONE generation that carries the same reference images (<Picture 1..N>: identity,
wardrobe, location, previous tail), the segment's narration as <Audio 1> reused 1:1, and its shot
cuts written inside the prompt at the narration timestamps. Identity and world hold because they
are conditioned every step, not because two clips happened to match.

Segments run in order; segment N+1 can reference segment N's last frame as its final <Picture>.

Usage:  python3 ref2va_piece.py piece.json
piece.json:
  {"steps": 25, "scheduler": "beta", "ref_image_size": "max", "turbo": false,
   "segments": [{"id": "s1", "frames": 243, "vo": "s1_vo.wav",
                 "refs": ["tech_ref.png", "tech_body.png", "workshop_loc.png"],
                 "prev_tail": false, "prompt": "..."}, ...]}
"""

import json
import subprocess
import sys
import time
from pathlib import Path

POD = ["-p", "27819", "root@81.27.69.177"]
PORT = 8188
ROOT = Path(__file__).parent
OUT = ROOT / "segments"
INPUT = "/workspace/ComfyUI/input"

DIFFUSION = "minimax_h3_ref2va_int8_convrot.safetensors"
ENCODER = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
TURBO = "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors"


def sh(args: list[str]) -> str:
    return subprocess.run(args, check=True, capture_output=True, text=True).stdout


def ssh(script: str) -> str:
    return sh(["ssh", *POD, script])


def push(local: Path, remote: str) -> None:
    sh(["scp", "-q", "-P", POD[1], str(local), f"{POD[2]}:{remote}"])


def graph(seg: dict, cfg: dict) -> dict:
    def N(cls, **inputs):
        return {"class_type": cls, "inputs": inputs}

    n = {
        "1": N("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors"),
        "2": N("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors"),
        "3": N("UNETLoader", unet_name=DIFFUSION, weight_dtype="default"),
        "4": N("CLIPLoader", clip_name=ENCODER, type="minimax", device="default"),
        "7": N("LoadAudio", audio=seg["vo"]),
    }
    model = ["3", 0]
    if cfg.get("turbo"):
        n["5"] = N("LoraLoaderModelOnly", model=model, lora_name=TURBO, strength_model=1.0)
        model = ["5", 0]
    n["6"] = N("MiniMaxH3SigmaShift", model=model, shift_video=12.0, shift_audio=3.0)
    model = ["6", 0]

    ref = dict(clip=["4", 0], vae=["1", 0], audio_vae=["2", 0], prompt=seg["prompt"],
               width=768, height=1344, length=seg["frames"],
               ref_image_size=cfg.get("ref_image_size", "max"))
    for i, name in enumerate(seg["refs"], start=1):
        n[f"r{i}"] = N("LoadImage", image=name)
        ref[f"ref_images.ref_image_{i}"] = [f"r{i}", 0]
    ref["ref_audios.ref_audio_1"] = ["7", 0]
    n["8"] = N("MiniMaxH3ReferenceToVideo", **ref)

    n["9"] = N("BasicGuider", model=model, conditioning=["8", 0])
    n["10"] = N("KSamplerSelect", sampler_name="res_multistep")
    n["11"] = N("BasicScheduler", model=model, scheduler=cfg.get("scheduler", "beta"),
                steps=cfg.get("steps", 25), denoise=1.0)
    n["12"] = N("RandomNoise", noise_seed=seg.get("seed", 1))
    n["13"] = N("SamplerCustomAdvanced", noise=["12", 0], guider=["9", 0], sampler=["10", 0],
                sigmas=["11", 0], latent_image=["8", 1])
    n["14"] = N("VAEDecode", samples=["13", 0], vae=["1", 0])
    n["15"] = N("VAEDecodeAudio", samples=["13", 0], vae=["2", 0])
    n["16"] = N("CreateVideo", images=["14", 0], audio=["15", 0], fps=24.0, bit_depth=8,
                color_space="sRGB")
    n["17"] = N("SaveVideo", video=["16", 0], filename_prefix=seg["id"], format="auto")
    return n


def submit(seg: dict, cfg: dict) -> str:
    job = OUT / f".job_{seg['id']}.json"
    job.write_text(json.dumps({"prompt": graph(seg, cfg)}))
    push(job, f"/workspace/job_{seg['id']}.json")
    reply = json.loads(ssh(f"curl -s -X POST -H 'Content-Type: application/json' "
                           f"--data-binary @/workspace/job_{seg['id']}.json http://127.0.0.1:{PORT}/prompt"))
    if "prompt_id" not in reply:
        raise SystemExit(f"{seg['id']} rejected:\n{json.dumps(reply, indent=1)[:1500]}")
    return reply["prompt_id"]


def wait(seg_id: str, prompt_id: str) -> tuple[str, int]:
    """Poll until done; return the rendered filename and the peak VRAM seen (MiB)."""
    peak = 0
    for _ in range(240):
        time.sleep(15)
        raw = ssh(f"nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits; "
                  f"curl -s -m 10 http://127.0.0.1:{PORT}/history/{prompt_id}")
        vram, _, hist = raw.partition("\n")
        peak = max(peak, int(vram.strip() or 0))
        history = json.loads(hist or "{}")
        if not history:
            continue
        entry = next(iter(history.values()))
        status = entry.get("status", {})
        if status.get("status_str") != "success":
            raise SystemExit(f"{seg_id}: {json.dumps(status)[:1500]}")
        return entry["outputs"]["17"]["images"][0]["filename"], peak
    raise SystemExit(f"{seg_id}: timed out")


def last_frame(video: Path, target: Path) -> Path:
    """The segment's final frame, for the next segment's continuity reference."""
    sh(["ffmpeg", "-y", "-v", "error", "-sseof", "-0.05", "-i", str(video), "-frames:v", "1",
        str(target)])
    return target


def main() -> int:
    cfg = json.loads(Path(sys.argv[1]).read_text())
    OUT.mkdir(exist_ok=True)
    for seg in cfg["segments"]:
        target = OUT / f"{seg['id']}.mp4"
        if target.exists():
            print(f"{seg['id']}: cached")
        else:
            if seg.get("prev_tail"):
                seg["refs"] = list(seg["refs"]) + [f"{seg['prev_tail']}_last.png"]
            started = time.time()
            rendered, peak = wait(seg["id"], submit(seg, cfg))
            sh(["scp", "-q", "-P", POD[1], f"{POD[2]}:/workspace/ComfyUI/output/{rendered}",
                str(target)])
            print(f"{seg['id']}: {time.time() - started:.0f}s, peak VRAM {peak} MiB, "
                  f"{len(seg['refs'])} refs -> {target.name}")
        tail = last_frame(target, OUT / f"{seg['id']}_last.png")
        push(tail, f"{INPUT}/{tail.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
