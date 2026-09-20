"""Run a shot list through local MiniMax H3-Base on the RunPod box and pull the clips back.

A shot is a keyframe pair (first, optional last) plus a prompt. Keyframes are made elsewhere
(imagemaker) and live in KEYFRAMES; this only ships them to the pod, queues one H3 job per shot,
waits, and downloads the rendered mp4 into CLIPS.

Everything is cached by shot id: a shot whose clip already exists is skipped, so a rerun only
renders what changed. Usage:  python3 shotfactory.py shots.json
"""

import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

POD = ["-p", "27819", "root@81.27.69.177"]
PORT = 8188
ROOT = Path(__file__).parent
KEYFRAMES = ROOT / "keyframes"
CLIPS = ROOT / "clips"

DIFFUSION = "minimax_h3_fl2va_int8_convrot.safetensors"
ENCODER = "qwen3vl_32b_minimax_h3_int8_convrot.safetensors"
TURBO = "minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"


def sh(args: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True, **kw)


def ssh(script: str) -> str:
    return sh(["ssh", *POD, script]).stdout


def push(local: Path, remote: str) -> None:
    sh(["scp", "-q", "-P", POD[1], str(local), f"{POD[2]}:{remote}"])


def frames(seconds: float) -> int:
    """H3 snaps length to the 17k+5 grid; the trained range is 124-362 frames at 24 fps."""
    n = max(5, round(seconds * 24))
    return n + (5 - (n % 17)) % 17


def graph(shot: dict) -> dict:
    def N(cls, **inputs):
        return {"class_type": cls, "inputs": inputs}

    n = {
        "127": N("VAELoader", vae_name="minimax_h3_video_vae_fp16.safetensors"),
        "128": N("VAELoader", vae_name="minimax_h3_audio_vae_fp32.safetensors"),
        "135": N("UNETLoader", unet_name=DIFFUSION, weight_dtype="default"),
        "136": N("CLIPLoader", clip_name=ENCODER, type="minimax", device="default"),
        "142": N("LoraLoaderModelOnly", model=["135", 0], lora_name=TURBO, strength_model=1.0),
        "200": N("LoadImage", image=shot["first"]),
        "131": N("KSamplerSelect", sampler_name="res_multistep"),
        "132": N("BasicScheduler", model=["142", 0], scheduler="simple",
                 steps=shot.get("steps", 8), denoise=1.0),
        "137": N("RandomNoise", noise_seed=shot.get("seed", 1)),
    }
    video = dict(clip=["136", 0], vae=["127", 0], prompt=shot["prompt"],
                 width=768, height=1344, length=frames(shot.get("seconds", 5.2)),
                 first_frame=["200", 0])
    if shot.get("last"):
        n["202"] = N("LoadImage", image=shot["last"])
        video["last_frame"] = ["202", 0]
    n["139"] = N("MiniMaxH3ImageToVideo", **video)
    n["134"] = N("BasicGuider", model=["142", 0], conditioning=["139", 0])
    n["133"] = N("SamplerCustomAdvanced", noise=["137", 0], guider=["134", 0], sampler=["131", 0],
                 sigmas=["132", 0], latent_image=["139", 1])
    n["130"] = N("VAEDecode", samples=["133", 0], vae=["127", 0])
    n["129"] = N("VAEDecodeAudio", samples=["133", 0], vae=["128", 0])
    n["138"] = N("CreateVideo", images=["130", 0], audio=["129", 0], fps=24.0, bit_depth=8,
                 color_space="sRGB")
    n["201"] = N("SaveVideo", video=["138", 0], filename_prefix=shot["id"], format="auto")
    return n


def submit(shot: dict) -> str:
    body = json.dumps({"prompt": graph(shot)}).encode()
    remote = f"/workspace/job_{shot['id']}.json"
    tmp = CLIPS / f".job_{shot['id']}.json"
    tmp.write_bytes(body)
    push(tmp, remote)
    tmp.unlink()
    out = ssh(f"curl -s -X POST -H 'Content-Type: application/json' "
              f"--data-binary @{remote} http://127.0.0.1:{PORT}/prompt")
    reply = json.loads(out)
    if "prompt_id" not in reply:
        raise SystemExit(f"{shot['id']}: rejected by ComfyUI: {out[:600]}")
    return reply["prompt_id"]


def wait(shot_id: str, prompt_id: str, timeout: int = 1800) -> str:
    """Block until the job leaves the queue, then return the rendered file name."""
    started = time.time()
    while time.time() - started < timeout:
        time.sleep(10)
        raw = ssh(f"curl -s -m 10 http://127.0.0.1:{PORT}/history/{prompt_id}")
        history = json.loads(raw or "{}")
        if not history:
            continue
        entry = next(iter(history.values()))
        status = entry.get("status", {}).get("status_str")
        if status != "success":
            raise SystemExit(f"{shot_id}: {status}\n{json.dumps(entry.get('status'))[:800]}")
        return entry["outputs"]["201"]["images"][0]["filename"]
    raise SystemExit(f"{shot_id}: still running after {timeout}s")


def render(shot: dict) -> Path:
    target = CLIPS / f"{shot['id']}.mp4"
    if target.exists():
        print(f"{shot['id']}: cached")
        return target
    for name in (shot["first"], shot.get("last")):
        if name:
            push(KEYFRAMES / name, f"/workspace/ComfyUI/input/{name}")
    started = time.time()
    rendered = wait(shot["id"], submit(shot))
    sh(["scp", "-q", "-P", POD[1], f"{POD[2]}:/workspace/ComfyUI/output/{rendered}", str(target)])
    print(f"{shot['id']}: {time.time() - started:.0f}s -> {target.name}")
    return target


def main() -> int:
    shots = json.loads(Path(sys.argv[1]).read_text())
    CLIPS.mkdir(exist_ok=True)
    started = time.time()
    for shot in shots:
        render(shot)
    print(f"{len(shots)} shots in {(time.time() - started) / 60:.1f} min")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
