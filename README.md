# Fancy QR Code Generator

Fancy QR Code Generator is a dual-component project that produces highly styled QR codes.

1. **FastAPI RESTful Service** — backend QR generator with custom finders, dot rendering, hole/logo features, and stateless JSON API.
2. **Streamlit Web Client** — interactive UI that configures the payload, calls the FastAPI service, and previews the generated QR code.

## Repository Layout

```
fastapi_service/         FastAPI backend
streamlit_web_client/    Streamlit frontend
```

## How It Works

The Streamlit client submits JSON payloads to the FastAPI service `/qr` endpoint. The service returns a base64-encoded PNG that the client displays and offers for download.

## Installation

Install dependencies for each component in a dedicated virtual environment:

```bash
cd fastapi_service
pip install -r requirements.txt

cd ../streamlit_web_client
pip install -r requirements.txt
```

## Manual Operation

### 1. Launch the FastAPI Service

```bash
uvicorn fastapi_service.main:app --host 0.0.0.0 --port 8000 --reload
```

- `--host 0.0.0.0` makes the service reachable from other machines on your network.
- `--reload` hot-reloads on file changes; omit it for a production-like run.
- For multi-worker production runs use:
  ```bash
  uvicorn fastapi_service.main:app --host 0.0.0.0 --port 8000 --workers 4
  ```

Visit the interactive API docs at `http://localhost:8000/docs`.

### 2. Launch the Streamlit Client

```bash
export QR_API_URL="http://localhost:8000"  # optional; defaults to this value
streamlit run streamlit_web_client/client.py
```

- The environment variable `QR_API_URL` tells the UI which FastAPI endpoint to call.
- The UI is exposed on `http://localhost:8501` by default.
- When hosting FastAPI remotely, update `QR_API_URL` to match the deployed URL.

### 3. Verifying Connectivity

Once both processes are running, open the Streamlit UI and click **Generate QR**. The client will POST to `http://localhost:8000/qr` and render the returned PNG inline.

```bash
curl -X POST "http://localhost:8000/qr" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello Fancy QR"}' | jq .
```

### Environment Variables

Configure hostnames or override defaults using environment variables:

- `FASTAPI_HOST_FQDN` — public fully qualified domain name for the FastAPI service (e.g. `api.example.com`).
- `FASTAPI_SCHEME` / `FASTAPI_PORT` — optional scheme and port used when constructing the default API URL (`https` / `443` assumed when omitted).
- `FASTAPI_API_BASE_PATH` — prepend an API base path such as `api/v1`.
- `QR_API_URL` — explicit base or full URL the Streamlit backend should call (takes precedence over the fields above). You can provide either a base like `https://api.example.com/api/v1` or the final endpoint `https://api.example.com/api/v1/qr`.
- `QR_API_ENDPOINT` — override the endpoint suffix appended to the base (default `/qr`). Ignored when `QR_API_URL` already ends with the same suffix.
- `STREAMLIT_HOST_FQDN` — advertise the public hostname serving the Streamlit UI (used for display purposes within the app).

Example (manual run):

```bash
export FASTAPI_HOST_FQDN="api.example.com"
export STREAMLIT_HOST_FQDN="qr.example.com"
export FASTAPI_API_BASE_PATH="api/v1"
export FASTAPI_SCHEME="https"
export QR_API_ENDPOINT="/qr"
# Optional: provide the exact URL instead of composing it from the pieces above
# export QR_API_URL="https://api.example.com/api/v1"
```

## Testing

```bash
pytest fastapi_service/tests
pytest streamlit_web_client/tests
```

## Docker

This repository ships with a multi-stage `Dockerfile` that can produce images for either component.

### Build Images

```bash
# FastAPI service image
docker build --target fastapi -t fancy-qr-api .

# Streamlit client image
docker build --target streamlit -t fancy-qr-client .

# Full stack image (FastAPI + Streamlit behind Nginx)
docker build --target fullstack -t fancy-qr-suite .
```

The `--target` flag selects the stage to build. Omit it to produce the default (final) stage; the provided Dockerfile exposes explicit stages named `fastapi`, `streamlit`, and `fullstack`.

### Run Containers

```bash
# FastAPI image
docker run -p 8000:8000 fancy-qr-api

# Streamlit image
docker run -p 8501:8501 -e QR_API_URL="http://host.docker.internal:8000" fancy-qr-client

# Full stack image with Nginx proxy
docker run -p 8080:80 fancy-qr-suite
```

Notes:
- `host.docker.internal` lets the Streamlit container reach the FastAPI service running on the Docker host (works on Docker Desktop). Replace with the correct host name/IP in other environments.
- When both containers run on the same Docker network, you can set `QR_API_URL` to the FastAPI container’s service name (e.g., `http://fancy-qr-api:8000` after calling `docker network create fancy-qr` and starting both containers with `--network fancy-qr`).
- Use `-e QR_API_URL=http://<fastapi_host>:8000` to point the UI at remote deployments.
- The combined `fancy-qr-suite` image exposes FastAPI at `http://localhost:8080/api/v1/qr` and the Streamlit UI at `http://localhost:8080/client/`, both served through Nginx.
- All container targets honor the environment variables described above, so you can inject FQDNs or custom API URLs at runtime, for example:
  ```bash
  docker run -p 8080:80 \
    -e FASTAPI_HOST_FQDN="api.example.com" \
    -e STREAMLIT_HOST_FQDN="qr.example.com" \
    -e FASTAPI_API_BASE_PATH="api/v1" \
    -e QR_API_URL="https://api.example.com/api/v1" \
    -e QR_API_ENDPOINT="/qr" \
    fancy-qr-suite
  ```

### Single-Container Deployment Walkthrough

1. Build the full stack image if you have not already:
   ```bash
   docker build --target fullstack -t fancy-qr-suite .
   ```
2. Run it and expose port 8080 (or any host port you prefer):
   ```bash
   docker run --rm -p 8080:80 fancy-qr-suite
   ```
3. Consume the services:
   - FastAPI endpoint: `http://localhost:8080/api/v1/qr`
   - Streamlit UI: `http://localhost:8080/client/`
4. Health check endpoint: `http://localhost:8080/health` (proxied to the FastAPI `/health` route).

This one-container option is handy for demos or sharing a single deployment artifact; for production, consider dedicated containers (or orchestration) so each service can scale independently.

## License

MIT License. See `LICENSE` for details and attribution.
