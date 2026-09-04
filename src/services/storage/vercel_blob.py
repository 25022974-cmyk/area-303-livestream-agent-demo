# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""Vercel Blob-backed storage (used when ``VERCEL=1`` + ``BLOB_READ_WRITE_TOKEN``).

The filesystem on Vercel serverless is ephemeral, so per-shop writable state is
persisted to Vercel Blob via its HTTP API. We use only ``urllib`` (no extra
dependency), mirroring ``ai_client.py``'s pattern. Every key is namespaced as
``area303/<shop_id>/<name>`` — Blob keys are flat, so the "directory" is just a
string prefix.

Vercel Blob REST (token-scoped store endpoint):
    GET  <base>/?prefix=<p>&mode=search[&cursor=<c>]   -> {blobs:[{pathname,url,uploadedAt,...}], cursor?}
    GET  <blob.url>                                    -> raw bytes (signed public URL)
    PUT  <base>/<key>                                  -> {url, pathname}
        Headers: Authorization: Bearer <token>,
                 x-addRandomSuffix: false,
                 x-content-type: <mime>
        Body: raw bytes
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import List, Optional, Tuple

# Vercel-provided store base. The store-specific endpoint is injected by Vercel
# as BLOB_STORE_URL when the Blob store is created; the generic
# blob.vercel-app.com hostname also works with the read/write token. We prefer
# BLOB_STORE_URL if set, then fall back to the project hostname.
_BLOB_BASE = os.environ.get("BLOB_STORE_URL", "https://blob.vercel-app.com").rstrip("/")
_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")
_PREFIX = "area303"
_USER_AGENT = "area303-livestream-agent/1.0"
_TIMEOUT = 30

_SHOP_ID_RE = re.compile(r"^\d+$")


class VercelBlobBackend:
    """Per-shop writable state backed by Vercel Blob over HTTP."""

    name = "vercel-blob"

    # -- key helpers -----------------------------------------------------
    @staticmethod
    def _key(shop_id: str, name: str) -> str:
        sid = str(shop_id or "").strip()
        if not sid or not _SHOP_ID_RE.match(sid):
            raise ValueError(f"Invalid shop_id: {shop_id!r}. Must be numeric.")
        # name is relative POSIX path; normalize backslashes just in case.
        normalized = name.replace("\\", "/").lstrip("/")
        return f"{_PREFIX}/{sid}/{normalized}"

    def _shop_key_prefix(self, shop_id: str) -> str:
        sid = str(shop_id or "").strip()
        if not sid or not _SHOP_ID_RE.match(sid):
            raise ValueError(f"Invalid shop_id: {shop_id!r}. Must be numeric.")
        return f"{_PREFIX}/{sid}/"

    # -- low-level HTTP --------------------------------------------------
    def _auth_headers(self) -> dict:
        if not _TOKEN:
            raise RuntimeError("BLOB_READ_WRITE_TOKEN chua duoc cau hinh.")
        return {
            "Authorization": f"Bearer {_TOKEN}",
            "User-Agent": _USER_AGENT,
        }

    def _list_prefix(self, prefix: str) -> List[dict]:
        """Return all blobs whose pathname starts with ``prefix``, paging through cursor."""
        out: List[dict] = []
        cursor: Optional[str] = None
        # Safety cap to avoid infinite loops on a misbehaving API.
        for _ in range(100):
            qs = {"prefix": prefix, "mode": "search", "limit": "1000"}
            if cursor:
                qs["cursor"] = cursor
            qs = {k: v for k, v in qs.items() if v is not None}
            url = f"{_BLOB_BASE}/?{urllib.parse.urlencode(qs)}"
            try:
                req = urllib.request.Request(url, headers=self._auth_headers(), method="GET")
                with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                # 404 / empty store -> treat as no blobs
                if e.code in (404,):
                    return out
                raise
            blobs = payload.get("blobs") or []
            out.extend(blobs)
            cursor = payload.get("cursor")
            if not cursor or not blobs:
                break
        return out

    # -- StorageBackend API ---------------------------------------------
    def list_shops(self) -> List[str]:
        blobs = self._list_prefix(f"{_PREFIX}/")
        ids = set()
        for b in blobs:
            pathname = b.get("pathname", "")
            parts = pathname.split("/")
            # expect ["area303", "<shop_id>", ...]
            if len(parts) >= 2 and parts[0] == _PREFIX and _SHOP_ID_RE.match(parts[1]):
                ids.add(parts[1])
        return list(ids)

    def read_text(self, shop_id: str, name: str) -> Optional[str]:
        raw = self.read_bytes(shop_id, name)
        if raw is None:
            return None
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return None

    def read_bytes(self, shop_id: str, name: str) -> Optional[bytes]:
        key = self._key(shop_id, name)
        # find the blob (list with exact prefix, then match pathname)
        prefix = self._shop_key_prefix(shop_id)
        for b in self._list_prefix(prefix):
            if b.get("pathname") == key:
                download_url = b.get("url")
                if not download_url:
                    return None
                try:
                    req = urllib.request.Request(download_url, headers={"User-Agent": _USER_AGENT})
                    with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
                        return resp.read()
                except urllib.error.HTTPError as e:
                    if e.code == 404:
                        return None
                    raise
        return None

    def write_text(self, shop_id: str, name: str, text: str) -> None:
        self.write_bytes(shop_id, name, text.encode("utf-8"), content_type="application/json; charset=utf-8")

    def write_bytes(self, shop_id: str, name: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        key = self._key(shop_id, name)
        # PUT <base>/<key> with URL-encoded key segments to keep slashes
        url = f"{_BLOB_BASE}/{urllib.parse.quote(key, safe='/')}"
        headers = self._auth_headers()
        headers["x-addRandomSuffix"] = "false"
        headers["x-content-type"] = content_type
        headers["Content-Length"] = str(len(data))
        req = urllib.request.Request(url, data=data, headers=headers, method="PUT")
        try:
            with urllib.request.urlopen(req, timeout=_TIMEOUT):
                pass
        except urllib.error.HTTPError as e:
            # surface a concise error message
            body = ""
            try:
                body = e.read().decode("utf-8", "replace")[:200]
            except Exception:
                pass
            raise RuntimeError(f"Vercel Blob PUT that bai ({e.code}) cho '{key}': {body}") from e

    def list_csvs(self, shop_id: str) -> List[Tuple[str, float]]:
        prefix = self._shop_key_prefix(shop_id) + "data/products_"
        blobs = self._list_prefix(prefix)
        items: List[Tuple[str, float]] = []
        for b in blobs:
            pathname = b.get("pathname", "")
            # map back to the relative name the ShopService expects
            stripped = pathname[len(self._shop_key_prefix(shop_id)):]
            # parse uploadedAt ISO -> epoch seconds (best-effort)
            ts_str = b.get("uploadedAt") or b.get("createdAt") or ""
            epoch = 0.0
            if ts_str:
                try:
                    # ISO 8601 with Z; fromisoformat needs +00:00
                    from datetime import datetime
                    dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                    epoch = dt.timestamp()
                except Exception:
                    epoch = 0.0
            items.append((stripped, epoch))
        items.sort(key=lambda x: x[1], reverse=True)
        return items
