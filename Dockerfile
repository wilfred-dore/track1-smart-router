# syntax=docker/dockerfile:1
# Image CPU-only pour l'environnement de grading : 4 Go RAM, 2 vCPU, linux/amd64.
# Les poids GGUF sont téléchargés AU BUILD et bundlés (aucun téléchargement au runtime).

# --- Étape 1 : téléchargement du modèle (layer isolé, bien caché par Docker) ---
FROM python:3.11-slim AS model
ARG GGUF_URL="https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /models && curl -fL --retry 3 -o /models/model.gguf "$GGUF_URL"

# --- Étape 2 : image finale ---
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt requirements-llm.txt ./
# Roues CPU précompilées de llama-cpp-python (évite gcc/cmake et la compilation
# sous QEMU depuis Apple Silicon). Si l'index ne répond plus : installer
# build-essential + cmake et retirer --extra-index-url.
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir -r requirements-llm.txt \
       --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu

COPY --from=model /models /models
COPY config.yaml ./
COPY src ./src

ENV LOCAL_MODEL_PATH=/models/model.gguf \
    PYTHONUNBUFFERED=1

CMD ["python", "-m", "src.main"]
