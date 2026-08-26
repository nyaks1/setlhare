# ── Stage 1: Fetch llama.cpp binary + model weights ──────────────────────
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /deps

# llama.cpp pre-built binary (CPU-only, Ubuntu x64)
RUN wget -q --show-progress -O llama.tar.gz \
    "https://github.com/ggml-org/llama.cpp/releases/download/b10636/llama-b10636-bin-ubuntu-x64.tar.gz" \
    && tar -xzf llama.tar.gz \
    && mv llama-b10636-bin-ubuntu-x64/llama-cli /usr/local/bin/llama-cli \
    && chmod +x /usr/local/bin/llama-cli \
    && rm -rf llama.tar.gz llama-b10636-bin-ubuntu-x64

# Qwen2.5-Coder 1.5B Q4_K_M (~1.1 GB)
RUN mkdir -p model \
    && wget -q --show-progress -O model/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf \
       "https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct-GGUF/resolve/main/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"

# ── Stage 2: Slim final image ──────────────────────────────────────────
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# llama-cli binary
COPY --from=builder /usr/local/bin/llama-cli /usr/local/bin/llama-cli

# Model weights
COPY --from=builder /deps/model/ /app/model/

# Application code (no pip install needed — pure stdlib)
COPY setlhare/ /app/setlhare/
COPY cli.py /app/cli.py
COPY download_model.sh /app/download_model.sh

WORKDIR /app
ENTRYPOINT ["python", "cli.py"]
CMD ["--help"]
