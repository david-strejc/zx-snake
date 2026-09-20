"""Czech narration for the three selfie-style AutoERP pieces, one voice per character.

First-person testimonial, so each character gets their own ElevenLabs voice rather than the shared
narrator. One generation per line for the same reason as vo.py: v3 truncates long prompts and its
pause tags misfire, so the pauses live in the edit instead.

Usage:  python3 vo_selfie.py            (renders all three into vo_<piece>/)
"""

import os
import subprocess
from pathlib import Path

from elevenlabs.client import ElevenLabs

ROOT = Path(__file__).parent
BRAND_SPOKEN = "Auto-é-er-pé"

PIECES = {
    "tech": {
        "voice": "uYFJyGaibp4N2VwYQshk",  # Adam - conversational
        "lines": [
            "Devět let jsem psal zakázky do sešitu.",
            "Zákazník volal, kde to vázne. A já hledal.",
            "Je ten díl na skladě? Netuším. Jdu se podívat.",
            "Teď mám všechno v tabletu.",
            "Naskenuju, zapíšu, hotovo.",
            "Zakázka je v systému dřív, než dojdu do kanceláře.",
            "AutoERP. Ať to konečně sedí.",
        ],
    },
    "owner": {
        "voice": "U48DQ1c9SVmD2BVCSiHL",  # Zazy - baritone
        "lines": [
            "Tři roky jsem nevěděl, jak na tom firma je.",
            "Čísla přišla až na konci měsíce.",
            "To už se nedalo nic změnit.",
            "Teď to vidím ráno v telefonu.",
            "Zakázky, sklad, tržby. Živě.",
            "Rozhoduju se podle čísel. Ne podle pocitu.",
            "AutoERP. Ať to konečně sedí.",
        ],
    },
    "acc": {
        "voice": "bF7C2fCv7Zf30iT84wZ1",  # Jana - female
        "lines": [
            "Faktury jsem přepisovala ručně.",
            "Ze sešitu do Excelu. Z Excelu do účetnictví.",
            "Třikrát to samé. A stejně tam byla chyba.",
            "Teď se faktura udělá rovnou ze zakázky.",
            "Jeden klik. A sedí to.",
            "Ušetřím den každý měsíc.",
            "AutoERP. Ať to konečně sedí.",
        ],
    },
}


def seconds(path: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                          "-of", "csv=p=0", str(path)], check=True, capture_output=True, text=True)
    return float(out.stdout.strip())


def trim(source: Path, target: Path) -> Path:
    """Strip the leading and trailing silence ElevenLabs pads onto every generation."""
    gate = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse,"
            "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(source), "-af", gate, str(target)],
                   check=True)
    return target


def main() -> int:
    client = ElevenLabs(api_key=os.environ["ELEVENLABS_API_KEY"])
    for name, piece in PIECES.items():
        raw, out = ROOT / f"vo_{name}_raw", ROOT / f"vo_{name}"
        raw.mkdir(exist_ok=True)
        out.mkdir(exist_ok=True)
        total = 0.0
        for n, text in enumerate(piece["lines"], start=1):
            source, target = raw / f"line{n:02d}.mp3", out / f"line{n:02d}.mp3"
            if not source.exists():
                audio = client.text_to_speech.convert(
                    voice_id=piece["voice"], text=text.replace("AutoERP", BRAND_SPOKEN),
                    model_id="eleven_v3", output_format="mp3_44100_192",
                    voice_settings={"stability": 0.4, "similarity_boost": 0.8, "style": 0.5,
                                    "speed": 1.04})
                source.write_bytes(b"".join(audio))
            if not target.exists():
                trim(source, target)
            length = seconds(target)
            total += length
            print(f"{name} line{n:02d}  {length:5.2f}s  {text}")
        print(f"-> {name}: {len(piece['lines'])} lines, {total:.1f}s of speech\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
