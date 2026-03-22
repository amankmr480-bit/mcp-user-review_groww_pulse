"""
Minimal GROQ (OpenAI-compatible) chat client with retries and JSON mode.

Used by Phase 3 to generate weekly note + email draft in a single call.
"""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from config import GROQ_API_URL, GROQ_MODEL, GROQ_API_KEY


def _loads_json_object(text: str) -> dict[str, Any]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # If the model returns extra text, extract the first JSON object.
        m = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not m:
            raise
        return json.loads(m.group(0))


# Backoff settings (kept local to avoid duplicating config structure too much).
INITIAL_BACKOFF_SEC = float(os.environ.get("PHASE3_INITIAL_BACKOFF_SEC", "1.0"))
MAX_RETRIES = int(os.environ.get("PHASE3_MAX_RETRIES", "5"))


def chat_completion_json(
    system_prompt: str,
    user_prompt: str,
    *,
    temperature: float = 0.2,
    api_key: Optional[str] = None,
) -> dict[str, Any]:
    key = (api_key or GROQ_API_KEY or "").strip()
    if not key:
        raise ValueError("GROQ_API_KEY is not set")

    use_response_format = os.environ.get("GROQ_USE_RESPONSE_FORMAT", "1").strip().lower() not in (
        "0",
        "false",
        "no",
    )

    payload_base: dict[str, Any] = {
        "model": GROQ_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature,
    }
    headers = {
        "Authorization": f"Bearer {key}",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) GroqPhase3/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }

    def _make_request(payload: dict[str, Any]) -> urllib.request.Request:
        body = json.dumps(payload).encode("utf-8")
        return urllib.request.Request(GROQ_API_URL, data=body, method="POST", headers=headers)

    tried_without_response_format = False
    payload = dict(payload_base)
    if use_response_format:
        payload["response_format"] = {"type": "json_object"}
    req = _make_request(payload)

    last_err: Optional[Exception] = None
    backoff = INITIAL_BACKOFF_SEC
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            content = raw["choices"][0]["message"]["content"]
            return _loads_json_object(content)
        except urllib.error.HTTPError as e:
            last_err = e
            code = e.code
            err_body = ""
            try:
                err_body = e.read().decode("utf-8", errors="replace")
            except Exception:
                pass

            if os.environ.get("GROQ_DEBUG", "").strip():
                snippet = (err_body or "").strip()[:800]
                print(f"GROQ HTTPError {code}. Body snippet: {snippet}")

            if code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES - 1:
                m = re.search(r"Please try again in\s+([0-9]*\.?[0-9]+)\s*s?\b", err_body or "")
                if m:
                    wait_s = float(m.group(1))
                    time.sleep(wait_s + random.uniform(0, 0.2))
                else:
                    time.sleep(backoff + random.uniform(0, 0.5 * backoff))
                    backoff = min(backoff * 2, 60.0)
                continue

            if (
                code in (400, 403)
                and use_response_format
                and not tried_without_response_format
                and attempt < MAX_RETRIES - 1
            ):
                tried_without_response_format = True
                payload = dict(payload_base)
                req = _make_request(payload)
                continue

            snippet = (err_body or "").strip()[:1200]
            extra = f" model={GROQ_MODEL} json_mode={use_response_format} retries_attempted={attempt+1}"
            raise RuntimeError(f"GROQ request failed with HTTP {code}.{extra}\nBody snippet:\n{snippet}")
        except (urllib.error.URLError, json.JSONDecodeError, KeyError, IndexError) as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                time.sleep(backoff + random.uniform(0, 0.5 * backoff))
                backoff = min(backoff * 2, 60.0)
                continue
            raise

    assert last_err is not None
    raise last_err

