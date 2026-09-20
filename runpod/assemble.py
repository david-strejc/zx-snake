"""Cut the rendered H3 shots to the Czech narration and finish them to look like phone footage.

Three things here are deliberate and each one is a measured anti-"AI slop" move:

* 24 -> 30 fps by *retiming* 1.25x, not by interpolating. H3's few-step distillation drags motion,
  and playing it 1.25x faster puts it back at roughly real speed. It also means 30 s of finished
  video needs ~37.5 s of generated material.
* Every cut is taken from the middle of an 8 s generation. The first frames carry H3's "boundary
  ghost" and the last ~10-15% is where the model decelerates toward a near-static frame.
* Picture cuts and audio cuts never land on the same frame. The diegetic bed crossfades across
  each cut while the picture cuts hard; that offset is what separates a fast edit from a CapCut
  jump-cut signature.

Usage:  python3 assemble.py edl.json out.mp4
"""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CLIPS = ROOT / "clips"
VO = ROOT / "vo_trim"
WORK = ROOT / "build"

RETIME = 1.25          # 24 fps material -> 30 fps delivery at ~1x real speed
AUDIO_FADE = 0.10      # diegetic bed crossfade, so the sound seam misses the picture seam
BED_LEVEL = 0.22       # diegetic bed under the narration
HEAD_GHOST = 0.12      # H3 emits a fragment of a never-spoken word at the head of every clip

# Handheld: two non-harmonic sine pairs, ~0.8 Hz drift plus ~3 Hz tremor, inside a 5% overscan.
# Phone-at-arm's-length is roughly half a camera-operator handheld rig: ~6-8 px RMS at 1080 wide.
DESLOP = (
    "scale=1134:2016,"
    "crop=1080:1920:x='27+7*sin(n/31)+4*sin(n/8.3)':y='48+6*sin(n/23)+3*cos(n/11)',"
    "rgbashift=rh=-1:bh=1,"
    "unsharp=5:5:0.35:5:5:0.0,"
    "curves=r='0/0.02 0.5/0.5 1/0.98':g='0/0.02 0.5/0.5 1/0.98':b='0/0.03 0.5/0.5 1/0.97',"
    "noise=c0s=3:c1s=6:c2s=6:allf=t+u,"
    "vignette=PI/5,"
    "format=yuv420p"
)


if os.environ.get("PLAIN"):  # A/B: retime only, so the finish's own contribution is visible
    DESLOP = "scale=1080:1920,format=yuv420p"


def run(args: list[str]) -> None:
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"ffmpeg failed:\n{' '.join(args[:12])}...\n{done.stderr[-2500:]}")


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def cut(n: int, item: dict) -> tuple[Path, Path]:
    """One cut: retimed and finished picture, plus its own diegetic audio, as separate files."""
    source = CLIPS / f"{item['clip']}.mp4"
    start = max(item["in"], HEAD_GHOST)
    video = WORK / f"v{n:02d}.mp4"
    audio = WORK / f"a{n:02d}.wav"
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(item["len"]), "-i", str(source),
         "-an", "-vf", f"setpts=PTS/{RETIME},fps=30,{DESLOP}",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(video)])
    run(["ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(item["len"]), "-i", str(source),
         "-vn", "-af", f"atempo={RETIME},aresample=44100", "-ac", "2", str(audio)])
    return video, audio


def concat_video(parts: list[Path], target: Path) -> Path:
    listing = WORK / "video.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-c", "copy", str(target)])
    return target


def bed(parts: list[Path], target: Path, length: float) -> Path:
    """Crossfade the per-cut room tone so the audio seams sit off the picture seams."""
    inputs, filters, label = [], [], "[0:a]"
    for n, path in enumerate(parts):
        inputs += ["-i", str(path)]
    for n in range(1, len(parts)):
        nxt = f"[x{n}]"
        filters.append(f"{label}[{n}:a]acrossfade=d={AUDIO_FADE}:c1=tri:c2=tri{nxt}")
        label = nxt
    # Each crossfade eats AUDIO_FADE from the running length, so the bed ends short of the
    # picture; pad it back or the last seconds play with no room tone at all.
    filters.append(f"{label}apad=whole_dur={length}[bed]")
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[bed]", "-ac", "2", str(target)])
    return target


def place(lines: list[dict], boundaries: list[float]) -> list[dict]:
    """Push every line off the picture cuts.

    A line that starts on a cut makes the edit read as machine-made: the viewer gets one combined
    event instead of two. Each start is nudged later until it clears every boundary by CLEARANCE
    and the previous line by BREATH.
    """
    clearance, breath, step = 0.28, 0.15, 0.06
    placed, previous_end = [], 0.0
    for line in lines:
        at = max(line["at"], previous_end + breath)
        while any(abs(at - b) < clearance for b in boundaries):
            at += step
        placed.append({**line, "at": round(at, 2)})
        previous_end = at + seconds(VO / line["file"])
    return placed


def narration(lines: list[dict], length: float, target: Path) -> Path:
    inputs, filters, labels = [], [], []
    for n, line in enumerate(lines):
        inputs += ["-i", str(VO / line["file"])]
        ms = int(line["at"] * 1000)
        filters.append(f"[{n}:a]aresample=44100,adelay={ms}|{ms}[n{n}]")
        labels.append(f"[n{n}]")
    filters.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0,"
                   f"apad=whole_dur={length}[out]")
    run(["ffmpeg", "-y", "-v", "error", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[out]", "-ac", "2", str(target)])
    return target


def main() -> int:
    edl = json.loads(Path(sys.argv[1]).read_text())
    target = Path(sys.argv[2])
    WORK.mkdir(exist_ok=True)

    videos, audios, boundaries, elapsed = [], [], [], 0.0
    for n, item in enumerate(edl["cuts"], start=1):
        video, audio = cut(n, item)
        videos.append(video)
        audios.append(audio)
        elapsed += item["len"] / RETIME
        boundaries.append(round(elapsed, 2))

    picture = concat_video(videos, WORK / "picture.mp4")
    length = seconds(picture)
    room = bed(audios, WORK / "bed.wav", length)
    lines = place(edl["narration"], boundaries)
    moved = sum(1 for a, b in zip(lines, edl["narration"]) if abs(a["at"] - b["at"]) > 0.01)
    print(f"narration: {moved}/{len(lines)} lines nudged clear of a picture cut; "
          f"last line ends {lines[-1]['at'] + seconds(VO / lines[-1]['file']):.2f}s")
    voice = narration(lines, length, WORK / "voice.wav")

    # Duck the room tone under the voice instead of fading it out: the ambience is the realism.
    run(["ffmpeg", "-y", "-v", "error", "-i", str(picture), "-i", str(room), "-i", str(voice),
         "-filter_complex",
         f"[1:a]volume={BED_LEVEL}[b];[b][2:a]sidechaincompress=threshold=0.05:ratio=6:attack=15:"
         f"release=300[duck];[duck][2:a]amix=inputs=2:normalize=0,"
         f"loudnorm=I=-14:TP=-1:LRA=11,atrim=0:{length}[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", str(target)])

    cuts = edl["cuts"]
    print(f"{len(cuts)} cuts, {length:.2f}s at 30 fps, "
          f"mean shot {length / len(cuts):.2f}s -> {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
