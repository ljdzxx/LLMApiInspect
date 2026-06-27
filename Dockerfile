FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    INSPECT_HOST=0.0.0.0 \
    INSPECT_PORT=8050 \
    INSPECT_LOG_LEVEL=INFO \
    GUNICORN_WORKERS=1 \
    GUNICORN_THREADS=8 \
    GUNICORN_TIMEOUT=120

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt

COPY app.py page_demo.py README.md README_CN.md ./
COPY inspect_core ./inspect_core
COPY assets ./assets
RUN python -c "import pathlib, shutil, plotly; src=pathlib.Path(plotly.__file__).parent/'package_data'/'plotly.min.js'; dst=pathlib.Path('/app/assets/plotly.min.js'); dst.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(src, dst)"

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s' % os.getenv('INSPECT_PORT', '8050'), timeout=3).read()"

CMD ["sh", "-c", "gunicorn --bind ${INSPECT_HOST}:${INSPECT_PORT} --workers ${GUNICORN_WORKERS} --threads ${GUNICORN_THREADS} --timeout ${GUNICORN_TIMEOUT} --access-logfile - --error-logfile - app:server"]
