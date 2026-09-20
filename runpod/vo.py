"""Render the Czech narration line by line with ElevenLabs and report the real durations.

One generation per line, not one per script: v3 truncates long prompts and its [pause] tags fire
inconsistently, so the pauses are timeline gaps here instead. Durations come back measured, which
is what the edit is cut against.
"""

import os
import subprocess
import sys
from pathlib import Path

from elevenlabs.client import ElevenLabs

NARRATOR = "7FpO7yFcBAfqM6vZJCg7"  # Jan - Bright and Gentle
BRAND_SPOKEN = "Auto-é-er-pé"
OUT = Path(__file__).parent / "vo"

LINES = [
    "Papíry. Pořád jenom papíry.",
    "Zakázka v sešitě, faktura v šuplíku, a díl nikdo neví kde.",
    "Večer to přepisuješ do Excelu. Zase.",
    "Přijde reklamace a ty hledáš tři hodiny.",
    "Takhle jede půlka českých firem.",
    "Pak to zapneš. Zakázka, sklad, fakturace na jednom místě.",
    "Technik naskenuje díl přímo v dílně. Majitel to vidí hned.",
    "Žádné přepisování. Žádné hledání.",
    "AutoERP. Ať to konečně sedí.",
]


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def main() -> int:
    OUT.mkdir(exist_ok=True)
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    total = 0.0
    for n, text in enumerate(LINES, start=1):
        path = OUT / f"line{n:02d}.mp3"
        if not path.exists():
            audio = client.text_to_speech.convert(
                voice_id=NARRATOR, text=text.replace("AutoERP", BRAND_SPOKEN),
                model_id="eleven_v3", output_format="mp3_44100_192",
                voice_settings={"stability": 0.4, "similarity_boost": 0.8, "style": 0.5,
                                "speed": 1.06})
            path.write_bytes(b"".join(audio))
        length = seconds(path)
        total += length
        words = len(text.split())
        print(f"line{n:02d}  {length:5.2f}s  {words:2d}w  {words / length * 60:5.0f} wpm  {text}")
    print(f"\n{len(LINES)} lines, {total:.1f}s of speech, "
          f"{sum(len(l.split()) for l in LINES)} words total")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
