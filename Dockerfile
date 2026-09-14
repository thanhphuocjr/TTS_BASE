FROM streamingtts:v5

WORKDIR /app

COPY app /app/app
COPY config /app/config
COPY engines /app/engines
COPY text_normalizer /app/text_normalizer
COPY presets /app/presets
COPY voices /app/voices
COPY requirements.txt /app/requirements.txt

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "13125", "--log-level", "info"]
