#!/usr/bin/env bash
# Inspect one rendered Ref2VA segment before it is allowed into the piece.
#   qa_segment.sh s1 "3.9 6.3"     -> the scripted cut times, for comparison
# Prints: where the model actually cut, whether the soundtrack is the reused VO, and writes a
# frame strip (/tmp/qa_<id>.png) sampled just before and after every scripted cut plus the head,
# middle and tail - the frames a viewer would notice.
set -euo pipefail
cd "$(dirname "$0")"
id="$1"; cuts="${2:-}"
src="segments/$id.mp4"
vo="ref/${id}_vo.wav"

echo "== $id: $(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")s"
echo "== detected cuts (scripted: ${cuts:-none}) =="
ffmpeg -v info -i "$src" -vf "select='gt(scene,0.30)',showinfo" -an -f null - 2>&1 \
  | grep -oE "pts_time:[0-9.]+" | sed 's/pts_time://' | awk '{printf "  %.2fs\n",$1}'

echo "== soundtrack vs reused VO =="
ffmpeg -v error -y -i "$src" -ac 1 -ar 16000 /tmp/qa_out.wav
ffmpeg -v error -y -i "$vo"  -ac 1 -ar 16000 /tmp/qa_vo.wav
python3 - <<'EOF'
import wave, numpy as np
def rd(p):
    w = wave.open(p); a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float)
    return a - a.mean()
o, v = rd('/tmp/qa_out.wav'), rd('/tmp/qa_vo.wav'); n = min(len(o), len(v)); o, v = o[:n], v[:n]
best = (-1.0, 0)
for l in range(-4800, 4801, 40):
    a = o[max(0, l):n + min(0, l)]; b = v[max(0, -l):n - max(0, l)]
    c = float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-9))
    if c > best[0]: best = (c, l)
print(f"  waveform NCC best {best[0]:.3f} at lag {best[1] / 16:+.0f} ms   (>0.9 = VO copied 1:1)")
k = 8000  # 0.5 s bins: a dropped line shows as VO energy with no OUT energy
eo = np.array([np.sqrt((o[i:i + k] ** 2).mean()) for i in range(0, n - k, k)])
ev = np.array([np.sqrt((v[i:i + k] ** 2).mean()) for i in range(0, n - k, k)])
print(f"  envelope corr (0.5 s bins): {np.corrcoef(eo, ev)[0, 1]:.3f}")
dropped = [f"{i * 0.5:.1f}s" for i in range(len(ev)) if ev[i] > 800 and eo[i] < 0.25 * ev[i]]
print("  DROPPED narration at: " + (", ".join(dropped) if dropped else "none"))
EOF

echo "== frame strip =="
times="0.4"
for c in $cuts; do times="$times $(python3 -c "print(round($c-0.5,2))") $(python3 -c "print(round($c+0.4,2))")"; done
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$src")
times="$times $(python3 -c "print(round($dur/2,2))") $(python3 -c "print(round($dur-0.3,2))")"
i=0; files=""
for t in $times; do
  ffmpeg -v error -y -ss "$t" -i "$src" -frames:v 1 -vf scale=150:-1 "/tmp/qa_f$i.png"; files="$files /tmp/qa_f$i.png|$t"; i=$((i+1))
done
python3 - "$id" $files <<'EOF'
import sys
from PIL import Image, ImageDraw
sid, items = sys.argv[1], sys.argv[2:]
ims = [(Image.open(p.split('|')[0]), p.split('|')[1]) for p in items]
w = sum(i.width for i, _ in ims); h = ims[0][0].height + 16
c = Image.new('RGB', (w, h), 'white'); d = ImageDraw.Draw(c); x = 0
for im, t in ims:
    c.paste(im, (x, 16)); d.text((x + 3, 2), t + 's', fill='black'); x += im.width
c.save(f'/tmp/qa_{sid}.png'); print(f"  /tmp/qa_{sid}.png  ({len(ims)} frames)")
EOF
