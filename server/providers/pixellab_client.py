import base64
import json
import time
import urllib.error
import urllib.request
from io import BytesIO

from PIL import Image

import config

DIR_FROM_LABEL = {
    "south": "S",
    "s": "S",
    "south-west": "SW",
    "southwest": "SW",
    "sw": "SW",
    "west": "W",
    "w": "W",
    "north-west": "NW",
    "northwest": "NW",
    "nw": "NW",
    "north": "N",
    "n": "N",
    "north-east": "NE",
    "northeast": "NE",
    "ne": "NE",
    "east": "E",
    "e": "E",
    "south-east": "SE",
    "southeast": "SE",
    "se": "SE",
}


def _friendly_http(status: int, body: str) -> str:
    if status == 401:
        return "PixelLab API token is invalid. Set PIXELLAB_API_KEY from https://pixellab.ai/account"
    if status == 402:
        return "PixelLab account is out of credits"
    if status == 429:
        return "PixelLab concurrency limit reached. Wait and retry."
    snippet = body[:400].strip() or "no response body"
    return f"PixelLab API error {status}: {snippet}"


def request(method: str, path: str, payload: dict | None = None, timeout: int = 90) -> dict:
    if not config.PIXELLAB_API_KEY:
        raise ValueError("PIXELLAB_API_KEY is not set")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{config.PIXELLAB_API_BASE}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {config.PIXELLAB_API_KEY}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "ignore")
        raise RuntimeError(_friendly_http(exc.code, body)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach PixelLab API: {exc.reason}") from exc


def encode_image(image: Image.Image) -> dict:
    buffer = BytesIO()
    image.convert("RGBA").save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return {"type": "base64", "base64": f"data:image/png;base64,{encoded}", "format": "png"}


def decode_image(value: str | dict) -> Image.Image:
    if isinstance(value, dict):
        value = str(value.get("base64") or value.get("url") or "")
    if value.startswith("http://") or value.startswith("https://"):
        return download_image(value)
    if "base64," in value:
        value = value.split("base64,", 1)[1]
    return Image.open(BytesIO(base64.b64decode(value))).convert("RGBA")


def download_image(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"Accept": "image/png,image/*,*/*"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return Image.open(BytesIO(response.read())).convert("RGBA")


def poll_job(job_id: str, on_step=None, timeout_s: int = 600) -> dict:
    started = time.time()
    delay = 2.0
    while time.time() - started < timeout_s:
        payload = request("GET", f"/background-jobs/{job_id}", timeout=30)
        status = str(payload.get("status") or "")
        if on_step:
            elapsed = int(time.time() - started)
            on_step(f"PixelLab job {status} ({elapsed}s)")
        if status == "completed":
            return payload
        if status == "failed":
            detail = payload.get("last_response") or payload
            raise RuntimeError(f"PixelLab job failed: {detail}")
        time.sleep(delay)
        delay = min(5.0, delay + 0.4)
    raise TimeoutError("PixelLab job timed out after 10 minutes")


def collect_direction_images(payload: dict | None) -> dict[str, Image.Image]:
    found: dict[str, Image.Image] = {}
    if not payload:
        return found
    stack: list[object] = [payload]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            urls = current.get("rotation_urls")
            if isinstance(urls, dict):
                for label, value in urls.items():
                    direction = DIR_FROM_LABEL.get(str(label).lower().replace("_", "-"))
                    if direction and value:
                        found[direction] = decode_image(value)
            for key, value in current.items():
                direction = DIR_FROM_LABEL.get(str(key).lower().replace("_", "-"))
                if direction and value and key != "rotation_urls":
                    if isinstance(value, str) or (isinstance(value, dict) and ("base64" in value or "url" in value)):
                        try:
                            found[direction] = decode_image(value)
                        except Exception:
                            pass
                if key in {"last_response", "result", "rotations", "images", "frames", "data"}:
                    stack.append(value)
        elif isinstance(current, list):
            stack.extend(current)
    return found


def collect_frames(payload: dict | None) -> list[Image.Image]:
    if not payload:
        return []
    blob = payload.get("last_response") or payload
    candidates = []
    if isinstance(blob, dict):
        candidates = blob.get("frames") or blob.get("images") or blob.get("animation") or []
    frames: list[Image.Image] = []
    if isinstance(candidates, dict):
        candidates = list(candidates.values())
    for item in candidates:
        try:
            frames.append(decode_image(item))
        except Exception:
            continue
    return frames
