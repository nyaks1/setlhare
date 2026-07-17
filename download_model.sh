#!/bin/bash
mkdir -p model
FILE="model/qwen2.5-coder-3b-instruct-q4_k_m.gguf"
if [ -f "$FILE" ]; then
  echo "Model already exists, skipping download."
  exit 0
fi
wget -O "$FILE" \
  https://huggingface.co/Qwen/Qwen2.5-Coder-3B-Instruct-GGUF/resolve/main/qwen2.5-coder-3b-instruct-q4_k_m.gguf
