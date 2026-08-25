#!/usr/bin/env bash
# Downloads the Setlhare model weights. Idempotent, resumable, no credentials.
set -euo pipefail

FILE="model/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"
URL="https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

is_valid_gguf() {
  [ -f "$1" ] && [ "$(head -c 4 "$1" 2>/dev/null)" = "GGUF" ]
}

mkdir -p model

if is_valid_gguf "$FILE"; then
  echo "Model already exists and is valid, skipping download."
  exit 0
fi

if [ -f "$FILE" ]; then
  echo "Found invalid or partial download, restarting..."
  rm -f "$FILE"
fi

echo "Downloading $URL"
wget -q --show-progress -c --tries=3 --timeout=60 -O "$FILE" "$URL"

if is_valid_gguf "$FILE"; then
  echo "Download complete: $FILE ($(du -h "$FILE" | cut -f1))"
else
  echo "ERROR: downloaded file is not valid GGUF." >&2
  rm -f "$FILE"
  exit 1
fi
