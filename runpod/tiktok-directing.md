# Directing 30s vertical video on local H3 that doesn't read as AI

Working notes for the local MiniMax H3-Base stack (`runpod/comfyui-h3.md`). Everything marked
**measured** was measured on this box or on the pod; everything else carries its source and its
confidence. A fair amount of what circulates on this topic is folklore, and it is marked as such.

## The one number that should reorder your effort

A year of r/RealOrAI guesses (7,945 posts, 10,745 reasoning comments, ~a third video —
arXiv:2605.24287) gives, per cue, the probability that a viewer citing it called the clip AI:

| cue | P(AI \| cue) |
|---|---|
| **audio / AV-sync** | **74.3%** |
| anatomy | 66.3% |
| visual artifacts | 65.9% |
| physics & motion | 62.2% |
| lighting & geometry | 53.4% (coin flip) |
| text & details | 53.1% (coin flip) |
| **grain / noise / wear** | **11.2% — argues the clip is REAL** |

So: **spend on sound and on motion restraint. Do not spend on skin adjectives** — pore-level
casting language sits in the verdict-neutral band. Grain is not a tell; it is an alibi.

## Why AI motion looks wrong, and why it is not fixable by prompting

Few-step distillation trades motion for polish. MoGAN (arXiv:2511.21592) on Wan2.1-1.3B:

| | Motion Smoothness | Dynamics Degree | Image Quality |
|---|---|---|---|
| 50 steps | 98.0 | **0.83** | 0.66 |
| 3-step distilled | 98.8 | **0.73** | **0.69** |

Dynamics collapse while *Image Quality rises* — the polish metrics are blind to the defect. Our
8-step turbo LoRA is exactly this trade. The practical consequence is the **1.25× retime** below:
you cannot prompt the drag away, but you can play it back at the right speed.

H3's released weights are CFG-distilled, and its issue #74 reports that high-dynamic prompts
shatter limbs and clothing — *"50 steps won't save it"*. With anatomy at 66.3% detection weight,
**fewer and smaller motions beat more fidgets.**

## The H3 prompt contract

Local H3-Base is missing the hosted pipeline's upstream rewriter (**H3-Context-IR, not open
sourced**), which MiniMax's own card calls *"critical to the quality of the final output"*. So the
prompt shape has to be supplied by hand:

```
<motion path: first-frame state -> observable intermediate changes -> last-frame state>
The view shakes slightly with small amplitude at slow speed as it follows her.
overall_soundscape: <ambient + action + non-verbal human sound. No dialogue, no music.>
non_diegetic_music: N/A
```

Camera vocabulary is **motion type + amplitude + speed**, written as natural English inside the
shot: `Zoom In/Out`, `Push In/Pull Out`, `Pan`, `Truck`, `Tilt`, `Pedestal`, `Arc Shot`,
`Tracking Shot`, `Static Shot`, `Shake Slightly / Shake Strongly`, `POV`, `Roll`; amplitude
`with small/large amplitude`; speed `at slow/fast speed`.

> **Omitting amplitude and speed silently selects medium/normal — which is the floaty AI look.**
> Always state both.

Bracketed `[Push in]` tokens are **Hailuo Director syntax, not H3**. In H3 the only meaningful
bracket is `[Shot N]`.

**FL2VA anti-pattern, from the official guide:** describing both keyframes statically. Supply the
*path that connects them*. FL2VA favours a single shot.

### Phrases that reliably produce slop
`cinematic` · `beautiful` · `4K` · `Ultra HD` · `masterpiece` · `professional lighting` ·
`golden hour` · adjective piles in place of a capture-situation sentence · `low quality, bad
anatomy, ugly` (SD-1.5-era cargo cult). Do **not** use imagemaker's `enhance_prompt` — its
`photorealistic` style expands to *"85mm portrait lens, golden hour, studio lighting"*, i.e. the
exact gloss. Inline negatives on H3 are **advisory**: issue #68 had every line come out sung and
`"no singing"` changed nothing. Never build a pipeline that depends on a prohibition holding.

## Keyframes

**The landmine (read from the node source):**

```python
if first_frame is not None: img = _resize(first_frame[:1], w, h, "disabled")  # STRETCH
if last_frame  is not None: img = _resize(last_frame[:1],  w, h, "center")    # COVER-CROP
```

The two keyframes are resized by **different rules**. Feed both at exactly **768×1344** or the
ends disagree geometrically and the model interpolates through a distortion — a likely cause of
much reported "morphing". `MAX_PIXELS` is `768*1344` exactly, no headroom.

Frame counts snap up until `n % 17 == 5`; trained band ~124–362. **192 frames = 8.000 s is the
only clean integer second in the band.** Keyframes are re-injected every step and never denoised,
so **start-frame quality dominates the result outright** — which is why the still generator
deserves as much prompt care as the video model.

**Verified here:** a start/end keyframe pair generated from one reference image holds identity and
lands on the end frame exactly, with natural motion between. That makes each shot's composition
deterministic at both ends, so cuts can be planned in advance.

**Do not chain pixels.** Chain *geography* via reference images, and describe each scene completely
as if the model has no memory of the neighbouring shot — that is what keeps characters consistent.
Models also decelerate over the final 10–15% of a clip, so the literal last frame is near-static;
generate long and harvest before the deceleration zone. (One practitioner advises the exact
opposite; recorded, not resolved.)

**Accept rate is the real budget.** Published practitioner rates: ~1%, ~5%, ~8%; vendor claim 25%.
Plan 5–20 generations per *directed* shot. Lock prompts on cheap low-res rolls first.

## Cutting

| parameter | value | provenance |
|---|---|---|
| mean shot in a 30 s ad | **1.67 s** | measured, AdSum204 n=102, TransNetV2 |
| shots per 30 s | **18** (range 8–38) | same |
| unfiltered short-form corpus | 2.59 s | SHOT n=853, 2023 |
| hook | **proposition on screen by 3 s** | TikTok help centre, updated 2025-06 |
| pattern interrupt | ~4 s | OpusClip n=500, 58% vs 41% retention |
| duration sweet spot | 21–34 s | same |

🔴 **The single most useful cutting rule found:** never place a picture cut and an audio cut on the
same frame. *"That's the tell, not the tightness. Hold the picture through the audio cut and you
can stay pretty aggressive without it feeling frantic."* Our `assemble.py` enforces this in code —
narration starts are nudged until they clear every picture boundary by 0.28 s.

**Contrarian evidence, worth respecting:** the only corpus regressing editing variables against
outcomes (n=9,654) finds **editing pace significant but "jump cuts prominent" null**, while audio
source and CTA outrank every editing variable. Pace matters; visible jump-cutting doesn't.

**Debunked, still everywhere:** the "8-second attention span" is fabricated (BBC *More or Less*
traced it to a citation with no underlying research). "TikTok says 1.7 seconds" is **Facebook IQ,
2016**, measuring dwell on any News Feed item, pre-dating TikTok's Western launch. TikTok's current
guidance has **quietly dropped every lift percentage and length recommendation** it used to
publish — that silent retraction is itself the signal. Assume ~80% of circulating pacing numbers
predate the current ranking stack.

## Finishing — measured on this box

**24 → 30 fps, three ways** (ffmpeg 6.1.1, 1080×1920, 6 s clip):

| method | wall time | verdict |
|---|---|---|
| `setpts=PTS/1.25,fps=30` | **6.2 s (~1× realtime)** | **use this** — also undoes the distillation drag |
| `minterpolate=mi_mode=mci` | 63 s (10× realtime) | expensive, smears |
| `fps=30` (duplicate) | 1.4 s | visible judder, itself a tell |

**Planning consequence: the retime shortens everything by 20%. A 30 s finished cut needs ~37.5 s
of generated material** before accept rate is even considered.

Phone footage is **digital sensor noise, lifted shadows and hard highlight clipping** — not film
grain. Highlight roll-off is the *cinematic* move; AI already clips hard, which happens to be the
phone cue. `noise` σ calibration (nobody publishes this): `c0s=3`→0.92, `5`→1.55, `10`→3.23,
`20`→6.65; the `u` flag roughly halves it. Well-lit phone sits at σ≈1–3, so **c0s=4–8 daylight**,
chroma at 40–60% of luma. The circulating `noise=alls=18` is σ≈6 on luma *and both chroma planes* —
folklore, and it costs 4.8–11× the bitrate.

⚠️ **Grain does not survive delivery.** Measured SSIM of a re-encode against its own source: clean
0.9985, grained 0.9529 — and that test was run at 8 Mbps, while **TikTok actually delivers 1080p at
0.85–1.7 Mbps HEVC** (29 live clips ffprobe'd). Grain is converted into blocky mosquito noise. Keep
it in low single digits. TikTok publishes **no bitrate spec at all**; every "official 2026 TikTok
bitrate" is SEO folklore. It also does **not** normalise frame rate (23.976 → 60 observed preserved
end to end), so 30 fps is a craft choice, not a platform requirement.

The de-slop chain in `assemble.py` — 5% overscan crop driven by two non-harmonic sine pairs
(~0.8 Hz drift + ~3 Hz tremor, matching a stabiliser library's own drift/tremor split), mild
chromatic shift, light sharpen, lifted-shadow curve, temporal noise, vignette. Handheld amplitude:
a camera-operator preset measures 11.5 px RMS pan at 1080 wide; **phone at arm's length is roughly
half that, ~6–8 px RMS, ~0.3° roll.** Keep a little roll — zero roll reads gimbal — and `allf=t` is
mandatory or the grain freezes into a static screen door.

**Not available in ffmpeg 6.1:** `boxblur` radius and `perspective` coords don't accept per-frame
`n`, so expression-driven whip blur and rolling-shutter skew can't be done that way. Do whips
**in-model** and cut at the blurriest frame.

## Audio — the highest-weight cue, so the one worth the most work

- **Speech-to-speech beats TTS** when you can perform the lines: it transforms a recording
  *"without losing the performance nuances of the original"*. For a 30 s VO that's one take. Cost:
  STS is v2-generation, so no v3 audio tags.
- **v3 pause tags are a known defect** — ElevenLabs support, verbatim: `[pause]` *"currently work
  inconsistently"*, and unexpected stopping is *"a known v3 truncation issue. Keeping each
  generation under 20–30 seconds helps."* v3 does **not** support SSML `<break>`. So: **render one
  generation per line and put the pauses in the timeline**, which is what `vo.py` does.
- **Trim 50–200 ms off every H3 clip head** — issue #51, maintainer-acknowledged: every generation
  opens with a fragment of a never-spoken word.
- **Keep stray non-verbal sounds out of H3 dialogue prompts.** An incidental *"small chuckle"* was
  counted as dialogue and destroyed speaker routing (issue #17 also reports voice bleed between
  same-gender speakers, reproduced on the paid model too — it is model-level).
- Keep the **diegetic bed** under the voice by ducking, not by muting. The room tone is the realism.
- Narration 160–180 wpm ⇒ ~75–95 words per 30 s. ⚠️ **Every source for this traces to the same
  content-farm cluster.** Our measured Czech VO ran 70–152 wpm per line, 61 words in ~31 s.
- **-14 LUFS / -1 dBTP is a judgement, not a finding** — TikTok has never published a LUFS target.
  The rationale is staying in control of your own limiting. Level the dialogue **for phone
  speakers**; music that sits fine on a laptop will bury the voice on a phone.

## Throughput, measured on the RTX PRO 6000 (96 GB)

| job | frames | wall |
|---|---|---|
| 768×1344, 5.2 s | 124 | **101 s** |
| 768×1344, 8.0 s | 192 | **178 s** |
| 768×1344, 15.1 s | 362 | **510 s** (77 GB peak) |

**Two jobs at once on one card is pointless.** Two ComfyUI instances, two simultaneous 124-frame
jobs: both finished at 187 s (93.5 s effective vs 101 s solo — an 8% gain) with VRAM pinned at
96.9 / 97.9 GB, i.e. on the edge of OOM. The weights alone are ~61 GB, so the second instance
cannot get its own copy; they simply time-share. **Real 2× requires a second pod.** At ~178 s per
8 s shot, one card yields ~20 shots/hour, which is already more coverage than a 30 s piece needs.

## Caveats worth keeping

1. **You cannot judge any of this on the master.** Validate on a real re-encode at phone size.
2. **The toolkit has a shelf life.** "Dirty = human" is on the same decay curve the "Gen Z edit"
   already went down: once every brand copies it, it reads as a template. Re-check in six months.
3. **"AI slop" is now thrown at human work too**, and the accused profile is *good audio and
   cinematic lighting*. Polishing toward three-point lighting moves you toward the accused profile.
4. **One visible tell early converts the rest of the clip into a hunt** — awareness flips viewing
   from passive to an active search for anomalies. The hook carries disproportionate weight.
5. ComfyUI's H3 surface changes weekly; pin the version. Known local-only artifact classes: VAE
   tile lattice, latent-cell grid from any denoise mask, and ripples from turbo LoRA +
   BlockSparseAttention.
6. **No A/B test of cut rate against retention exists, by anyone, at any scale.** The fast-cutting
   doctrine is heuristic. Treat the numbers above as a starting cadence, not a law.
