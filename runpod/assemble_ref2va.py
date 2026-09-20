"""Join Ref2VA segments into the finished piece.

Deliberately much less than assemble.py did, because this mode needs less: the narration is
already inside each segment's soundtrack (reused 1:1 by the model), the cuts are already inside
the picture, and the motion is real-time - so there is NO retime (it would pitch-shift the voice)
and no synthetic handheld on top of the model's own. What remains is the boundary-ghost head trim
the model is known for, a straight concat, loudness, and a light phone-sensor finish.

Usage:  python3 assemble_ref2va.py s1 s2 s3 out.mp4
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SEG = ROOT / "segments"
WORK = ROOT / "build_ref2va"

HEAD_TRIM = 0.12   # H3 emits a fragment of a never-spoken word at the head of every generation
FINISH = ("scale=1080:1920,"
          "curves=r='0/0.02 0.5/0.5 1/0.98':g='0/0.02 0.5/0.5 1/0.98':b='0/0.03 0.5/0.5 1/0.97',"
          "noise=c0s=3:c1s=5:c2s=5:allf=t+u,"
          "format=yuv420p")


def run(args: list[str]) -> None:
    done = subprocess.run(args, capture_output=True, text=True)
    if done.returncode:
        raise SystemExit(f"ffmpeg failed:\n{done.stderr[-2000:]}")


def main() -> int:
    *ids, target = sys.argv[1:]
    WORK.mkdir(exist_ok=True)
    parts = []
    for sid in ids:
        part = WORK / f"{sid}.mp4"
        run(["ffmpeg", "-y", "-v", "error", "-ss", str(HEAD_TRIM), "-i", str(SEG / f"{sid}.mp4"),
             "-vf", FINISH, "-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2", str(part)])
        parts.append(part)
    listing = WORK / "concat.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
         "-af", "loudnorm=I=-14:TP=-1:LRA=11", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
         "-movflags", "+faststart", target])
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", target], capture_output=True, text=True).stdout.strip()
    print(f"{len(ids)} segments -> {target} ({float(out):.2f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
