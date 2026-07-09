# syntax=docker/dockerfile:1
# CPU-only image for the grading environment: 4 GB RAM, 2 vCPU, linux/amd64.
# GGUF weights are downloaded AT BUILD time and bundled (no runtime download).

# --- Stage 1: model download (isolated layer, cached well by Docker) ---
FROM python:3.11-slim AS model
ARG GGUF_URL="https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /models && curl -fL --retry 3 -o /models/model.gguf "$GGUF_URL"

# --- Stage 2: final image ---
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt requirements-llm.txt ./
# Precompiled CPU wheels for llama-cpp-python (avoids gcc/cmake and QEMU
# compilation when building from Apple Silicon). If the index goes down:
# install build-essential + cmake and drop --extra-index-url.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-llm.txt \
       --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY --from=model /models /models
COPY config.yaml ./
COPY src ./src

ENV LOCAL_MODEL_PATH=/models/model.gguf \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
