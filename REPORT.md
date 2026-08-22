# Technical Report — Setlhare: Offline Terminal Pair Programmer

**Team ID:** nyaks1
**Domain:** coding_assistants
**Model:** Setlhare-Qwen2.5-Coder-1.5B-Instruct-Q4_K_M

---

## Problem

African developers — university students in Lagos, self-taught programmers in Arusha, freelancers in Dakar — routinely debug code without reliable internet. Stack Overflow is unreachable, cloud LLM APIs cost money they don't have, and load-shedding makes long cloud sessions fragile. Yet the error itself is local: a stack trace on their own machine.

**Setlhare** (Setswana: "tree", as in solution tree) is an offline terminal pair programmer. Run `python setlhare/cli.py fix <command>` and it:

1. Executes your command and intercepts any stack trace,
2. Parses the exception, file, and failing line number,
3. Extracts ±15 lines of code context plus the enclosing function via Python AST,
4. Sends language + error + code context to a locally-hosted GGUF model through llama.cpp,
5. Returns a diagnosis, a unified Git diff patch, and an explanation of the fix.

Zero network calls after weights are downloaded. It runs on the machines Africans actually own.

---

## Design Decisions

- **Base model:** Qwen2.5-Coder-1.5B-Instruct. We benchmarked three candidates head-to-head on the same error-repair task:
  - Qwen2.5-Coder-3B-Instruct: best output quality, but 2.9 t/s generation, 3.45 GB peak RSS, and 98.9% CPU utilization — too close to thermal/OOM limits for the 8 GB profile.
  - Base Qwen2.5-Coder-1.5B-Instruct: 5.96 t/s, 1.82 GB peak RSS, correct fixes.
  - Setlhare fine-tune (LoRA on the 1.5B): identical speed/memory, better format compliance (diagnosis → diff → explanation), so we ship the fine-tune.
- **Fine-tuning:** LoRA (r=16, all projection modules) via Unsloth on 4,000 commit-fix examples across 9 languages (Python, Java, JS/TS, C#, C++, Rust, Go, Shell) from CommitPackFT, formatted into our diagnosis/patch/explanation template with prompt-loss masking so the model only learns assistant responses.
- **Quantization:** Q4_K_M chosen for the quality/memory balance. Q8_0 doubled memory for marginal gains; lower quants degraded code syntax noticeably.
- **Alternatives considered:** Phi-3 mini (slower tokenization of code), Llama 3.2 1B (weaker at code), StableLM (poor instruction following at low quant).

## Constraints

- Target: ADTC Standard Laptop profile — 8 GB RAM, integrated GPU only, Ubuntu.
- Development happened on an older machine than the reference profile (Intel i5-6200U, 5.8 GB usable RAM, no GPU), which is *harder* than the evaluation target — all numbers below are worst-case.
- Pure CPU inference via llama.cpp; 4 threads to stay within the 4 vCPU budget.
- Full offline operation during inference; the only network touchpoint is `download_model.sh` before evaluation starts.

## Benchmarks

Measured with `adtc-profiler 0.1.0`, participant mode, seed 42:

| Metric | Value |
|---|---|
| Machine | Intel Core i5-6200U @ 2.30GHz, 5.8 GB RAM, no GPU, Ubuntu 24.04 |
| Peak RSS | 1,687 MB (~1.6 GB) |
| Steady-state RSS | 1,605 MB |
| Generation throughput | ~5.96 tokens/s |
| First-token latency | ~31 s (512-token prompt) |
| Prompt processing | ~29 t/s |
| CPU p99 | 87% |
| Thermal throttling | None observed |

Model card: 1.54B parameters (GGUF metadata verified by profiler), 32K native context, Q4_K_M quantization.

### Model selection comparison (same machine, same task)

| Model | t/s | First token | Peak RSS | CPU p99 | Patch correctness |
|---|---|---|---|---|---|
| Qwen2.5-Coder-3B Q4_K_M | 2.92 | 72 s | 3,450 MB | 98.9% | Correct |
| Qwen2.5-Coder-1.5B Q4_K_M (base) | 5.96 | 25 s | 1,820 MB | 81.0% | Correct |
| **Setlhare FT 1.5B Q4_K_M** | 5.96 | 31 s | 1,687 MB | 87.0% | Format-correct |

We selected the fine-tune: equal throughput, lowest memory, and structured output matching our agent contract.

These are self-reported development benchmarks. Official scores are measured by the ADTC profiler on the standard evaluation machine.

---

## Usage

```bash
bash download_model.sh          # fetches GGUF weights (idempotent)
pip install llama-cpp-python    # or install llama.cpp CLI
python cli.py fix "python3 buggy_script.py"
```
