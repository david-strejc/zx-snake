# One-hour benchmark: local H3-Base as a short-form video engine

Question: can the local MiniMax H3-Base stack on one RTX PRO 6000 direct and deliver a finished
30-second vertical piece with Czech narration in about an hour of generation, and how close does it
get to footage that doesn't read as AI?

Craft findings and their sources live in `tiktok-directing.md`. This file is the measurement.

## Throughput (measured, 768×1344, 8-step turbo)

| job | frames | wall | per second of output |
|---|---|---|---|
| 5.2 s | 124 | 101 s | 19.4 s |
| **8.0 s** | **192** | **178 s** | **22.3 s** |
| 15.1 s | 362 | 510 s | 33.8 s |

Cost per second of finished video rises with clip length — the attention cost is not linear. **8 s
(192 frames) is the sweet spot**: it is the only clean integer second inside the trained 124–362
band, and it yields 2–3 usable cuts per generation.

### Two jobs at once: no
Two ComfyUI instances on the one card, two simultaneous 124-frame jobs:

| | wall | effective per clip |
|---|---|---|
| one job alone | 101 s | 101 s |
| two jobs together | 187 s | **93.5 s** |

An 8% gain, with VRAM pinned at **96.9 / 97.9 GB** — on the edge of OOM. The weights alone are
~61 GB, so a second instance cannot hold its own copy and the two simply time-share the SM.
**Real 2× needs a second pod, not a second process.** One card sustains ~20 shots/hour, which is
already more coverage than a 30 s piece consumes.

## Accept rate (measured, small sample)

Published practitioner rates run 1–8% per *directed* shot. Ours, on a first pass of 11 generations:

| outcome | n |
|---|---|
| usable as directed | 10 |
| rejected | 1 |

The rejection is instructive: `s03_invoices` drifted off its keyframe — it replaced the greasy
desk close-up with a tidy workbench and rendered **readable, misspelled document text
("INVOCE")**, which is a first-order tell. Both failure modes were designed out on the re-roll by
filling the frame with paper so no document is ever whole or in focus, and by anchoring the
framing explicitly in the prompt.

Our rate is far better than the published 1–8%, and the reason is that **every shot is anchored by
a generated keyframe**. Practitioners quoting 1% are mostly working text-to-video, where
composition is also a lottery. Keyframe-first collapses the search space — but it moves the cost
upstream into the still generator, which is cheap and fast by comparison.

## Pipeline

```
imagemaker (Nano Banana Pro, 9:16)        keyframes, identity carried by reference image
        |
shotfactory.py   -> pod: ComfyUI H3-Base  8 s FL2VA generations, native audio
        |
vo.py            -> ElevenLabs eleven_v3  Czech narration, one generation per line
        |
assemble.py      -> ffmpeg                retime 24->30, de-slop finish, cut to VO
```

Three things in `assemble.py` are anti-slop measures rather than taste:

1. **Retime 1.25×, not interpolate.** Few-step distillation drags motion (MoGAN measures a 12%
   Dynamics collapse while Image Quality *rises*); playing back 25% faster restores roughly real
   speed. Consequence: **a 30 s cut needs ~37.5 s of generated material.**
2. **Every cut is taken from the middle of its generation** — the head carries H3's acknowledged
   "boundary ghost" and the last 10–15% is where the model decelerates to a near-static frame.
3. **Picture cuts and audio cuts never coincide.** Narration starts are nudged in code until they
   clear every picture boundary by 0.28 s; the diegetic bed crossfades across cuts while the
   picture cuts hard. Cutting both on the same frame is reported as *the* tell of machine editing —
   "that's the tell, not the tightness".

## The piece

Czech-narrated, AutoERP subject, documentary register, shot with the videomaker character
references so identity holds across setups.

| | |
|---|---|
| cuts | 19 |
| mean shot | 1.73 s (target 1.67 s) |
| duration | ~33 s (band 21–34 s) |
| narration | 9 lines, 61 words, ~31 s of speech |
| material generated | 7 × 8 s = 56 s for a ~33 s cut |

## Style matrix

Four registers, same model, same finish, generated to test which survives as "real":

| register | verdict |
|---|---|
| direct-flash night snapshot | |
| front-facing selfie | |
| locked-off observational | |
| "cinematic golden hour" (control) | |

The control is deliberately prompted with every phrase the research flags as slop-inducing —
`cinematic`, `4K`, `golden hour`, `professional lighting`, `flawless glowing skin`. It already
announced itself at the still stage, before a frame of video existed.
