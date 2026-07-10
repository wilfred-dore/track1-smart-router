# syntax=docker/dockerfile:1
# CPU-only image for the grading environment: 4 GB RAM, 2 vCPU, linux/amd64.
# GGUF weights are downloaded AT BUILD time and bundled (no runtime download).

# --- Stage 1: build the llama-cpp-python wheel (glibc, portable CPU flags) ---
# The prebuilt CPU wheels from the abetlen index are musl-linked and fail to
# load on Debian (libc.musl-x86_64.so.1 missing) — build from source instead.
FROM python:3.11-slim AS wheels
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential cmake ninja-build \
    && rm -rf /var/lib/apt/lists/*
COPY requirements-llm.txt .
# GGML_NATIVE=OFF: do not specialize for the build machine's CPU (the grading VM
# may not support the same instruction set; AVX2 baseline remains enabled).
# GGML_OPENMP=OFF: avoid a runtime dependency on libgomp1 (absent from slim).
ENV CMAKE_ARGS="-DGGML_NATIVE=OFF -DLLAMA_NATIVE=OFF -DGGML_OPENMP=OFF"
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements-llm.txt

# --- Stage 2: model download (isolated layer, cached well by Docker) ---
FROM python:3.11-slim AS model
ARG GGUF_URL="https://huggingface.co/bartowski/Qwen2.5-3B-Instruct-GGUF/resolve/main/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /models && curl -fL --retry 3 -o /models/model.gguf "$GGUF_URL"

# --- Stage 3: final image ---
FROM python:3.11-slim
WORKDIR /app

COPY requirements.txt requirements-llm.txt ./
RUN --mount=type=bind,from=wheels,source=/wheels,target=/wheels \
    pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir --no-index --find-links=/wheels -r requirements-llm.txt

COPY --from=model /models /models
COPY config.yaml ./
COPY src ./src

ENV LOCAL_MODEL_PATH=/models/model.gguf \
    PYTHONUNBUFFERED=1

LABEL org.opencontainers.image.source="https://github.com/wilfred-dore/track1-smart-router" \
      org.opencontainers.image.description="Smart Router — AMD Developer Hackathon ACT II, Track 1"

CMD ["python", "-m", "src.main"]
