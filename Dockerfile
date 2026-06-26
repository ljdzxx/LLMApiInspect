FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    INSPECT_HOST=0.0.0.0 \
    INSPECT_PORT=8050 \
    INSPECT_DEBUG=0

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app.py page_demo.py README.md ./
COPY inspect_core ./inspect_core

RUN mkdir -p /data

EXPOSE 8050

CMD ["python", "app.py"]
