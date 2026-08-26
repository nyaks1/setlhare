# Setlhare 🌳

*Three shadows: shelter from the blazing sun, medicine in the dark, and the answer you didn't know you needed.*

**Setlhare** is an offline terminal pair programmer. It reads your stack trace, finds the broken code, and asks a local LLM for a diagnosis, a unified Git diff patch, and an explanation. No internet. No API fees. No cloud. Just your machine and the answer.

---

## What it does

```bash
$ setlhare fix "python3 app.py"
[Setlhare] Intercepting execution: python3 app.py
[Setlhare] Failure detected! Analyzing output...
[Setlhare] Exception: NameError in app.py:5

[Setlhare Engine] Generating patch via llama.cpp (4 threads)...
-    return total / len(items)
+    return total / len(numbers)
```

That's it. One command. Stack trace in, fix out.

### Supported languages

- **Python** — tracebacks, NameError, TypeError, IndexError, KeyError, and more
- **Java** — NullPointerException, ArithmeticException, full thread traces
- **JavaScript / Node.js** — TypeError, ReferenceError, module resolution errors

---

## Install

### Docker (recommended)

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
docker build -t setlhare .
docker run --rm -v "$(pwd):/work" -w /work setlhare fix "python3 app.py"
```

### pip

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
pip install .
```

This installs a `setlhare` command globally.

### From source

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
bash download_model.sh        # ~1.1 GB, idempotent
# ensure llama-cli is on PATH: https://github.com/ggml-org/llama.cpp
python cli.py fix "python3 app.py"
```

---

## Usage

```bash
# Fix a Python script
setlhare fix "python3 app.py"

# Fix with pytest
setlhare fix "pytest tests/"

# Fix a Java application
setlhare fix "java -jar app.jar"

# Fix a Node.js script
setlhare fix "node server.js"

# Use more threads for faster inference
setlhare --threads 8 fix "python3 app.py"

# Use a larger model for better quality
setlhare --model model/qwen2.5-coder-3b-instruct-q4_k_m.gguf fix "python3 app.py"
```

---

## Shell hook (automatic fixes)

Setlhare can sit in your terminal and jump in when any command crashes — no wrapping needed:

```bash
# One-time setup — add to your shell config
eval "$(setlhare hook)"        # bash/zsh
setlhare hook --fish | source   # fish
setlhare hook --powershell | Invoke-Expression  # powershell
```

Then use your terminal normally. When a command fails with a recognizable stack trace, Setlhare shows a fix and asks to apply it:

```bash
$ python3 app.py
Traceback (most recent call last):
  File "app.py", line 5
    return total / len(items)
               ^^^^^
NameError: name 'items' is not defined

[Setlhare] Detected: NameError in app.py:5
[Setlhare] Generating fix via llama.cpp (4 threads)...
[Setlhare] Fix:
-    return total / len(items)
+    return total / len(numbers)
[Setlhare] Apply patch? [y/N]
```

Detection is based on real stack traces, not exit codes — `grep` returning 1 (no match) doesn't trigger it. See [docs/HOOK.md](docs/HOOK.md) for setup instructions and troubleshooting.

---

## CLI options

| Flag | Default | Description |
|---|---|---|
| `--model` | `qwen2.5-coder-1.5b-instruct-q4_k_m.gguf` | Path to a `.gguf` model file |
| `--threads` | `4` | CPU threads for inference |
| `--ctx-size` | `2048` | Context window size |
| `--n-predict` | `512` | Max tokens to generate |
| `--timeout` | `600` | Seconds before inference times out |

---

## Architecture

```
cli.py                    Entry point: runs your command, orchestrates repair
setlhare/parser.py        Multi-language stack trace parser (Python / Java / JavaScript)
setlhare/indexer.py       Extracts ±15 lines around the failure + enclosing function via AST
setlhare/hook.py          Shell hook engine — auto-detects stack traces and offers fixes
download_model.sh         Idempotent weight download with GGUF validation
```

**Flow:** command fails → stderr parsed into an `ErrorReport` (exception type, message, source frames) → last frame's file/line fed to the indexer → language detected from file extension → structured prompt sent to Qwen2.5-Coder-1.5B via llama.cpp at temperature 0.1 → patch printed.

---

## How it works

1. **Run your command** through Setlhare: `setlhare fix "python3 app.py"`
2. **If it succeeds**, Setlhare exits. Nothing to fix.
3. **If it fails**, Setlhare intercepts the stderr and parses the stack trace.
4. **It extracts context** — ±15 lines around the failing line, plus the enclosing function name via Python AST analysis.
5. **It detects the language** from the file extension (`.py`, `.java`, `.js`, etc.).
6. **It sends a structured prompt** to the local GGUF model through `llama-cli`.
7. **It prints a diagnosis**, a unified Git diff patch, and an explanation.

All inference happens locally via `llama.cpp`. No network calls after the initial weight download.

---

## Requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4+ cores |
| Disk | 2 GB free | 5 GB free |
| OS | Linux, macOS, WSL2 | Ubuntu 22.04+ |
| Python | 3.9+ | 3.12+ |

The default 1.5B model runs on ~1.8 GB RAM. No GPU required.

---

## Further reading

- [Deployment guide](docs/DEPLOY.md) — Docker, pip, aliases, wrapper scripts
- [Maximising use](docs/MAXIMISE.md) — custom models, git pairing, IDE integration, team sharing

---

## Built by

**Nyakallo Masiu** — [nyakallomasiu@gmail.com](mailto:nyakallomasiu@gmail.com) · [github.com/nyaks1](https://github.com/nyaks1)

---

## License

GPL v3 — see [LICENSE](LICENSE).
