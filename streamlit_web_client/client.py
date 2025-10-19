import base64
import io
import json
import os
from datetime import datetime

import requests
import streamlit as st
from PIL import Image

# ---------- Environment helpers ----------

FASTAPI_HOST_FQDN = os.getenv("FASTAPI_HOST_FQDN")
FASTAPI_SCHEME = os.getenv("FASTAPI_SCHEME", "https")
FASTAPI_PORT = os.getenv("FASTAPI_PORT")
FASTAPI_API_BASE_PATH = os.getenv("FASTAPI_API_BASE_PATH", "")
STREAMLIT_HOST_FQDN = os.getenv("STREAMLIT_HOST_FQDN")
QR_API_URL_ENV = os.getenv("QR_API_URL")
API_QR_ENDPOINT = os.getenv("QR_API_ENDPOINT", "/qr")


def _compose_api_base() -> str:
    if QR_API_URL_ENV:
        return QR_API_URL_ENV.rstrip("/")

    if FASTAPI_HOST_FQDN:
        host_value = FASTAPI_HOST_FQDN.strip()
        if host_value.startswith(("http://", "https://")):
            base = host_value.rstrip("/")
        else:
            netloc = host_value
            if FASTAPI_PORT and ":" not in host_value:
                netloc = f"{host_value}:{FASTAPI_PORT}"
            base = f"{FASTAPI_SCHEME}://{netloc}".rstrip("/")
        if FASTAPI_API_BASE_PATH:
            base = f"{base}/{FASTAPI_API_BASE_PATH.strip('/')}"
        return base.rstrip("/")

    return "http://localhost:8000"


def _resolve_endpoint(base_url: str, endpoint: str) -> str:
    base = base_url.rstrip("/")
    path = endpoint.strip()
    if not path:
        return base
    if not path.startswith("/"):
        path = "/" + path
    if base.lower().endswith(path.lower()):
        return base
    return base + path


# ---------- Config ----------

API_URL_DEFAULT = _compose_api_base()

st.set_page_config(page_title="Fancy QR Client", page_icon="🔳", layout="centered")

st.title("🔳 Fancy QR – Streamlit Client")
st.caption("Talks to your FastAPI service (POST /qr) and shows the generated 1080×1080 PNG.")

# ---------- Sidebar: API target ----------
with st.sidebar:
    st.header("Server")
    api_url = st.text_input("FastAPI base URL", API_URL_DEFAULT, help="Example: http://localhost:8000")
    endpoint = _resolve_endpoint(api_url, API_QR_ENDPOINT)
    st.write(f"Endpoint: `{endpoint}`")
    if FASTAPI_HOST_FQDN:
        st.caption(f"API FQDN: {FASTAPI_HOST_FQDN}")
    if STREAMLIT_HOST_FQDN:
        st.caption(f"Client FQDN: {STREAMLIT_HOST_FQDN}")

# ---------- Inputs ----------
st.subheader("Content")
text = st.text_input("Text to encode (default: current UTC timestamp on server)", value="", placeholder="https://example.com or any text")

st.subheader("Style")
colA, colB = st.columns(2)
with colA:
    rounded_finders = st.checkbox("Rounded finder corners", value=True)
    dot_style = st.checkbox("Dot style for data modules", value=True)
    rounded_canvas = st.checkbox("Rounded outer canvas corners (white)", value=True)
with colB:
    error_correction = st.selectbox("Error correction", options=["L", "M", "Q", "H"], index=3)
    quiet_zone_modules = st.number_input("Quiet zone (modules)", min_value=1, max_value=8, value=4, step=1)

colC, colD = st.columns(2)
with colC:
    foreground = st.color_picker("Foreground (dark) color", "#000000")
    dot_margin = st.slider("Dot margin (0..0.49)", min_value=0.00, max_value=0.49, value=0.18, step=0.01)
with colD:
    background = st.color_picker("Background (light) color", "#ffffff")
    finder_round_ratio = st.slider("Finder corner rounding (0..0.5)", min_value=0.0, max_value=0.5, value=0.45, step=0.01)

st.subheader("Center Hole & Logo")
hole = st.checkbox("Create hole", value=False)
hole_shape = st.selectbox("Hole shape", options=["circle", "rectangle"], index=0, disabled=not hole)
hole_percentage = st.slider("Hole size (% of QR width)", 0.00, 0.20, 0.10, 0.01, disabled=not hole)

colE, colF = st.columns(2)
with colE:
    use_logo = st.checkbox("Add logo", value=False)
with colF:
    logo_file = st.file_uploader("Transparent PNG logo", type=["png"], disabled=not use_logo)

logo_b64 = None
if use_logo and logo_file is not None:
    # Validate transparence is not strictly required, but recommended
    try:
        im = Image.open(logo_file)
        # Re-save to PNG bytes to ensure canonical base64
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        logo_b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception as e:
        st.warning(f"Logo read error: {e}")
        logo_b64 = None

# Fixed size per your service
pixel_size = 1080

payload = {
    "text": text if text.strip() else None,
    "rounded_finders": rounded_finders,
    "dot_style": dot_style,
    "foreground": foreground,
    "background": background,
    "hole": hole,
    "hole_shape": hole_shape,
    "hole_percentage": hole_percentage,
    "use_logo": use_logo and (logo_b64 is not None),
    "logo_base64": logo_b64,
    "rounded_canvas": rounded_canvas,
    "finder_round_ratio": finder_round_ratio,
    "dot_margin": dot_margin,
    "quiet_zone_modules": int(quiet_zone_modules),
    "error_correction": error_correction,
    "pixel_size": 1080,  # Literal on server, included for clarity
}

st.divider()
left, right = st.columns([1,1])
with left:
    if st.button("Generate QR", use_container_width=True, type="primary"):
        try:
            resp = requests.post(endpoint, json=payload, timeout=30)
            if resp.status_code != 200:
                st.error(f"Server returned {resp.status_code}: {resp.text[:300]}")
            else:
                data = resp.json()
                img_b64 = data.get("png_base64")
                if not img_b64:
                    st.error("No png_base64 in response.")
                else:
                    img_bytes = base64.b64decode(img_b64)
                    st.image(img_bytes, caption=f"Generated {data.get('width')}×{data.get('height')} PNG", use_container_width=True)
                    filename = f"qr_{datetime.utcnow().strftime('%Y%m%dT%H%M%S')}.png"
                    st.download_button("Download PNG", data=img_bytes, file_name=filename, mime="image/png")
        except Exception as e:
            st.exception(e)

with right:
    st.write("**Current Request JSON**")
    st.code(json.dumps({k: v for k, v in payload.items() if v is not None}, indent=2), language="json")

st.info("Tip: set environment variable `QR_API_URL` to point the client at a remote FastAPI instance.")
