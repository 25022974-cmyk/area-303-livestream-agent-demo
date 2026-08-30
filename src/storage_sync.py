# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; even without the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Seed the writable per-shop storage from committed seed data.

On Vercel (and any serverless host) the bundle filesystem is read-only except
``/tmp``, and ``/tmp`` is wiped when an instance sleeps or is replaced. We point
``STORAGE_DIR`` at a writable subdirectory of ``/tmp`` (see ``config.py``), then
seed it once per instance from ``SEED_DIR`` (committed in the repo at
``data/shops_seed/``) so:

* benchmark + previously-recorded shop state (playbooks, reviews,
  ``learning_state.json``, ``config.json``, uploaded CSVs) is present, and
* the app's ordinary write path (``path.write_text(...)`` in the services)
  keeps working because it targets the seeded copy under ``/tmp``.

This is intentionally best-effort and idempotent — failures (e.g. seed dir
missing during local dev) degrade silently to an empty storage dir, exactly
like the original ``STORAGE_DIR.mkdir`` behaviour.
"""

import shutil
from pathlib import Path

# Marker file written into STORAGE_DIR once seeding completes for a given
# instance. Prevents re-copying when a warm instance re-imports the module or
# when the directory was already populated by an earlier request.
_SEED_MARKER = ".seeded"


def _copy_tree(src: Path, dst: Path) -> None:
    """Copies the contents of ``src`` into ``dst`` recursively (merges)."""
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        target = dst / item.name
        if item.is_dir():
            _copy_tree(item, target)
        else:
            shutil.copy2(item, target)


def ensure_storage_seeded(storage_dir: Path, seed_dir: Path) -> None:
    """Seeds ``storage_dir`` from ``seed_dir`` if it has not been seeded yet.

    Safe to call at import time. No-op when ``seed_dir`` does not exist (e.g.
    during local development without a committed seed snapshot) — callers then
    fall back to an empty but writable storage dir.
    """
    if storage_dir is None:
        return
    try:
        storage_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        # storage_dir pointing at a read-only location or full /tmp: leave as-is.
        return

    marker = storage_dir / _SEED_MARKER
    if marker.exists():
        return  # Already seeded on this instance.

    if seed_dir is None or not seed_dir.exists():
        # No seed available — accept the empty dir (matches prior mkdir behaviour).
        try:
            marker.touch()
        except OSError:
            pass
        return

    try:
        _copy_tree(seed_dir, storage_dir)
        marker.touch()
    except OSError:
        # Copy failed (e.g. disk full). Don't raise — app should still boot.
        # On the next request we'll retry the copy because the marker is absent.
        pass
