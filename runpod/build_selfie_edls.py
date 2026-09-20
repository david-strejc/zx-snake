"""Build the three selfie-piece EDLs.

A piece is an ordered list of (clip, in-point) beats. The lengths are solved rather than typed:
each beat gets a share of the required source time, following a cadence that starts fast and
eases off, and the whole thing is scaled so the finished cut lands on the target runtime.

Source seconds = target runtime * RETIME, because assemble.py plays everything 1.25x faster.
"""

import json
from pathlib import Path

ROOT = Path(__file__).parent
RETIME = 1.25
TARGET = 30.5          # finished runtime per piece, seconds
ZOOM = {"s03b_invoices": (1.28, 0.0)}   # crop past the camera UI baked into that keyframe

# Cadence: relative shot length through the piece. Fast on the hook, longer once it turns.
CADENCE = [0.85, 0.85, 0.9, 0.9, 0.95, 1.0, 1.0, 1.05, 1.05, 1.1, 1.1, 1.15, 1.15, 1.2, 1.25, 1.3]

# In-points stay in {0.20, 2.40, 4.20} so that start + length never crosses the 6.95 s usable
# window of an 8 s generation, which otherwise silently truncates a cut to nothing.
PIECES = {
    "tech": [
        ("a1_tech_selfie", 0.20), ("s01_logbook", 0.20), ("a1_tech_selfie", 2.40),
        ("s03b_invoices", 2.40), ("s02_frustrated", 0.20), ("a1_tech_selfie", 4.20),
        ("s06_warehouse", 0.20), ("s02_frustrated", 2.40), ("a2_tech_after", 0.20),
        ("s05_tablet", 0.20), ("a2_tech_after", 2.40), ("s06_warehouse", 2.40),
        ("s05_tablet", 2.40), ("a2_tech_after", 4.20), ("s07_together", 0.20),
        ("s05_tablet", 4.20),
    ],
    "owner": [
        ("b1_owner_selfie", 0.20), ("s04_owner_sceptic", 0.20), ("b1_owner_selfie", 2.40),
        ("s03b_invoices", 0.20), ("s04_owner_sceptic", 2.40), ("b1_owner_selfie", 4.20),
        ("s03b_invoices", 4.20), ("s01_logbook", 0.20), ("b2_owner_after", 0.20),
        ("s07_together", 0.20), ("b2_owner_after", 2.40), ("s05_tablet", 2.40),
        ("s07_together", 2.40), ("b2_owner_after", 4.20), ("s04_owner_sceptic", 4.20),
        ("s07_together", 4.20),
    ],
    "acc": [
        ("c1_acc_selfie", 0.20), ("c3_acc_desk", 0.20), ("c1_acc_selfie", 2.40),
        ("s03b_invoices", 0.20), ("c3_acc_desk", 2.40), ("c1_acc_selfie", 4.20),
        ("s03b_invoices", 4.20), ("s01_logbook", 0.20), ("c2_acc_after", 0.20),
        ("c3_acc_desk", 4.20), ("c2_acc_after", 2.40), ("s01_logbook", 2.40),
        ("c3_acc_desk", 0.20), ("c2_acc_after", 4.20), ("c1_acc_selfie", 2.40),
        ("c2_acc_after", 2.40),
    ],
}

NARRATION = {name: [f"line{n:02d}.mp3" for n in range(1, 8)] for name in PIECES}
# Rough first placement; assemble.py nudges each line clear of the picture cuts from here.
STARTS = [0.2, 3.6, 7.8, 12.2, 15.0, 18.6, 25.0]


def solve(beats: list[tuple[str, float]]) -> list[dict]:
    """Scale the cadence so the beats sum to the source time the target runtime needs."""
    weights = CADENCE[:len(beats)]
    scale = (TARGET * RETIME) / sum(weights)
    cuts = []
    for (clip, start), weight in zip(beats, weights):
        length = round(weight * scale, 2)
        cut = {"clip": clip, "in": start, "len": length}
        if clip in ZOOM:
            cut["zoom"], cut["x"] = ZOOM[clip]
        # Never run past the usable window: the last ~1s of an 8s generation is deceleration.
        if start + length > 6.95:
            cut["len"] = round(max(1.2, 6.95 - start), 2)
        cuts.append(cut)
    return cuts


def main() -> int:
    for name, beats in PIECES.items():
        cuts = solve(beats)
        edl = {"cuts": cuts,
               "narration": [{"file": f, "at": s} for f, s in zip(NARRATION[name], STARTS)]}
        path = ROOT / f"edl_{name}.json"
        path.write_text(json.dumps(edl, indent=2))
        out = sum(c["len"] for c in cuts) / RETIME
        print(f"{name}: {len(cuts)} cuts, picture {out:.2f}s, mean shot {out / len(cuts):.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
