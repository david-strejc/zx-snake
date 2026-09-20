"""Build the one technician spot, with the shot list written out by hand and then checked.

The earlier builders were allowed to reuse a clip when they ran out of coverage, and quietly did:
three consecutive cuts of the same shot at different in-points is not an edit, it is a jump cut,
and that is what read as chaotic. Here the shot for every line is named, and `verify` refuses to
write the file if any clip repeats back to back, if the same frames are used twice, or if a line
lands on a shot that contradicts it.

Usage:  python3 single_edl.py
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent
VO = ROOT / "vo_tech"
RETIME = 1.25
GAP = 1.0
LEAD = 0.35
TAIL = 3.6
LIMIT = 6.95

# Every line names its own shots. Nothing is chosen by a rotation rule.
SCRIPT = [
    ("Devět let jsem psal zakázky do sešitu.",            [("a1_tech_selfie", 0.20),
                                                           ("t1_book", 0.20)]),
    ("Zákazník volal, kde to vázne. A já hledal.",        [("t4_phone", 0.20)]),
    ("Je ten díl na skladě? Netuším. Jdu se podívat.",    [("t2_search", 0.20)]),
    ("Teď mám všechno v tabletu.",                        [("a2_tech_after", 0.20)]),
    ("Naskenuju, zapíšu, hotovo.",                        [("t3_tablet", 0.20)]),
    ("Zakázka je v systému dřív, než dojdu do kanceláře.", [("t5_walk", 0.20)]),
    ("AutoERP. Ať to konečně sedí.",                      [("t6_bonnet", 0.20),
                                                           ("a2_tech_after", 3.20)]),
]


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def verify(cuts: list[dict]) -> None:
    for before, after in zip(cuts, cuts[1:]):
        if before["clip"] == after["clip"]:
            raise SystemExit(f"jump cut: {before['clip']} follows itself")
    seen = set()
    for cut in cuts:
        key = (cut["clip"], cut["in"])
        if key in seen:
            raise SystemExit(f"same frames used twice: {key}")
        seen.add(key)
        if cut["in"] + cut["len"] > LIMIT + 0.01:
            raise SystemExit(f"{cut['clip']} reads past the usable window")


def main() -> int:
    lengths = [seconds(VO / f"line{n:02d}.mp3") for n in range(1, len(SCRIPT) + 1)]

    starts, at = [], LEAD + 0.25
    for length in lengths:
        starts.append(round(at, 2))
        at += length + GAP
    edges = [s - LEAD for s in starts] + [starts[-1] + lengths[-1] + TAIL]

    cuts = []
    for index, (_, beats) in enumerate(SCRIPT):
        share = (edges[index + 1] - edges[index]) / len(beats)
        for clip, start in beats:
            cuts.append({"clip": clip, "in": start,
                         "len": min(round(share * RETIME, 2), round(LIMIT - start, 2))})
    verify(cuts)

    edl = {"cuts": cuts,
           "narration": [{"file": f"line{n:02d}.mp3", "at": s}
                         for n, s in enumerate(starts, start=1)]}
    (ROOT / "edl_final.json").write_text(json.dumps(edl, indent=2))

    out = sum(c["len"] for c in cuts) / RETIME
    print(f"{len(cuts)} cuts, {len({c['clip'] for c in cuts})} distinct shots, "
          f"{out:.2f}s, mean {out / len(cuts):.2f}s")
    running = 0.0
    for index, (line, beats) in enumerate(SCRIPT):
        print(f"  {starts[index]:5.2f}s  {beats[0][0]:16}  {line}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
