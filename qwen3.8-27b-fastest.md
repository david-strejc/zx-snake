# Qwen3.8-27B — fastest local setup (researched 2026-08-21)

Model: Qwen/Qwen3.8-27B (released 2026-08-14, Apache 2.0, 27.78B dense, multimodal, 262K ctx).
One week old; no community finetune beats base yet. Speed wins come from quant + draft model + reasoning config.

## Recipe

1. **Weights: unsloth Dynamic v3.0 GGUF** — claims >10% better accuracy than other quants at same size.
   https://huggingface.co/unsloth/Qwen3.8-27B-GGUF
   (Q4_K_M ≈ 17 GB, runs full 262K context; alternative: lmstudio-community GGUF, mlx-community 4/8-bit on Mac.)

2. **Speculative decoding: DFlash2 draft model** — 2B block-diffusion drafter, ~2× generation speed,
   output quality unchanged (target model verifies every token). Works with SGLang, vLLM, llama.cpp.
   - GPU/native: https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2
   - GGUF (llama.cpp): https://huggingface.co/z-lab/Qwen3.8-27B-DFlash2-GGUF

3. **Set `reasoning_effort` to `low` or off.** Default is `xhigh` = pathological overthinking
   (Willison: 21 min + 22k reasoning tokens for a task that takes 2 min without thinking).
   https://simonwillison.net/2026/Aug/16/qwen-38-27b/

4. Multi-token prediction (MTP) where the engine supports it: +72% throughput in benchmarks.

## Skip

- `redashes/Qwen3.8-27B-BF16-SSMFIX` — "ssm_conv1d structural defect" claim from HF discussion #76
  is disputed as a hoax with fabricated metrics; no Qwen response.
- "Uncensored/ULTIMATE" finetunes (AEON, orcarouter…) — junk tier, with one exception:
  `JonathanColetti/Qwen3.8-27B-Uncensored-GGUF` (Heretic refusal-direction removal, MTP and vision
  retained, benchmarked at −0.5 mean points, refusals 98/100 → 12/100). Deployed and verified —
  see `runpod/README.md`.

## Reference throughput

15–30 tok/s on M5 Max 128GB / DGX Spark at Q4_K_M **without** DFlash2 (Willison). Expect ~2× with drafter.
