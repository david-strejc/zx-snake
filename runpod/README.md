# Qwen3.8-27B-Uncensored on RunPod (RTX PRO 6000 Blackwell)

> **Torn down 2026-08-31.** Pod `rx4bvwvhuj1huh` destroyed with its disk (`podTerminate`) after
> tests finished — no pod, no volume, endpoint 404s. This recipe was proven twice (deploy
> 2026-08-30, redeploy 2026-08-31, both live in one pass at 95.8 gen tok/s); redeploy reproduces it.

Verified live 2026-08-30, redeployed and re-verified 2026-08-31. OpenAI-compatible endpoint, vision + 262K context,
speculative decoding via DFlash2.

## Pod

| | |
|---|---|
| GPU | `NVIDIA RTX PRO 6000 Blackwell Server Edition` — 96 GB, sm_120 |
| Image | `runpod/pytorch:1.1.0-cu1290-torch291-ubuntu2404` (ships CUDA 12.9 toolkit at `/usr/local/cuda-12.9`, no `nvcc` on PATH) |
| Disk | 40 GB container + 100 GB volume at `/workspace` |
| Ports | `8080/http,22/tcp`, `startSsh: true` |

Deploy with the GraphQL `podFindAndDeployOnDemand` mutation; `POST https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY`.
The REST path `/v1/gputypes` does not exist — GraphQL `gpuTypes` is the working query.

## Build (once, into /workspace so it survives pod restart)

The image already has the CUDA toolkit. Two gotchas:

```bash
rm -f /etc/apt/sources.list.d/cuda.list   # duplicate repo, breaks apt-get update with a Signed-By conflict
apt-get update -qq && apt-get install -y ninja-build libcurl4-openssl-dev
export PATH=/usr/local/cuda-12.9/bin:$PATH
cd /workspace && git clone --depth 1 https://github.com/ggml-org/llama.cpp && cd llama.cpp
cmake -B build -G Ninja -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES=120 -DLLAMA_CURL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build -j 64 --target llama-server llama-cli llama-bench
```

`pip install` needs `--break-system-packages` (Ubuntu 24.04 PEP 668).

## Weights

```bash
export HF_HUB_ENABLE_HF_TRANSFER=1 HF_HOME=/workspace/hf
hf download JonathanColetti/Qwen3.8-27B-Uncensored-GGUF \
  Qwen3.8-27B-Uncensored-Q8_0.gguf mmproj-Qwen3.8-27B-Uncensored-F16.gguf --local-dir /workspace/models
hf download z-lab/Qwen3.8-27B-DFlash2-GGUF Qwen3.8-27B-DFlash2-Q8_0.gguf --local-dir /workspace/models
```

Q8_0 (29 GB) + mmproj + drafter + 262K q8_0 KV = **42 GB of 96 GB**. Room to spare; no reason
to go below Q8_0 on this card.

## Serve

`serve.sh` — set `LLM_API_KEY` first. The RunPod HTTP proxy is public, so the API key is the
only thing in front of the endpoint.

```bash
setsid nohup bash /workspace/serve.sh </dev/null >/workspace/server.log 2>&1 &
```

## Measured (600-token generation, Q8_0, c=32768)

| spec-decode | gen tok/s | draft accepted |
|---|---|---|
| none | 46.3 | — |
| `draft-mtp` n_max=4 | 90.9 | 390/830 |
| `draft-mtp` n_max=8 | 75.7 | 412/1483 |
| **`draft-dflash` n_max=8** | **96.0** | 405/1343 |
| `draft-simple` (repo's own draft-Q8_0) | segfault | — |

DFlash2 clamps to its trained block size 7, so n_max above 8 changes nothing (12 and 16 measured
identical). MTP gets *worse* past n_max=4. Live at full 262K context: **~99 tok/s**, prompt ~172–272 tok/s.

That is 2.1× over no speculation, matching z-lab's claim.

## llama.cpp flag drift

Recent llama.cpp renamed the speculative flags. `-cd` and `--draft-max` are gone:

| old | new |
|---|---|
| `--draft-max` | `--spec-draft-n-max` |
| `--draft-min` | `--spec-draft-n-min` |
| `-cd` | removed |
| — | `--spec-type none,draft-simple,draft-eagle3,draft-mtp,draft-dflash,draft-dspark,ngram-*` |

`--spec-type draft-mtp` uses the MTP head inside the main GGUF — no second model needed.

## Verified behaviour

- Vision: reads text off a PNG through `image_url` data-URI. ✅
- Refusals: answers prompts base Qwen3.8 declines. ✅
- `--reasoning-effort low` still emits a reasoning trace into `reasoning_content`; budget
  `max_tokens` for it or the visible answer can come back empty on tight caps.

## Stop the pod

```bash
curl -s -X POST "https://api.runpod.io/graphql?api_key=$RUNPOD_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"query":"mutation { podStop(input:{podId:\"<POD_ID>\"}) { id desiredStatus } }"}'
```
`podStop` keeps the volume (rebuild survives). `podTerminate` throws it away.

---

## Client: opencode on 23.davidstrejc.cz

Installed and verified 2026-08-30. Debian 13 (trixie), opencode **1.18.25**, standalone binary
(no node/bun needed on the host).

```bash
curl -fsSL https://opencode.ai/install | bash        # -> /root/.opencode/bin/opencode
ln -sf /root/.opencode/bin/opencode /usr/local/bin/opencode
```

The installer only appends to `~/.bashrc`, so `opencode` is missing from login and
non-interactive shells (cron, systemd, `ssh host cmd`). The `/usr/local/bin` symlink is what
makes it resolve everywhere — verified with `env -i /bin/sh -c "which opencode"`.

`/root/.config/opencode/opencode.json` (chmod 600 — it holds the API key):

```json
{
  "$schema": "https://opencode.ai/config.json",
  "provider": {
    "runpod-qwen": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Qwen3.8-27B Uncensored (RunPod RTX PRO 6000)",
      "options": { "baseURL": "https://<POD_ID>-8080.proxy.runpod.net/v1", "apiKey": "<KEY>" },
      "models": {
        "qwen3.8-27b-uncensored": {
          "name": "Qwen3.8-27B-Uncensored Q8_0",
          "tool_call": true, "reasoning": true,
          "limit": { "context": 262144, "output": 32768 }
        }
      }
    }
  },
  "model": "runpod-qwen/qwen3.8-27b-uncensored",
  "autoupdate": false
}
```

### Verified on the host

| test | result |
|---|---|
| `opencode models \| grep runpod` | `runpod-qwen/qwen3.8-27b-uncensored` |
| plain round-trip (`opencode run`) | returns exact requested string |
| **tool calling** — write `fib.py`, then run it via bash tool | wrote the file, ran `python3 -c`, returned `6765` ✅ |
| refusal behaviour through opencode | answers, no disclaimer ✅ |
| `env -i /bin/sh -c "which opencode"` | `/usr/local/bin/opencode` |

Tool calling is the part that usually breaks against a local model; llama.cpp's `--jinja` Qwen3
template handles opencode's schema correctly — write and bash tools both fired in one turn.

### Coupling

The `baseURL` points at the RunPod HTTP proxy. **Stop or terminate the pod and opencode on this
server stops working** — the proxy hostname is derived from the pod id, so a re-created pod needs
`options.baseURL` updated in `opencode.json`. `podStop` + start again keeps the same id and URL.

### Full auto (no permission prompts)

Two ways. Config is the persistent one and applies to the TUI as well:

```json
"permission": "allow"
```

`opencode debug config` resolves that to `{"*": "allow"}` — the wildcard covers every tool,
including ones added by future versions. Verified on 2026-08-30: `opencode run` executed
`date -u > /tmp/fullauto_proof.txt` and read the file back, both outside the project directory,
with no approval step.

Per-invocation instead of permanently, `run` takes a flag:

```bash
opencode run --auto "…"     # auto-approve everything not explicitly denied
```

To keep full auto but fence off the sharp edges, use the object form — anything unlisted still
falls through to the `"*"` default:

```json
"permission": {
  "*": "allow",
  "bash": { "rm *": "ask", "git push *": "ask", "*": "allow" },
  "external_directory": "ask"
}
```

Tool keys the schema knows: `read`, `edit`, `glob`, `grep`, `list`, `bash`, `task`,
`external_directory`, `todowrite`, `question`, `webfetch`, `websearch`, `lsp`, `doom_loop`,
`skill`. Values are `ask` / `allow` / `deny`; `bash`, `edit` and a few others also take a
map of glob pattern to action.

### Browser tools: agent-browser over MCP

Installed on 23.davidstrejc.cz 2026-08-30, exposed to the model as MCP tools.

```bash
curl -fsSL https://deb.nodesource.com/setup_24.x | bash    # Debian 13 ships node 20; agent-browser needs >=24
apt-get install -y nodejs
npm i -g --allow-scripts=agent-browser agent-browser       # npm 11 blocks the postinstall without this
agent-browser install --with-deps                          # Chrome 152 + the GTK/GBM libs a headless box lacks
```

Two install traps, both silent: with node 20 npm only warns `EBADENGINE` and installs anyway, and
npm 11 skips the postinstall that fetches the binary unless `--allow-scripts` is passed. Neither
fails loudly — you get a broken install that looks fine.

Wired into `opencode.json` as a stdio MCP server:

```json
"mcp": {
  "agent-browser": {
    "type": "local",
    "command": ["agent-browser", "mcp"],
    "enabled": true,
    "timeout": 120000,
    "environment": {
      "PATH": "/usr/local/bin:/usr/bin:/bin",
      "AGENT_BROWSER_IDLE_TIMEOUT_MS": "600000"
    }
  }
}
```

The explicit `PATH` matters — opencode spawns the server with a minimal environment, and the
default idle timeout would otherwise hold Chrome for an hour after the last call.

### Verified — Qwen driving the browser itself

Read-only pass, model chose the tools unprompted:

```
⚙ agent-browser_agent_browser_open     {"url":"https://example.com"}
⚙ agent-browser_agent_browser_snapshot {"interactive":false,"includeUrls":true}
→ H1 "Example Domain", link "Learn more" (https://iana.org/domains/example)
```

Full interaction chain, including a click through a redirect:

```
⚙ open → snapshot → click {"selector":"e2"} → get_url → get_title → screenshot
→ URL   https://www.iana.org/help/example-domains
→ Title Example Domains
→ /root/octest/shot.png, 1280x577, 1928 distinct colours
```

The screenshot is a genuine render — IANA logo, web fonts, full layout — on a host with no X
server and `DISPLAY` unset. The model used accessibility-tree refs (`e2`) from the snapshot to
target the link rather than guessing a CSS selector, which is the interaction pattern that
normally fails on smaller local models.

`agent-browser skills get core --full` on the host prints the version-matched usage guide;
specialised skills cover Electron, Slack, exploratory QA, and cloud browser providers.
