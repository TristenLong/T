import os
import time

import requests
from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
load_dotenv(os.path.join(ROOT_DIR, ".env"), override=True)

PUBLIC_DREAMS_DIR = os.path.join(ROOT_DIR, "public", "dreams")
if not os.path.exists(PUBLIC_DREAMS_DIR):
    os.makedirs(PUBLIC_DREAMS_DIR)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL") or None
# Base URL the UI serves the saved images from. Served straight by the Vite dev
# server (public/ is mounted at /) or by Electron's dist/ renderer host.
LOCAL_IMAGE_BASE = "http://localhost:5173/dreams"

# Puter's image-generation driver. The puter.js SDK calls the same endpoint
# (src/lib/networkUtils.js driverCall); this mirrors its wire shape exactly so
# the armed Puter token from the renderer sign-in works without extra setup.
PUTER_DRIVER_URL = "https://api.puter.com/drivers/call"
PUTER_IMAGE_MODEL = os.getenv("JESTER_PUTER_IMAGE_MODEL", "gpt-image-1-mini")
DREAM_TIMEOUT = 240


def _puter_token():
    """Puter token currently armed in this process, if any.

    configure_puter() (from the renderer's CONNECT PUTER flow or /api/puter)
    stores the token on llm_router.PUTER_API_TOKEN and also pushes it onto
    OPENAI_API_KEY with the Puter base URL. Read the live module global rather
    than a stale import-time snapshot.
    """
    try:
        import llm_router
        if getattr(llm_router, 'PUTER_API_TOKEN', None):
            return llm_router.PUTER_API_TOKEN
    except Exception:
        pass
    token = os.getenv("PUTER_AUTH_TOKEN") or os.getenv("PUTER_API_KEY")
    if token:
        return token
    try:
        import llm_router
        base = os.getenv("OPENAI_BASE_URL") or ""
        if base == llm_router.PUTER_BASE_URL:
            return os.getenv("OPENAI_API_KEY")
    except Exception:
        pass
    return None


def _puter_txt2img(prompt):
    """Generate an image through Puter's armed free-tier backend.

    Returns (image_bytes, error). Exactly one is set. The successful response
    is the raw image (application/octet-stream), mirroring the SDK's
    responseType 'blob' path.
    """
    token = _puter_token()
    if not token:
        return None, "Puter is not armed. Connect Puter first (or set PUTER_AUTH_TOKEN in .env)."
    body = {
        "interface": "puter-image-generation",
        "driver": "ai-image",
        "method": "generate",
        "args": {"prompt": prompt, "model": PUTER_IMAGE_MODEL},
        "auth_token": token,
    }
    try:
        resp = requests.post(
            PUTER_DRIVER_URL,
            json=body,
            headers={"Content-Type": "text/plain;actually=json"},
            timeout=DREAM_TIMEOUT,
        )
    except requests.RequestException as e:
        return None, f"Puter image request failed: {e}"
    data = resp.content
    if resp.status_code == 200 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return data, None
    try:
        payload = data[:400].decode("utf-8", "replace")
    except Exception:
        payload = ""
    return None, f"Puter text-to-image failed (HTTP {resp.status_code}): {payload}"


def _openai_txt2img(prompt):
    """Legacy DALL-E path, only reachable with a real OpenAI key.

    The default .env points OPENAI_API_KEY at a local Ollama shim, which has no
    images endpoint; this path is a guarded fallback, not the primary route.
    """
    if not OPENAI_API_KEY or OPENAI_API_KEY == "ollama":
        return None, "OpenAI fallback unavailable (no real key)."
    client = OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)
    response = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        size="1024x1024",
        quality="standard",
        n=1,
    )
    image_url = response.data[0].url
    img_data = requests.get(image_url, timeout=DREAM_TIMEOUT).content
    return img_data, None


def generate_dream(prompt):
    """Manifest a picture for a prompt and save it under /dreams/.

    Primary backend is Puter's free text-to-image driver (uses whatever token
    the renderer armed). Falls back to the legacy DALL-E call when Puter is
    unarmed AND a real OpenAI key exists. Returns a dict with status and either
    'url' (local HTTP URL) or 'error'.
    """
    if not prompt or not str(prompt).strip():
        return {"status": "ERROR", "message": "Empty prompt"}

    image_bytes, puter_error = _puter_txt2img(prompt)

    if image_bytes is None:
        image_bytes, openai_error = _openai_txt2img(prompt)
        if image_bytes is None:
            return {"status": "ERROR", "message": puter_error, "error": openai_error}

    timestamp = int(time.time())
    filename = f"dream_{timestamp}.png"
    filepath = os.path.join(PUBLIC_DREAMS_DIR, filename)
    try:
        with open(filepath, "wb") as f:
            f.write(image_bytes)
    except OSError as e:
        return {"status": "ERROR", "message": f"Could not save image: {e}"}

    local_url = f"{LOCAL_IMAGE_BASE}/{filename}"
    return {"status": "DREAM_MANIFESTED", "url": local_url}