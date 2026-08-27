"""Per-shop state isolation cho AREA_303 server.

Layout (trong SHOPS_DIR):
    shops/{shop_id}/
      data/products_{ts}.csv
      learning_state.json
      config.json
      recommendations/recommendation_{ts}.json

JSON files keyed by shop_id (đơn giản, đủ cho 1 shop = 1 CSV ~287 rows).
Tất cả hàm validate shop_id (chỉ số) để anti path traversal.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..config import SHOPS_DIR

_SHOP_ID_RE = re.compile(r"^\d+$")


def _validate_shop_id(shop_id: str) -> str:
    if not shop_id or not _SHOP_ID_RE.match(shop_id):
        raise ValueError(f"shop_id phải là chuỗi số (got {shop_id!r})")
    return shop_id


def shop_dir(shop_id: str) -> Path:
    _validate_shop_id(shop_id)
    d = SHOPS_DIR / shop_id
    (d / "data").mkdir(parents=True, exist_ok=True)
    (d / "recommendations").mkdir(parents=True, exist_ok=True)
    return d


def save_csv(shop_id: str, data: bytes) -> Path:
    d = shop_dir(shop_id)
    ts = _utc_ts()
    path = d / "data" / f"products_{ts}.csv"
    path.write_bytes(data)
    return path


def save_config(shop_id: str, config: dict[str, Any]) -> Path:
    d = shop_dir(shop_id)
    path = d / "config.json"
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load_config(shop_id: str) -> Optional[dict[str, Any]]:
    path = shop_dir(shop_id) / "config.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_recommendation(shop_id: str, recommendation: dict[str, Any]) -> Path:
    d = shop_dir(shop_id)
    ts = _utc_ts()
    path = d / "recommendations" / f"recommendation_{ts}.json"
    path.write_text(json.dumps(recommendation, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def list_sessions(shop_id: str) -> list[str]:
    rec_dir = shop_dir(shop_id) / "recommendations"
    files = sorted(rec_dir.glob("recommendation_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files]


def load_learning_state(shop_id: str) -> Optional[dict[str, Any]]:
    path = shop_dir(shop_id) / "learning_state.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def save_learning_state(shop_id: str, state: dict[str, Any]) -> Path:
    path = shop_dir(shop_id) / "learning_state.json"
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _utc_ts() -> str:
    """Timestamp UTC dạng yyyymmddHHMMSS — an toàn cho tên file (không dùng Date.now() nhập nhằng)."""
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
