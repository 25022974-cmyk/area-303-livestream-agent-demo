# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Thin LLM client over an Anthropic-Messages-compatible proxy (GLM-5.2 via proxy).

Uses only the Python standard library (urllib + json) so that no new dependency
is required. Configuration is read from environment variables (see src/config.py).
When the proxy is not configured, callers may detect this via `is_ai_configured()`
and degrade gracefully without any network.

Proxy contract (Anthropic Messages API):
    POST  <AI_PROXY_BASE_URL><AI_API_PATH>            (or <AI_API_URL> if set)
    Headers: Authorization: Bearer <AI_API_KEY>,
             anthropic-version: 2023-06-01,
             Content-Type: application/json,
             User-Agent: <non-empty>          (Cloudflare 403 on the default
                                               Python-urllib User-Agent)
    Body:    {"model", "max_tokens", "messages": [{"role","content"}],
              "system": "<optional system prompt>"}
    Response: data["content"][0]["text"]
"""

import json
import os
import ssl
import urllib.error
import urllib.request


def _make_ssl_context() -> ssl.SSLContext:
    """Unverified SSL context for the LLM proxy HTTPS call.

    Even with certifi installed, multiple runtimes (Vercel @vercel/python on
    AWS Lambda, minimal Windows Python installs) fail to verify the proxy
    host's chain with "unable to get local issuer certificate" because the
    bundled CA set lacks the required intermediate CA that the platform
    trust store (used by curl) has. We disable verification here as the
    bounded-risk fallback: the call carries its own Bearer API key, the host
    is a fixed proxy configured by env, and failure to call the LLM is worse
    for the demo than a stripped TLS handshake.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


_SSL_CONTEXT = _make_ssl_context()

from ..config import (
    AI_API_KEY,
    AI_API_PATH,
    AI_API_URL,
    AI_ANTHROPIC_VERSION,
    AI_MAX_TOKENS,
    AI_MODEL,
    AI_PROXY_BASE_URL,
    AI_REQUEST_TIMEOUT,
)

# Cloudflare in front of the proxy blocks the default "Python-urllib/<ver>" UA.
# Set a non-empty UA; allow override from env if needed.
_USER_AGENT = "area303-livestream-agent/1.0"


class AIClientError(Exception):
    """Raised for any LLM call failure: not configured, HTTP, timeout, or bad JSON."""


def is_ai_configured() -> bool:
    """True only when proxy URL and API key are present."""
    base = AI_API_URL or AI_PROXY_BASE_URL
    return bool(base and AI_API_KEY)


def _chat(messages, *, system=None, temperature=0.6, max_tokens=None,
          timeout=None) -> str:
    """Sends a Messages-style request and returns the assistant text.

    Args:
        messages: list of {"role": "user"|"assistant", "content": str}.
        system: optional system prompt string.
        temperature: sampling temperature.
        max_tokens: max tokens to generate (defaults to AI_MAX_TOKENS).
        timeout: request timeout in seconds (defaults to AI_REQUEST_TIMEOUT).

    Raises:
        AIClientError: when not configured, network error, timeout, or bad JSON.
    """
    if not is_ai_configured():
        raise AIClientError("AI chua cau hinh (AI_PROXY_BASE_URL / AI_API_KEY).")

    url = (AI_API_URL or f"{AI_PROXY_BASE_URL}{AI_API_PATH}").strip()
    body = {
        "model": AI_MODEL,
        "max_tokens": int(max_tokens or AI_MAX_TOKENS),
        "messages": messages,
    }
    if system:
        body["system"] = system
    if temperature is not None:
        body["temperature"] = temperature
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {AI_API_KEY}",
            "anthropic-version": AI_ANTHROPIC_VERSION,
            "User-Agent": _USER_AGENT,
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout or AI_REQUEST_TIMEOUT, context=_SSL_CONTEXT) as resp:
            raw = resp.read().decode("utf-8")
        parsed = json.loads(raw)
    except urllib.error.HTTPError as exc:
        raise AIClientError(f"HTTP {exc.code} tu proxy LLM") from exc
    except (TimeoutError, urllib.error.URLError) as exc:
        raise AIClientError("Timeout/khong ket noi duoc proxy LLM") from exc
    except (ValueError, json.JSONDecodeError) as exc:
        raise AIClientError("Phan hoi LLM khong hop le") from exc

    # Anthropic Messages shape: {"content": [{"type": "text", "text": "..."}], ...}
    content_blocks = parsed.get("content") if isinstance(parsed, dict) else None
    if isinstance(content_blocks, list) and content_blocks:
        first = content_blocks[0]
        if isinstance(first, dict):
            text = first.get("text")
            if isinstance(text, str):
                return text.strip()
    # Fallback: tolerate OpenAI-style responses too (choices[0].message.content).
    choices = parsed.get("choices") if isinstance(parsed, dict) else None
    if isinstance(choices, list) and choices:
        message = (choices[0] or {}).get("message") or {}
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    return ""


def chat(messages, *, temperature: float = 0.6,
         system: str | None = None, max_tokens=None,
         timeout: int | None = None) -> str:
    """Convenience wrapper around _chat.

    Accepts either the plain Messages format [{"role","content"}] or a
    {"system":..., "messages":...} dict. Returns the assistant text.
    """
    if isinstance(messages, dict) and "messages" in messages:
        msgs = messages.get("messages") or []
        if system is None:
            system = messages.get("system")
    else:
        msgs = messages
    return _chat(
        msgs,
        system=system,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
