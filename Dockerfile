# syntax=docker/dockerfile:1

FROM python:3.11-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# -----------------------
# FastAPI service image
# -----------------------
FROM base AS fastapi

COPY fastapi_service/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY fastapi_service /app/fastapi_service

EXPOSE 8000
CMD ["uvicorn", "fastapi_service.main:app", "--host", "0.0.0.0", "--port", "8000"]

# -----------------------
# Streamlit client image
# -----------------------
FROM base AS streamlit

COPY streamlit_web_client/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY streamlit_web_client /app/streamlit_web_client

ENV QR_API_URL=http://localhost:8000

EXPOSE 8501
CMD ["streamlit", "run", "streamlit_web_client/client.py", "--server.headless=true", "--server.address=0.0.0.0", "--server.port=8501"]

# -----------------------
# Full stack (FastAPI + Streamlit behind Nginx)
# -----------------------
FROM base AS fullstack

RUN apt-get update \
    && apt-get install -y --no-install-recommends nginx supervisor \
    && rm -rf /var/lib/apt/lists/*

COPY fastapi_service/requirements.txt /tmp/fastapi-requirements.txt
COPY streamlit_web_client/requirements.txt /tmp/streamlit-requirements.txt
RUN pip install --no-cache-dir -r /tmp/fastapi-requirements.txt \
    && pip install --no-cache-dir -r /tmp/streamlit-requirements.txt

COPY fastapi_service /app/fastapi_service
COPY streamlit_web_client /app/streamlit_web_client

COPY docker/fullstack/nginx.conf /etc/nginx/nginx.conf
COPY docker/fullstack/supervisord.conf /etc/supervisor/conf.d/supervisord.conf

ENV QR_API_URL=http://127.0.0.1:8000 \
    FASTAPI_SCHEME=http \
    FASTAPI_API_BASE_PATH= \
    FASTAPI_HOST_FQDN= \
    STREAMLIT_HOST_FQDN= \
    FASTAPI_PORT=

EXPOSE 80

CMD ["supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
