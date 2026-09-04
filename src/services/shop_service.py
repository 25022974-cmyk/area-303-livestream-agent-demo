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

"""Shop service managing multi-shop data, isolation, configurations, and datasets.

The service is storage-backend agnostic: per-shop writable state (uploaded CSVs,
``config.json``, ``learning_state.json``) is delegated to a ``StorageBackend``
chosen by env (filesystem locally, Vercel Blob on serverless). Read-only
benchmark data under ``DATA_DIR`` is still read straight from disk. Routes and
callers see the same public API regardless of backend.
"""

import datetime
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from ..config import (
    DATA_DIR,
    DEFAULT_ALPHA,
    DEFAULT_BETA,
    DEFAULT_BUDGET_VOUCHER_MONTH,
    DEFAULT_SHOP_ID,
    DEFAULT_USE_DP_KNAPSACK,
    PRELOADED_SHOPS,
    STORAGE_DIR,
)
from ..models.learner import default_learning_state
from ..models.loader import build_observations_from_snapshots, load_csv_data
from .storage import get_storage_backend

_SHOP_ID_RE = re.compile(r"^\d+$")


class ShopService:
    """Service handling multi-tenant shop datasets and per-shop storage isolation."""

    def __init__(self):
        self.storage_dir = STORAGE_DIR
        self.data_dir = DATA_DIR
        self.backend = get_storage_backend()

    def validate_shop_id(self, shop_id: str) -> str:
        """Validates numeric shop ID to prevent path traversal."""
        sid = str(shop_id or "").strip()
        if not sid or not _SHOP_ID_RE.match(sid):
            raise ValueError(f"Invalid shop_id: '{shop_id}'. Must be numeric string.")
        return sid

    # Note: legacy per-shop filesystem dir kept for LocalFilesystemBackend and
    # for ad-hoc callers/tests that may still expect a directory path. On the
    # Blob backend this directory is only used as a scratch /tmp cache.
    def get_shop_dir(self, shop_id: str) -> Path:
        """Returns local (filesystem) directory for a specific shop.

        On the Blob backend this is a scratch dir under /tmp used only as a
        download cache for pandas; it is NOT the source of truth.
        """
        sid = self.validate_shop_id(shop_id)
        if self.backend.name == "local":
            d = self.storage_dir / sid
        else:
            d = Path(tempfile.gettempdir()) / "area303_shops" / sid
        (d / "data").mkdir(parents=True, exist_ok=True)
        (d / "playbooks").mkdir(parents=True, exist_ok=True)
        return d

    def list_available_shops(self) -> List[Dict[str, Any]]:
        """Lists all preloaded benchmark shops and any custom uploaded shops."""
        shops: List[Dict[str, Any]] = []

        # 1. Preloaded shops from DATA_DIR
        for sid, meta in PRELOADED_SHOPS.items():
            shop_info_file = self.data_dir / "dataset=shop_info" / f"shop_id={sid}" / "shop_info.csv"
            info = dict(meta)

            if shop_info_file.exists():
                try:
                    df_info = pd.read_csv(shop_info_file)
                    if not df_info.empty:
                        row = df_info.iloc[0].to_dict()
                        info["rating_star"] = float(row.get("rating_star", 4.9))
                        info["follower_count"] = int(float(row.get("follower_count", 0)))
                        info["item_count"] = int(float(row.get("item_count", 0)))
                        info["response_rate"] = float(row.get("response_rate", 98))
                except Exception:
                    pass

            shops.append(info)

        # 2. Check backend for additional user-uploaded custom shops
        try:
            custom_ids = self.backend.list_shops()
        except Exception:
            custom_ids = []
        for sid in custom_ids:
            if sid in PRELOADED_SHOPS:
                continue
            if not _SHOP_ID_RE.match(sid):
                continue
            cfg = self.load_shop_config(sid)
            shops.append({
                "shop_id": sid,
                "shop_name": cfg.get("shop_name", f"Custom Shop #{sid}"),
                "username": f"custom_shop_{sid}",
                "is_default": False,
                "category": "Custom Uploaded Shop",
                "badge": "Custom",
                "brand_color": "#475569",
                "item_count": cfg.get("item_count", 0),
            })

        return shops

    def get_shop_meta(self, shop_id: str) -> Dict[str, Any]:
        """Gets metadata for a specific shop."""
        sid = self.validate_shop_id(shop_id)
        if sid in PRELOADED_SHOPS:
            return PRELOADED_SHOPS[sid]
        cfg = self.load_shop_config(sid)
        return {
            "shop_id": sid,
            "shop_name": cfg.get("shop_name", f"Shop #{sid}"),
            "username": f"shop_{sid}",
            "is_default": False,
            "category": "Uploaded Shop",
            "badge": "Shop",
            "brand_color": "#1e293b",
        }

    def get_shop_data_path(self, shop_id: str) -> Optional[Path]:
        """Locates the latest products CSV for a shop as a local Path.

        Returns a Path that ``load_csv_data``/pandas can read directly. The
        returned path is either:
          - the on-disk uploaded file (local backend), or
          - a benchmark CSV shipped in the repo (DATA_DIR), or
          - a /tmp scratch file downloaded from the Blob backend (cached for
            the lifetime of the instance).
        """
        sid = self.validate_shop_id(shop_id)

        # Uploaded files first (via backend)
        csvs = []
        try:
            csvs = self.backend.list_csvs(sid)
        except Exception:
            csvs = []
        if csvs:
            newest_name, _mtime = csvs[0]
            if self.backend.name == "local":
                # Local backend stores under STORAGE_DIR; build the path directly
                return (self.storage_dir / sid / newest_name)
            # Blob backend: download (with a /tmp cache) so pandas can read it
            return self._materialize_csv_locally(sid, newest_name)

        # Preloaded benchmark data (read-only, on disk)
        preloaded_path = self.data_dir / "dataset=products" / f"shop_id={sid}" / "products.csv"
        if preloaded_path.exists():
            return preloaded_path

        return None

    def _materialize_csv_locally(self, shop_id: str, name: str) -> Optional[Path]:
        """Download a CSV from the backend into a /tmp cache path and return it."""
        local_dir = Path(tempfile.gettempdir()) / "area303_shops" / shop_id / "data"
        local_dir.mkdir(parents=True, exist_ok=True)
        # name looks like "data/products_<ts>.csv" — flatten to a filename
        filename = name.replace("/", "_")
        local_path = local_dir / filename
        # cache hit: skip the download
        if local_path.exists() and local_path.stat().st_size > 0:
            # sanity check we can still re-fetch: if backend has a newer file this
            # still works because callers pass the newest name we just selected.
            return local_path
        raw = self.backend.read_bytes(shop_id, name)
        if raw is None:
            return None
        local_path.write_bytes(raw)
        return local_path

    def save_uploaded_csv(self, shop_id: str, raw_bytes: bytes, shop_name: Optional[str] = None) -> str:
        """Saves an uploaded CSV via the storage backend.

        Returns the relative name under the shop dir (the backend key's tail),
        so callers/tests can reference it without knowing the backend.
        """
        sid = self.validate_shop_id(shop_id)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
        name = f"data/products_{ts}.csv"
        self.backend.write_bytes(sid, name, raw_bytes, content_type="text/csv")

        # Update shop configuration
        cfg = self.load_shop_config(sid)
        if shop_name:
            cfg["shop_name"] = shop_name
        cfg["latest_csv"] = name
        self.save_shop_config(sid, cfg)

        return name

    def load_shop_config(self, shop_id: str) -> Dict[str, Any]:
        """Loads shop configuration from config.json."""
        sid = self.validate_shop_id(shop_id)
        raw = self.backend.read_text(sid, "config.json")
        if raw is not None:
            try:
                return json.loads(raw)
            except Exception:
                pass

        meta = self.get_shop_meta(sid)
        return {
            "shop_id": sid,
            "shop_name": meta.get("shop_name", f"Shop {sid}"),
            "budget_voucher_month": DEFAULT_BUDGET_VOUCHER_MONTH,
            "alpha": DEFAULT_ALPHA,
            "beta": DEFAULT_BETA,
            "use_dp_knapsack": DEFAULT_USE_DP_KNAPSACK,
        }

    def save_shop_config(self, shop_id: str, config: Dict[str, Any]) -> None:
        """Saves shop configuration to config.json."""
        sid = self.validate_shop_id(shop_id)
        self.backend.write_text(sid, "config.json",
                                json.dumps(config, ensure_ascii=False, indent=2))

    def load_learning_state(self, shop_id: str) -> Dict[str, Any]:
        """Loads persistent learning state or returns default."""
        sid = self.validate_shop_id(shop_id)
        raw = self.backend.read_text(sid, "learning_state.json")
        if raw is not None:
            try:
                return json.loads(raw)
            except Exception:
                pass
        return default_learning_state()

    def save_learning_state(self, shop_id: str, state: Dict[str, Any]) -> None:
        """Saves updated learning state."""
        sid = self.validate_shop_id(shop_id)
        self.backend.write_text(sid, "learning_state.json",
                                json.dumps(state, ensure_ascii=False, indent=2))

    def load_shop_data(
        self, shop_id: str
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Loads and parses shop data into: (data_pool, snapshots, observations).
        """
        csv_path = self.get_shop_data_path(shop_id)
        if not csv_path or not (hasattr(csv_path, "exists") and csv_path.exists()):
            raise FileNotFoundError(f"No products CSV found for shop_id {shop_id}")

        data_pool, snapshots = load_csv_data(csv_path)
        observations = build_observations_from_snapshots(snapshots)
        return data_pool, snapshots, observations

    def load_all_industry_snapshots(self) -> List[Dict[str, Any]]:
        """Loads all benchmark shop snapshots across competitors for industry-wide signals."""
        all_snapshots: List[Dict[str, Any]] = []
        prod_dir = self.data_dir / "dataset=products"

        if prod_dir.exists():
            for shop_folder in prod_dir.glob("shop_id=*"):
                csv_file = shop_folder / "products.csv"
                if csv_file.exists():
                    try:
                        _, snaps = load_csv_data(csv_file)
                        all_snapshots.extend(snaps)
                    except Exception:
                        pass

        return all_snapshots


shop_service = ShopService()
