FROM streamingtts:v7

WORKDIR /app

ENV PYTORCH_CUDA_ALLOC_CONF="expandable_segments:True"

COPY app /app/app
COPY config /app/config
COPY engines /app/engines
COPY text_normalizer /app/text_normalizer
COPY presets /app/presets
COPY voices /app/voices
COPY requirements.txt /app/requirements.txt

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13128", "--log-level", "info"]
