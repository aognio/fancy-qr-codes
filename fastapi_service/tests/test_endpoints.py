import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from fastapi_service.main import (
    QRRequest,
    app,
    clamp,
    draw_qr,
    parse_hex_rgba,
)

client = TestClient(app)


def _decode_png(b64_string: str) -> Image.Image:
    raw_bytes = base64.b64decode(b64_string)
    with Image.open(io.BytesIO(raw_bytes)) as img:
        return img.convert("RGBA")


def _make_logo_base64(color=(0, 0, 255, 255), size=(64, 64)) -> str:
    buff = io.BytesIO()
    Image.new("RGBA", size, color).save(buff, format="PNG")
    return base64.b64encode(buff.getvalue()).decode("ascii")


def test_basic_qr_generation_returns_png_base64():
    response = client.post("/qr", json={"text": "Hello"})
    assert response.status_code == 200
    payload = response.json()
    image = _decode_png(payload["png_base64"])
    assert payload["width"] == 1080
    assert payload["height"] == 1080
    assert payload["content_type"] == "image/png"
    assert image.size == (1080, 1080)
    # Finder background should be light (white) in a corner pixel
    assert image.getpixel((10, 10))[0:3] == (255, 255, 255)


def test_qr_generation_with_logo_and_custom_options():
    logo_b64 = _make_logo_base64()
    request_payload = {
        "text": "Custom",
        "rounded_finders": False,
        "dot_style": False,
        "foreground": "#336699",
        "background": "#ffeeff",
        "hole": True,
        "hole_shape": "rectangle",
        "hole_percentage": 0.18,
        "use_logo": True,
        "logo_base64": logo_b64,
        "rounded_canvas": False,
        "finder_round_ratio": 0.2,
        "dot_margin": 0.15,
        "quiet_zone_modules": 6,
        "error_correction": "M",
    }
    response = client.post("/qr", json=request_payload)
    assert response.status_code == 200
    data = response.json()
    image = _decode_png(data["png_base64"])
    # The center pixel should come from our blue logo overlay.
    assert image.getpixel((540, 540))[2] >= 200
    # Background change should persist in the quiet zone area.
    assert image.getpixel((50, 540))[0:3] == (255, 238, 255)


def test_logo_data_url_is_accepted():
    bare_logo = _make_logo_base64(color=(20, 200, 20, 255))
    data_url = f"data:image/png;base64,{bare_logo}"
    response = client.post(
        "/qr",
        json={
            "text": "data-url",
            "use_logo": True,
            "logo_base64": data_url,
        },
    )
    assert response.status_code == 200
    decoded = _decode_png(response.json()["png_base64"])
    # Expect the central pixel to reflect our green logo fill.
    assert decoded.getpixel((540, 540))[1] >= 180


def test_invalid_logo_base64_returns_422():
    response = client.post(
        "/qr",
        json={"text": "bad", "use_logo": True, "logo_base64": "not_base64"},
    )
    assert response.status_code == 422


def test_hole_percentage_out_of_range_returns_422():
    response = client.post("/qr", json={"hole_percentage": 0.25})
    assert response.status_code == 422


def test_parse_hex_rgba_variants():
    assert parse_hex_rgba("#fff", (0, 0, 0, 0)) == (255, 255, 255, 255)
    assert parse_hex_rgba("#112233", (0, 0, 0, 0)) == (17, 34, 51, 255)
    assert parse_hex_rgba("#112233AA", (0, 0, 0, 0)) == (17, 34, 51, 170)
    assert parse_hex_rgba("invalid", (1, 1, 1, 1)) == (1, 1, 1, 1)


@pytest.mark.parametrize(
    "value,lo,hi,expected",
    [
        (-5, 0, 10, 0),
        (5, 0, 10, 5),
        (15, 0, 10, 10),
    ],
)
def test_clamp_behavior(value, lo, hi, expected):
    assert clamp(value, lo, hi) == expected


def test_draw_qr_direct_invocation_matches_request_model_defaults():
    request = QRRequest()
    image = draw_qr(request)
    assert image.size == (1080, 1080)
    # Default background stays fully white.
    assert image.getpixel((20, 20)) == (255, 255, 255, 255)
