# Technical Report — Setlhare

**Model:** Qwen2.5-Coder-1.5B-Instruct-Q4_K_M

---

## Problem

Developers routinely debug code without reliable internet. Stack Overflow is unreachable, cloud LLM APIs cost money, and long cloud sessions are fragile under load-shedding. Yet the error itself is local: a stack trace on their own machine.

**Setlhare** is an offline terminal pair programmer. Run `setlhare fix <command>` and it:

1. Executes your command and intercepts any stack trace,
2. Parses the exception, file, and failing line number,
3. Extracts ±15 lines of code context plus the enclosing function via Python AST,
4. Sends language + error + code context to a locally-hosted GGUF model through llama.cpp,
5. Returns a diagnosis, a unified Git diff patch, and an explanation of the fix.

Zero network calls after weights are downloaded.

---

## Design Decisions

- **Base model:** Qwen2.5-Coder-1.5B-Instruct. We benchmarked three candidates head-to-head on an identical error-repair task:
  - Qwen2.5-Coder-3B-Instruct: best raw quality, but 2.9 t/s generation, 3.45 GB peak RSS, and 98.9% CPU utilization — too close to thermal/OOM limits for an 8 GB laptop.
  - Base Qwen2.5-Coder-1.5B-Instruct: 5.96 t/s, 1.82 GB peak RSS, correct fixes with valid diffs.
  - Setlhare LoRA fine-tune of the 1.5B: identical speed/memory, better format compliance, but patch correctness regressed below base on our evaluation set.
  - **Decision:** ship the base model wrapped in Setlhare's structured prompting; keep the fine-tuning pipeline (`scripts/train.py`, `scripts/augment_dataset.py`) in-repo for future work once a larger, cleaner repair corpus is available.
- **Fine-tuning exploration:** LoRA (r=16, all projection modules) via Unsloth on 4,000 commit-fix examples across 9 languages plus 1,500 synthetic error-repair samples with verified working diffs. The experiment taught us that commit-style diffs do not transfer to runtime-error repair without substantially more curated data — documented as a negative result.
- **Quantization:** Q4_K_M chosen for the quality/memory balance. Q8_0 doubled memory for marginal gains; lower quants degraded code syntax noticeably.
- **Alternatives considered:** Phi-3 mini (slower tokenization of code), Llama 3.2 1B (weaker at code), StableLM (poor instruction following at low quant).

## Constraints

- Target: 8 GB RAM laptop, integrated GPU only, Ubuntu.
- Pure CPU inference via llama.cpp; 4 threads to stay within the 4 vCPU budget.
- Full offline operation during inference; the only network touchpoint is `download_model.sh` before first use.

## Benchmarks

Measured on an Intel Core i5-6200U @ 2.30 GHz, 5.8 GB RAM, no GPU, Ubuntu 24.04:

| Metric | Value |
|---|---|
| Peak RSS | 1,820 MB (~1.8 GB) |
| Steady-state RSS | 1,729 MB |
| Generation throughput | ~5.96 tokens/s |
| First-token latency | ~25 s (512-token prompt) |
| Prompt processing | ~28 t/s |
| CPU p99 | 81% |
| Thermal throttling | None observed |

Model card: 1.78B parameters (GGUF metadata), 32K native context, Q4_K_M quantization.

### Model selection comparison (same machine, same task)

| Model | t/s | First token | Peak RSS | CPU p99 | Patch correctness |
|---|---|---|---|---|---|
| Qwen2.5-Coder-3B Q4_K_M | 2.92 | 72 s | 3,450 MB | 98.9% | Correct |
| **Qwen2.5-Coder-1.5B Q4_K_M (shipped)** | 5.96 | 25 s | 1,820 MB | 81.0% | Correct |
| Setlhare FT 1.5B Q4_K_M (evaluated) | 5.96 | 31 s | 1,687 MB | 87.0% | Regressed |

We selected the base model: fastest, correct output on real error-repair tasks, and the largest safety margin against thermal penalties on constrained hardware.

---

## Usage

```bash
bash download_model.sh                        # fetches GGUF weights (idempotent)
setlhare fix "python3 buggy_script.py"        # runs the command and repairs failures
```

Requires `llama-cli` on PATH (https://github.com/ggml-org/llama.cpp). Optional flags: `--model`, `--threads`, `--ctx-size`, `--n-predict`, `--timeout`.

## Testing

```bash
python -m unittest discover -s tests
```
