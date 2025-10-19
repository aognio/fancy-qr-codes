from fastapi import FastAPI, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, ValidationError, field_validator
from typing import Optional, Literal
import base64, io, re
from PIL import Image, ImageDraw
import qrcode

app = FastAPI(title="Fancy QR API", version="1.0.0")

# ---------- Helpers ----------

def parse_hex_rgba(value: str, default):
    """
    Accepts #RGB, #RRGGBB, or #RRGGBBAA (case-insensitive).
    Returns (R,G,B,A).
    """
    if not isinstance(value, str):
        return default
    v = value.strip().lstrip("#")
    if len(v) == 3:
        r, g, b = (int(v[i] * 2, 16) for i in range(3))
        return (r, g, b, 255)
    if len(v) == 6:
        r = int(v[0:2], 16); g = int(v[2:4], 16); b = int(v[4:6], 16)
        return (r, g, b, 255)
    if len(v) == 8:
        r = int(v[0:2], 16); g = int(v[2:4], 16); b = int(v[4:6], 16); a = int(v[6:8], 16)
        return (r, g, b, a)
    return default

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------- Request/Response Models ----------

class QRRequest(BaseModel):
    # Content
    text: Optional[str] = Field(None, description="Text to encode; default=current timestamp on server")
    # Styling toggles
    rounded_finders: bool = Field(True, description="Render finder patterns with rounded corners")
    dot_style: bool = Field(True, description="Render data modules as dots (circles). If false: squares.")
    # Colors (hex)
    foreground: str = Field("#000000", description="Dark color as hex (#RRGGBB or #RRGGBBAA)")
    background: str = Field("#ffffff", description="Light color as hex (#RRGGBB or #RRGGBBAA)")
    # Hole/logo
    hole: bool = Field(False, description="Create a central hole painted with background color")
    hole_shape: Literal["circle", "rectangle"] = Field("circle", description="Hole shape")
    hole_percentage: float = Field(0.10, ge=0.0, le=0.20, description="Hole size as fraction of QR width (0..0.20)")
    logo_base64: Optional[str] = Field(None, description="Base64-encoded transparent PNG for logo (optional)")
    use_logo: bool = Field(False, description="If true, place the provided logo (required to send logo_base64)")
    # Output
    pixel_size: Literal[1080] = 1080  # Fixed output size (1080×1080)
    # Canvas corners
    rounded_canvas: bool = Field(True, description="White background with rounded outer corners")
    finder_round_ratio: float = Field(0.45, ge=0.0, le=0.5, description="Corner rounding ratio for finders (0..0.5)")
    dot_margin: float = Field(0.18, ge=0.0, le=0.49, description="For dots: 0=square fill, 0.49=tiny dots")
    quiet_zone_modules: int = Field(4, ge=1, le=8, description="Quiet zone in modules (normally 4)")
    error_correction: Literal["L", "M", "Q", "H"] = Field("H", description="QR Error correction level")

    @field_validator("logo_base64")
    @classmethod
    def validate_b64(cls, v):
        if v is None:
            return v
        # Allow raw base64 or data URL
        if v.startswith("data:"):
            m = re.match(r"^data:image/(png|octet-stream);base64,(.+)$", v, re.I)
            if not m:
                raise ValueError("Only data:image/png;base64 is accepted")
            v = m.group(2)
        # quick sanity check
        try:
            base64.b64decode(v, validate=True)
        except Exception:
            raise ValueError("logo_base64 must be valid base64")
        return v

class QRResponse(BaseModel):
    width: int
    height: int
    content_type: str
    png_base64: str

# ---------- Core draw routines (module-accurate) ----------

def generate_matrix(text: Optional[str], ec: str):
    import datetime
    payload = text or datetime.datetime.utcnow().isoformat()
    ec_map = {"L": qrcode.constants.ERROR_CORRECT_L,
              "M": qrcode.constants.ERROR_CORRECT_M,
              "Q": qrcode.constants.ERROR_CORRECT_Q,
              "H": qrcode.constants.ERROR_CORRECT_H}
    qr = qrcode.QRCode(
        version=None,
        error_correction=ec_map.get(ec, qrcode.constants.ERROR_CORRECT_H),
        box_size=1,
        border=0,  # we will handle quiet zone ourselves
    )
    qr.add_data(payload)
    qr.make(fit=True)
    matrix = qr.get_matrix()  # list[list[bool]]
    return matrix  # N x N

def draw_qr(req: QRRequest) -> Image.Image:
    m = generate_matrix(req.text, req.error_correction)
    N = len(m)
    B = req.quiet_zone_modules
    SIZE = req.pixel_size

    # Compute integer module size and center inside canvas if needed
    modules_total = N + 2 * B
    S = SIZE // modules_total
    if S < 1:
        raise ValueError("Output too small for this payload/EC; increase pixel_size.")
    render_px = modules_total * S
    offset = (SIZE - render_px) // 2

    DARK = parse_hex_rgba(req.foreground, (0, 0, 0, 255))
    LIGHT = parse_hex_rgba(req.background, (255, 255, 255, 255))

    # Full 1080x1080 transparent canvas => then draw white rounded background
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    def rect_for_block(r0, c0, w):
        x0 = offset + (B + c0) * S
        y0 = offset + (B + r0) * S
        return [x0, y0, x0 + w * S, y0 + w * S]

    # Rounded white background (match finder rounding visually)
    bg_radius = int(req.finder_round_ratio * S * 2.0) if req.rounded_canvas else 0
    draw.rounded_rectangle(
        [offset, offset, offset + render_px, offset + render_px],
        radius=bg_radius,
        fill=LIGHT,
    )

    # Finder helpers
    def draw_finder(top_r, left_c):
        # 1-module light separator (ensure clean ring)
        draw.rectangle(rect_for_block(top_r - 1, left_c - 1, 9), fill=LIGHT)
        r_band = int(req.finder_round_ratio * S)
        r_eye  = int(req.finder_round_ratio * 1.5 * S)
        # 7x7 outer dark
        draw.rounded_rectangle(rect_for_block(top_r, left_c, 7), radius=r_band, fill=DARK)
        # 5x5 middle light
        draw.rounded_rectangle(rect_for_block(top_r + 1, left_c + 1, 5), radius=r_band, fill=LIGHT)
        # 3x3 inner dark
        draw.rounded_rectangle(rect_for_block(top_r + 2, left_c + 2, 3), radius=r_eye, fill=DARK)

    def in_finder_footprint(r, c):
        if -1 <= r <= 7 and -1 <= c <= 7: return True
        if -1 <= r <= 7 and (N - 8) <= c <= N: return True
        if (N - 8) <= r <= N and -1 <= c <= 7: return True
        return False

    # 1) Finders first
    if req.rounded_finders:
        draw_finder(0, 0); draw_finder(0, N - 7); draw_finder(N - 7, 0)
    else:
        # Square finders (still 7/5/3 structure + 1-module separator)
        draw.rectangle(rect_for_block(-1, -1, 9), fill=LIGHT)
        draw.rectangle(rect_for_block(0, 0, 7), fill=DARK)
        draw.rectangle(rect_for_block(1, 1, 5), fill=LIGHT)
        draw.rectangle(rect_for_block(2, 2, 3), fill=DARK)
        draw.rectangle(rect_for_block(-1, N - 8, 9), fill=LIGHT)
        draw.rectangle(rect_for_block(0, N - 7, 7), fill=DARK)
        draw.rectangle(rect_for_block(1, N - 6, 5), fill=LIGHT)
        draw.rectangle(rect_for_block(2, N - 5, 3), fill=DARK)
        draw.rectangle(rect_for_block(N - 8, -1, 9), fill=LIGHT)
        draw.rectangle(rect_for_block(N - 7, 0, 7), fill=DARK)
        draw.rectangle(rect_for_block(N - 6, 1, 5), fill=LIGHT)
        draw.rectangle(rect_for_block(N - 5, 2, 3), fill=DARK)

    # 2) Data modules (dots or squares), skipping the 9×9 finder+separator areas
    if req.dot_style:
        dot_margin = clamp(req.dot_margin, 0.0, 0.49)
        r_px = int(S * (0.5 - dot_margin))
        for r in range(N):
            for c in range(N):
                if not m[r][c]: continue
                if in_finder_footprint(r, c): continue
                cx = offset + (B + c) * S + S // 2
                cy = offset + (B + r) * S + S // 2
                draw.ellipse([cx - r_px, cy - r_px, cx + r_px, cy + r_px], fill=DARK)
    else:
        for r in range(N):
            for c in range(N):
                if not m[r][c]: continue
                if in_finder_footprint(r, c): continue
                draw.rectangle(rect_for_block(r, c, 1), fill=DARK)

    # 3) Hole (after modules & finders), filled with background (white)
    if req.hole and req.hole_percentage > 0:
        hole_px = int(render_px * clamp(req.hole_percentage, 0.0, 0.20))
        cx = offset + render_px // 2
        cy = offset + render_px // 2
        if req.hole_shape == "rectangle":
            hw = hh = hole_px // 2
            draw.rectangle([cx - hw, cy - hh, cx + hw, cy + hh], fill=LIGHT)
        else:
            r = hole_px // 2
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=LIGHT)

    # 4) Logo (optional) — resized to fit within 20% of final image (nearest neighbor)
    if req.use_logo and req.logo_base64:
        try:
            raw = base64.b64decode(req.logo_base64.split(",")[-1])
            with Image.open(io.BytesIO(raw)).convert("RGBA") as logo:
                max_side = int(SIZE * 0.20)
                logo.thumbnail((max_side, max_side), Image.NEAREST)
                lw, lh = logo.size
                cx = offset + render_px // 2
                cy = offset + render_px // 2
                img.alpha_composite(logo, (cx - lw // 2, cy - lh // 2))
        except Exception:
            # If logo decoding fails, just ignore logo
            pass

    return img

# ---------- Routes ----------

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/qr", response_model=QRResponse)
def create_qr(req: QRRequest = Body(...)):
    try:
        img = draw_qr(req)
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return JSONResponse(
            content=QRResponse(
                width=img.width,
                height=img.height,
                content_type="image/png",
                png_base64=b64,
            ).model_dump()
        )
    except ValidationError as e:
        return JSONResponse(status_code=422, content=e.errors())
    except Exception as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

# Run with: uvicorn fastapi_service.main:app --reload --port 8000
