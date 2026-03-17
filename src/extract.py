"""
Extract structured data from handwritten cladding sketches using Gemini Vision.
Falls back to OpenRouter when Gemini quota (20/day) is exceeded.
Falls back to Claude (Anthropic) if ANTHROPIC_API_KEY is set.
"""
import base64
import json
import os
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _get_secret(key: str) -> str | None:
    """Read secret from environment or Streamlit Cloud secrets."""
    val = os.getenv(key)
    if val:
        return val
    try:
        import streamlit as st
        return st.secrets.get(key)
    except Exception:
        return None

# Models to try in order (503 = overloaded, try next)
GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
]

# OpenRouter free vision model (fallback)
OPENROUTER_MODEL = "google/gemini-2.0-flash-exp:free"

# Claude fallback model (cheap, excellent vision)
CLAUDE_MODEL = "claude-haiku-4-5-20251001"

EXTRACTION_PROMPT = """You are analyzing a handwritten technical drawing of aluminum facade cladding panels.
The drawing is on grid paper and may contain multiple profiles with dimensions in millimeters.

Extract ALL data and return ONLY valid JSON matching this exact structure. No other text, no markdown.

{
  "header": {
    "project_id": "string (e.g. MR277-3)",
    "date": "string (e.g. 26/02/2025)",
    "client_name": "string",
    "project_name": "string",
    "order_number": "string or number",
    "color_ral": "string (e.g. 9011)",
    "material": "אלומיניום",
    "thickness_mm": 2
  },
  "panels": [
    {
      "panel_id": "string (e.g. S-101)",
      "length_mm": number,
      "width_mm": number,
      "quantity": number,
      "turn": "N" or "Y",
      "notes": "string (e.g. ניקוב or בלי ניקוב)",
      "profile_type": "K" or "P" or null,
      "profile_dimensions": [number, ...] or null,
      "bend_angle_deg": 93,
      "bend_offset_mm": 30
    }
  ]
}

Rules:
- All dimensions in mm. Default thickness 2mm, default bend angle 93 degrees.
- If a value is unclear, use null.
- panel_id: use id from drawing (e.g. 1570) or generate S-101, S-102...
- Extract every profile/panel you see.
- Return ONLY the JSON object, nothing else.
"""


def _parse_json_response(text: str) -> dict:
    """Parse JSON from model response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last fence lines
        inner = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner.append(line)
        text = "\n".join(inner).strip()
    return json.loads(text)


def _extract_via_gemini(image_bytes: bytes, mime: str) -> dict:
    """Extract using Gemini via google-genai SDK."""
    from google import genai
    from google.genai import types
    from google.genai.errors import ServerError, ClientError

    api_key = _get_secret("GOOGLE_API_KEY") or _get_secret("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY not set")

    client = genai.Client(api_key=api_key)
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type=mime),
        EXTRACTION_PROMPT,
    ]

    last_error = None
    for model in GEMINI_MODELS:
        for retry in range(3):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=contents,
                )
                return _parse_json_response(response.text)

            except (ServerError, ClientError) as e:
                last_error = e
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    # Daily quota hit - no point retrying same model, try next
                    break
                if "503" in err_str or "UNAVAILABLE" in err_str:
                    time.sleep((retry + 1) * 3)
                    continue
                raise
            except json.JSONDecodeError:
                if retry < 2:
                    time.sleep(2)
                    continue
                raise

    # All models exhausted
    if last_error:
        raise last_error
    raise RuntimeError("All Gemini models failed")


def _extract_via_openrouter(image_bytes: bytes, mime: str) -> dict:
    """Extract via OpenRouter API (fallback when Gemini quota exceeded)."""
    api_key = _get_secret("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError(
            "OpenRouter API key not set. "
            "Get a free key at https://openrouter.ai/keys and add OPENROUTER_API_KEY to .env"
        )
    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    data_uri = f"data:{mime};base64,{b64}"
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["choices"][0]["message"]["content"]
    return _parse_json_response(text)


def _extract_via_claude(image_bytes: bytes, mime: str) -> dict:
    """
    Extract via Anthropic Claude API.
    ~$0.001 per image (claude-haiku). Set ANTHROPIC_API_KEY in .env.
    """
    api_key = _get_secret("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set")

    b64 = base64.standard_b64encode(image_bytes).decode("ascii")
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        json={
            "model": CLAUDE_MODEL,
            "max_tokens": 2048,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": mime,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": EXTRACTION_PROMPT},
                    ],
                }
            ],
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    text = data["content"][0]["text"]
    return _parse_json_response(text)


def extract_from_image(image_path: str | Path) -> dict:
    """
    Extract structured data from image.
    Tries in order: Gemini → Claude → OpenRouter
    """
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    mime = "image/jpeg" if path.suffix.lower() in (".jpg", ".jpeg") else "image/png"
    image_bytes = path.read_bytes()

    errors = []

    # 1. Try Gemini (free, primary)
    gemini_key = _get_secret("GOOGLE_API_KEY") or _get_secret("GEMINI_API_KEY")
    if gemini_key:
        try:
            return _extract_via_gemini(image_bytes, mime)
        except Exception as e:
            err_str = str(e)
            errors.append(f"Gemini: {err_str}")
            is_quota = "429" in err_str or "quota" in err_str.lower() or "RESOURCE_EXHAUSTED" in err_str
            if not is_quota:
                # Non-quota error (auth, network) - don't silently fall through
                raise

    # 2. Try Claude (paid but very cheap ~$0.001/image, excellent quality)
    anthropic_key = _get_secret("ANTHROPIC_API_KEY")
    if anthropic_key:
        try:
            return _extract_via_claude(image_bytes, mime)
        except Exception as e:
            errors.append(f"Claude: {e}")

    # 3. Try OpenRouter (free fallback)
    openrouter_key = _get_secret("OPENROUTER_API_KEY")
    if openrouter_key:
        try:
            return _extract_via_openrouter(image_bytes, mime)
        except Exception as e:
            errors.append(f"OpenRouter: {e}")

    # All failed
    quota_hit = any("quota" in e.lower() or "429" in e for e in errors)
    if quota_hit:
        raise RuntimeError(
            "מכסת ה-API היומית של Gemini נגמרה (20 בקשות ביום).\n"
            "פתרונות:\n"
            "  • המתן למחר (המכסה מתאפסת)\n"
            "  • הוסף ANTHROPIC_API_KEY ל-.env (Claude – ~$0.001 לתמונה)\n"
            "  • הוסף OPENROUTER_API_KEY ל-.env (חינמי)\n"
            "  • העלה קובץ JSON ישירות (ללא API)\n"
            f"שגיאות: {'; '.join(errors)}"
        )
    raise RuntimeError(f"כל ה-API-ים נכשלו: {'; '.join(errors)}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m src.extract <image_path>")
        sys.exit(1)
    result = extract_from_image(sys.argv[1])
    print(json.dumps(result, ensure_ascii=False, indent=2))
