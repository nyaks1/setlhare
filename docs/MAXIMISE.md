# Maximising Setlhare

Setlhare works out of the box, but there are ways to make it significantly more useful depending on your workflow and hardware.

---

## 1. Swap models for your hardware

The default 1.5B model is a starting point. You can trade speed for quality (or vice versa) by swapping the GGUF file.

### Larger model (better quality, more RAM)

```bash
# Download Qwen2.5-Coder-3B Q4_K_M (~2 GB, needs ~3.5 GB RAM)
wget -O model/qwen2.5-coder-3b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf"

# Use it
setlhare --model model/qwen2.5-coder-3b-instruct-q4_k_m.gguf fix "python3 app.py"
```

### Smaller model (faster, less RAM)

```bash
# Download Qwen2.5-Coder-0.5B Q4_K_M (~400 MB, needs ~800 MB RAM)
wget -O model/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf \
  "https://huggingface.co/Qwen/Qwen2.5-Coder-0.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf"

setlhare --model model/qwen2.5-coder-0.5b-instruct-q4_k_m.gguf fix "python3 app.py"
```

### Any GGUF model works

Setlhare works with any GGUF model, not just Qwen. Try CodeLlama, DeepSeek Coder, or StarCoder — as long as it's a chat/instruct model. The quality of fixes depends on the model's coding ability.

---

## 2. Pair with git

Setlhare outputs unified diffs. You can apply them directly:

```bash
# Run fix and save the patch
setlhare fix "python3 app.py" > patch.txt

# Apply the patch (if the diff is clean)
git apply patch.txt

# Or commit the fix
git add -A && git commit -m "fix: $(head -1 patch.txt)"
```

### Auto-commit workflow

```bash
#!/usr/bin/env bash
# save as /usr/local/bin/setlhare-commit
setlhare fix "$@" | tee /tmp/setlhare-patch.txt
if git apply --check /tmp/setlhare-patch.txt 2>/dev/null; then
    git apply /tmp/setlhare-patch.txt
    git add -A
    git commit -m "fix: auto-repaired by Setlhare"
    echo "Committed."
else
    echo "Patch didn't apply cleanly. Review manually."
fi
```

---

## 3. RAG over local documentation

For cross-module bugs where the failing code calls into another file, Setlhare only sees ±15 lines around the error. To give it more context:

### Manual context injection

```bash
# If you know the bug involves a specific file, include it manually
cat src/utils/helpers.py | setlhare fix "python3 src/main.py"
```

### Future: built-in RAG

The architecture supports adding a retrieval step — index your codebase, retrieve relevant files, inject them into the prompt. This is on the roadmap.

---

## 4. IDE integration

### VS Code task

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Setlhare Fix",
      "type": "shell",
      "command": "setlhare fix \"python3 ${file}\"",
      "group": "test",
      "presentation": { "reveal": "always", "panel": "new" }
    }
  ]
}
```

Then run it with `Ctrl+Shift+P` → "Tasks: Run Task" → "Setlhare Fix".

### Vim autocmd

```vim
autocmd QuickFixCmdPost *grep* copen
nnoremap <leader>sf :!setlhare fix "python3 %"<CR>
```

### JetBrains / IntelliJ

Create an External Tool:
- Program: `setlhare`
- Arguments: `fix "python3 $FilePath$"`
- Working directory: `$ProjectFileDir$`

---

## 5. Team sharing

### Docker registry

Build and push to a private registry:

```bash
docker build -t registry.internal/setlhare:latest .
docker push registry.internal/setlhare:latest
```

Team members pull and run:

```bash
docker pull registry.internal/setlhare:latest
docker run --rm -v "$(pwd):/work" -w /work setlhare fix "python3 app.py"
```

### Internal pip package

Build a wheel and host it on a private PyPI:

```bash
pip install build
python -m build
twine upload --repository-url https://pypi.internal dist/*
```

Team members install with:

```bash
pip install --index-url https://p.internal setlhare
```

---

## 6. Custom system prompt

If you want Setlhare to explain errors differently (e.g., for teaching), edit the `SYSTEM_PROMPT` in `cli.py`:

```python
SYSTEM_PROMPT = (
    "You are a patient coding tutor. Given a stack trace and code context, "
    "explain what went wrong in simple terms, then show the fix with a diff."
)
```

Or pass it via a wrapper script that builds a custom prompt.

---

## 7. Improvements roadmap

These are features that would make Setlhare significantly more useful:

| Feature | Impact | Difficulty |
|---|---|---|
| **Streaming output** — tokens appear as they generate | High (perceived speed) | Medium |
| **`setlhare explain`** — tutoring mode, no patch | High (education) | Low |
| **Multi-file context** — retrieve related files | High (cross-module bugs) | High |
| **Plugin system** — custom parsers for other languages | Medium | Medium |
| **`setlhare watch`** — auto-fix on file save | Medium | Low |
| **JSON output mode** — machine-readable results | Medium | Low |
| **GUI wrapper** — Electron/Tauri desktop app | Medium | High |
| **LSP integration** — errors inline in editor | High | Very high |

### Contributing

If you want to work on any of these, the codebase is small (~400 lines of Python) and dependency-free. Start with:

```bash
git clone https://github.com/nyaks1/setlhare.git
cd setlhare
python -m unittest discover -s tests
```

All changes should pass the existing test suite.
