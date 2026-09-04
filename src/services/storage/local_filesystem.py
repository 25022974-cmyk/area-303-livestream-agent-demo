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

"""Filesystem-backed storage (default for local dev and tests).

This is a faithful extraction of the path operations ``ShopService`` already
performed against ``STORAGE_DIR``: a per-shop directory tree with
``config.json``, ``learning_state.json``, and ``data/products_*.csv``. It
keeps the exact on-disk layout, so existing local data and tests are
unaffected.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple

from ...config import STORAGE_DIR

_SHOP_ID_RE = re.compile(r"^\d+$")
_csv_glob = "products_*.csv"


class LocalFilesystemBackend:
    """Stores per-shop state under ``STORAGE_DIR/<shop_id>/...``."""

    name = "local"

    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir if storage_dir is not None else STORAGE_DIR

    # -- helpers ---------------------------------------------------------
    def _shop_dir(self, shop_id: str) -> Path:
        sid = str(shop_id or "").strip()
        if not sid or not _SHOP_ID_RE.match(sid):
            raise ValueError(f"Invalid shop_id: {shop_id!r}. Must be numeric.")
        d = self.storage_dir / sid
        (d / "data").mkdir(parents=True, exist_ok=True)
        (d / "playbooks").mkdir(parents=True, exist_ok=True)
        return d

    @staticmethod
    def _join(shop_dir: Path, name: str) -> Path:
        # keep name relative inside the shop dir — no escape via ".."
        candidate = (shop_dir / name).resolve()
        shop_root = shop_dir.resolve()
        try:
            candidate.relative_to(shop_root)
        except ValueError:
            raise ValueError(f"Refusing to escape shop dir with name: {name!r}")
        return candidate

    # -- StorageBackend API ---------------------------------------------
    def list_shops(self) -> List[str]:
        shops: List[str] = []
        if not self.storage_dir.exists():
            return shops
        for child in self.storage_dir.iterdir():
            if child.is_dir() and _SHOP_ID_RE.match(child.name):
                shops.append(child.name)
        return shops

    def read_text(self, shop_id: str, name: str) -> Optional[str]:
        path = self._join(self._shop_dir(shop_id), name)
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except Exception:
            return None

    def write_text(self, shop_id: str, name: str, text: str) -> None:
        path = self._join(self._shop_dir(shop_id), name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def read_bytes(self, shop_id: str, name: str) -> Optional[bytes]:
        path = self._join(self._shop_dir(shop_id), name)
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception:
            return None

    def write_bytes(self, shop_id: str, name: str, data: bytes) -> None:
        path = self._join(self._shop_dir(shop_id), name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def list_csvs(self, shop_id: str) -> List[Tuple[str, float]]:
        d = self._shop_dir(shop_id) / "data"
        files = []
        for p in d.glob(_csv_glob):
            if p.is_file():
                files.append((f"data/{p.name}", p.stat().st_mtime))
        files.sort(key=lambda x: x[1], reverse=True)
        return files
