"""Build each piece's EDL from its narration, so the picture means what the voice says.

The previous builder solved cut lengths from a cadence curve and placed narration from a fixed
array of start times. The two never referenced each other, so the payoff line landed on the shot
of a man with his head in his hands. This builds the other way round:

    every line owns one or two picture beats, and a line's first beat is named in the script

so the turn lands on the turn. Line start times come from the measured audio, and each picture
change is placed LEAD seconds *before* its line begins - a J-cut, which both keeps picture and
audio cuts off the same frame and makes the image feel like it motivates the sentence.

Usage:  python3 narrative_edl.py
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
RETIME = 1.25
GAP = 1.0        # breath between lines; testimonial, not a music video
LEAD = 0.35      # picture changes this long before its line starts
TAIL = 1.5       # how long the last shot holds after the last word
WINDOWS = (0.20, 2.40, 4.20)   # usable in-points inside an 8 s generation
LIMIT = 6.95     # never read past here: the model decelerates over the last ~10-15%

# line -> the shots that carry it. The first beat of the turn line is the "after" shot on purpose.
PIECES = {
    "tech": [
        ["a1_tech_selfie", "t1_book"],
        ["a1_tech_selfie", "t2_search"],
        ["t2_search"],
        ["a2_tech_after"],
        ["t3_tablet"],
        ["t3_tablet", "a2_tech_after"],
        ["a2_tech_after"],
    ],
    "owner": [
        ["b1_owner_selfie"],
        ["o1_night", "b1_owner_selfie"],
        ["o1_night"],
        ["b2_owner_after"],
        ["o2_dash", "o3_door"],
        ["o3_door", "b2_owner_after"],
        ["b2_owner_after"],
    ],
    "acc": [
        ["c1_acc_selfie"],
        ["k1_retype", "k1_retype"],
        ["k1_retype", "c1_acc_selfie"],
        ["c2_acc_after"],
        ["k2_screen"],
        ["k3_clear"],
        ["c2_acc_after"],
    ],
}


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def window(clip: str, need: float, used: dict) -> float:
    """Pick an in-point that fits `need` source seconds, rotating for variety where it can."""
    fits = [w for w in WINDOWS if w + need <= LIMIT]
    if not fits:
        return WINDOWS[0]
    return fits[used.get(clip, 0) % len(fits)]


def build(name: str, beats: list[list[str]]) -> dict:
    vo = ROOT / f"vo_{name}"
    lengths = [seconds(vo / f"line{n:02d}.mp3") for n in range(1, len(beats) + 1)]

    starts, at = [], LEAD + 0.25       # leave the first shot a moment before the first word
    for length in lengths:
        starts.append(round(at, 2))
        at += length + GAP

    # A line's picture span runs from its own cut point to the next line's cut point.
    edges = [s - LEAD for s in starts] + [starts[-1] + lengths[-1] + TAIL]

    cuts, used = [], {}
    for index, group in enumerate(beats):
        span = edges[index + 1] - edges[index]
        share = span / len(group)
        for clip in group:
            need = round(share * RETIME, 2)
            start = window(clip, need, used)
            used[clip] = used.get(clip, 0) + 1
            cuts.append({"clip": clip, "in": start, "len": min(need, round(LIMIT - start, 2))})

    return {"cuts": cuts,
            "narration": [{"file": f"line{n:02d}.mp3", "at": s}
                          for n, s in enumerate(starts, start=1)]}


def main() -> int:
    for name, beats in PIECES.items():
        edl = build(name, beats)
        (ROOT / f"edl2_{name}.json").write_text(json.dumps(edl, indent=2))
        out = sum(c["len"] for c in edl["cuts"]) / RETIME
        turn = beats[3][0]
        print(f"{name}: {len(edl['cuts'])} cuts, {out:.2f}s, mean {out / len(edl['cuts']):.2f}s, "
              f"turn line lands on {turn}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
