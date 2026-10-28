# StreamingTTS — self-contained image (built from scratch, no private base image).
#
# - Library versions are pinned to what ran in production via constraints.txt.
# - Model weights are baked in (models/viettts, engtts, normalizer must exist in
#   the build context), so the image runs anywhere with no volume mounts.
# - No CUDA base image: the torch cu128 wheels ship their own CUDA/cuDNN libs;
#   the NVIDIA Container Toolkit injects the host driver.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True" \
    NVIDIA_VISIBLE_DEVICES=all \
    NVIDIA_DRIVER_CAPABILITIES=compute,utility

# Python 3.10 (Ubuntu 22.04 default, same as production) + audio tools
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip python-is-python3 \
        sox libsox-fmt-mp3 ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dependencies first so code changes don't invalidate this (large) layer
COPY requirements.txt constraints.txt /app/
RUN pip install -c constraints.txt -r requirements.txt \
    && pip install -c constraints.txt --no-deps omnivoice soe-vinorm

# Models: one layer each, placed before the code so code-only changes reuse
# these cached layers (and latest/previous images share them on disk).
COPY models/normalizer /app/models/normalizer
COPY models/engtts /app/models/engtts
COPY models/viettts /app/models/viettts

COPY app /app/app
COPY config /app/config
COPY engines /app/engines
COPY text_normalizer /app/text_normalizer
COPY voices /app/voices

# Build-time smoke test: fail the build (not the first request) if any
# runtime import or model file is missing.
RUN python -c "\
import torch, torchaudio, librosa, pydub, soundfile; \
from omnivoice.models.omnivoice import OmniVoice; \
from transformers.models.higgs_audio_v2_tokenizer.modeling_higgs_audio_v2_tokenizer import HiggsAudioV2TokenizerModel; \
from soe_vinorm import SoeNormalizer; \
import app.main; \
from config.settings import VIETTTS_MODEL_DIR as V, ENGTTS_MODEL_DIR as E, NORMALIZER_MODEL_DIR as N; \
need = [V/'model.safetensors', V/'audio_tokenizer/model.safetensors', E/'model.safetensors', E/'audio_tokenizer/model.safetensors', N/'nsw_detector']; \
missing = [str(p) for p in need if not p.exists()]; \
assert not missing, f'missing model files: {missing}'; \
print('smoke test OK: torch', torch.__version__)" \
    && rm -rf /app/logs

EXPOSE 13128

# Model loading + warmup takes a while; don't report unhealthy during it.
HEALTHCHECK --interval=30s --timeout=10s --start-period=300s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:13128/health', timeout=5)" || exit 1

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13128", "--log-level", "info"]
