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

"""Storage backend interface and factory.

A ``StorageBackend`` abstracts the small set of file-shaped operations
``ShopService`` actually performs against per-shop writable state:

  - list ``config.json`` / ``learning_state.json`` as text
  - write them back
  - list and read/write uploaded product CSVs (binary)
  - enumerate custom-uploaded shop ids (for ``list_available_shops``)

Names are POSIX-style relative paths scoped to a shop, e.g. ``config.json`` or
``data/products_20260904123000.csv``. Backends decide how to namespace keys
(filesystem: a directory tree; Blob: a flat key with a prefix). Callers never
see absolute storage paths.
"""

from __future__ import annotations

from typing import List, Optional, Protocol, Tuple, runtime_checkable


@runtime_checkable
class StorageBackend(Protocol):
    """Per-shop writable-state storage."""

    @property
    def name(self) -> str:
        """Short identifier for logging, e.g. ``"local"`` / ``"vercel-blob"``."""
        ...

    def list_shops(self) -> List[str]:
        """Return custom-uploaded shop ids (numeric strings), unordered."""
        ...

    def read_text(self, shop_id: str, name: str) -> Optional[str]:
        """Return text content of ``name`` for ``shop_id``, or ``None`` if absent."""
        ...

    def write_text(self, shop_id: str, name: str, text: str) -> None:
        """Atomically-ish write text to ``name`` for ``shop_id``."""
        ...

    def read_bytes(self, shop_id: str, name: str) -> Optional[bytes]:
        """Return raw bytes of ``name`` for ``shop_id``, or ``None`` if absent."""
        ...

    def write_bytes(self, shop_id: str, name: str, data: bytes) -> None:
        """Write raw bytes to ``name`` for ``shop_id``."""
        ...

    def list_csvs(self, shop_id: str) -> List[Tuple[str, float]]:
        """List uploaded product CSVs.

        Returns ``(name, mtime_epoch_seconds)`` pairs, ordered newest first.
        ``name`` is the relative path (e.g. ``data/products_<ts>.csv``).
        """
        ...


def get_storage_backend() -> StorageBackend:
    """Pick a backend at import-time based on env.

    Selection order:
      1. ``AREA303_STORAGE_BACKEND`` explicit ("local" | "blob") wins.
      2. ``BLOB_READ_WRITE_TOKEN`` + ``VERCEL=1`` -> blob.
      3. Otherwise -> local filesystem.
    """
    import os

    forced = os.environ.get("AREA303_STORAGE_BACKEND", "").strip().lower()
    has_token = bool(os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip())
    is_vercel = os.environ.get("VERCEL") == "1"

    if forced == "blob" or (forced != "local" and is_vercel and has_token):
        from .vercel_blob import VercelBlobBackend
        return VercelBlobBackend()
    from .local_filesystem import LocalFilesystemBackend
    return LocalFilesystemBackend()
