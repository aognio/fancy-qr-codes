# FastAPI QR Service

This FastAPI application generates highly customizable QR codes. It supports rounded finder patterns, dot-style modules, optional center holes, and optional logo overlays without persisting any state.

## Setup

```bash
pip install -r requirements.txt
```

## Run

### Development server

```bash
uvicorn fastapi_service.main:app --host 0.0.0.0 --port 8000 --reload
```

The `--reload` flag hot-reloads on file changes and binds to all interfaces for easier local testing.

### Production-style server

```bash
uvicorn fastapi_service.main:app --host 0.0.0.0 --port 8000 --workers 4
```

Increase `--workers` to leverage additional CPU cores. Pair with a process manager (systemd, supervisord, or gunicorn) for hardened deployments.

The OpenAPI docs are available at `http://127.0.0.1:8000/docs`.

## Example Request

```bash
curl -X POST "http://127.0.0.1:8000/qr" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello from Fancy QR"}'
```

### Request Schema (excerpt)

```json
{
  "text": "Optional text payload",
  "rounded_finders": true,
  "dot_style": true,
  "foreground": "#000000",
  "background": "#ffffff",
  "hole": false,
  "hole_shape": "circle",
  "hole_percentage": 0.10,
  "use_logo": false,
  "logo_base64": null,
  "rounded_canvas": true,
  "finder_round_ratio": 0.45,
  "dot_margin": 0.18,
  "quiet_zone_modules": 4,
  "error_correction": "H",
  "pixel_size": 1080
}
```

### Response Schema (excerpt)

```json
{
  "width": 1080,
  "height": 1080,
  "content_type": "image/png",
  "png_base64": "iVBORw0KGgoAAAANSUhEUg..."
}
```

The API is stateless: every request produces a fresh image solely from the JSON payload, making horizontal scaling straightforward. Responses are PNGs encoded as base64 strings; clients should decode and persist or display them as needed.
