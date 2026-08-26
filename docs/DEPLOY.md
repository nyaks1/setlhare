# Deploying Setlhare

Setlhare is a standalone CLI tool. No cloud, no API keys, no account. Here's how to get it running on any machine.

---

## Option 1: Docker (recommended)

The Docker image bundles everything — model weights, llama.cpp, and the Python CLI — into a single offline container.

### Build the image

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
docker build -t setlhare .
```

First build takes 10–15 minutes (downloading ~1.1 GB of model weights). Subsequent builds use cache.

### Run it

```bash
# Fix a script in the current directory
docker run --rm -v "$(pwd):/work" -w /work setlhare fix "python3 buggy.py"

# Fix with more threads (match your CPU core count)
docker run --rm -v "$(pwd):/work" -w /work setlhare --threads 8 fix "pytest tests/"

# Use a custom model
docker run --rm -v "$(pwd):/work" -w /work \
  -v /path/to/other.gguf:/app/model/custom.gguf \
  setlhare --model /app/model/custom.gguf fix "node server.js"
```

### Why Docker works well here

- **Zero installation** beyond Docker itself
- **Offline once built** — no network calls during inference
- **Portable** — identical behaviour on Linux, macOS, Windows (Docker Desktop)
- **Reproducible** — same model, same quantization, same result

---

## Option 2: pip install (global command)

Install Setlhare as a system-wide `setlhare` command:

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
pip install .
```

This installs a `setlhare` binary into your PATH. Usage becomes:

```bash
setlhare fix "python3 app.py"
setlhare --threads 8 fix "pytest tests/"
setlhare --model /path/to/bigger.gguf fix "java -jar app.jar"
```

Requirements:
- Python 3.9+
- `llama-cli` on PATH ([install llama.cpp](https://github.com/ggml-org/llama.cpp))
- Model weights downloaded via `bash download_model.sh`

To uninstall: `pip uninstall setlhare`

---

## Option 3: Shell alias (no install)

If you don't want to install anything, add this to `~/.bashrc` or `~/.zshrc`:

```bash
alias setlhare='python3 /path/to/setlhare/cli.py'
```

Then:

```bash
setlhare fix "python3 buggy.py"
```

---

## Option 4: Wrapper script

Create `/usr/local/bin/setlhare` (needs sudo):

```bash
#!/usr/bin/env bash
exec python3 /path/to/setlhare/cli.py "$@"
```

```bash
sudo chmod +x /usr/local/bin/setlhare
```

---

## System requirements

| Component | Minimum | Recommended |
|---|---|---|
| RAM | 4 GB | 8 GB |
| CPU | 2 cores | 4+ cores |
| Disk | 2 GB free | 5 GB free |
| OS | Linux, macOS, WSL2 | Ubuntu 22.04+ |
| Python | 3.9+ | 3.12+ |
| Network | Only for initial download | Offline after that |

### Model size vs RAM

| Model | Params | RAM needed | Speed (4 cores) |
|---|---|---|---|
| Qwen2.5-Coder-1.5B Q4_K_M (default) | 1.5B | ~1.8 GB | ~6 t/s |
| Qwen2.5-Coder-3B Q4_K_M | 3B | ~3.5 GB | ~3 t/s |
| Any GGUF model | varies | varies | varies |

The default 1.5B model runs comfortably on 4 GB RAM machines. If you have 8 GB+, you can swap in a larger model for better quality — see [MAXIMISE.md](MAXIMISE.md).

---

## Troubleshooting

**"llama-cli not found on PATH"**
Install llama.cpp: https://github.com/ggml-org/llama.cpp

**"Model not found"**
Run `bash download_model.sh` — it downloads the weights and validates the GGUF format.

**Slow first response (~30s)**
First inference loads the model into RAM. Subsequent calls are faster. This is normal for CPU-only inference.

**OOM killed**
Your machine doesn't have enough RAM. Use the default 1.5B model, or close other applications.
