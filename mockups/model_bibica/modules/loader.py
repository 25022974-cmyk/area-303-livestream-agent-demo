"""Loader AREA_303 — parse CSV sản phẩm Shopee thành (data_pool, snapshots).

Tổng quát hóa từ `bibica_playbook.load_products` + `_load_raw_products`:
- Không hard-code shop_id hay đường dẫn. Nhận đường dẫn file hoặc bytes/in-memory.
- Validate cột bắt buộc (schema 40 cột Shopee).
- Dedup theo item_id (giữ row có monthly_sold_value lớn nhất) cho `data_pool`.
- Giữ `snapshots` = toàn bộ rows để build_observations cross-time cho M1.
- Gán `line` (line_or_catid) generic:
    * 1 catid duy nhất  -> synthetic line từ keyword tên (Zoo/Quasure/Gooka/Sumika/Other)
    * nhiều catid      -> line = str(catid) thật
- Trả (data_pool, snapshots). Mỗi row dict có đủ field cho 5 module.

Stdlib thuần (csv, io, re, collections).
"""
import csv
import io
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Union

from ._helpers import to_float

# Cột bắt buộc trong products.csv (schema 40 cột Shopee VN).
REQUIRED_COLUMNS = [
    "shop_id", "item_id", "product_name", "price", "price_original",
    "discount_percent", "monthly_sold_value", "rating_count", "rating",
    "ctime", "voucher_discount", "voucher_min_spend", "voucher_start_time",
    "voucher_end_time", "catid", "date",
]


class LoaderError(Exception):
    """Lỗi khi load/validate CSV."""

    def __init__(self, message: str, missing_columns: List[str] = None):
        super().__init__(message)
        self.missing_columns = missing_columns or []


# Keyword -> synthetic line (chỉ dùng khi shop có 1 catid, như Bibica).
_LINE_KEYWORDS = [
    ("zoo", "Zoo"),
    ("em bé", "Zoo"),
    ("em be", "Zoo"),
    ("kid", "Zoo"),
    ("trẻ em", "Zoo"),
    ("tre em", "Zoo"),
    ("quasure", "Quasure"),
    ("sure", "Quasure"),
    ("gooka", "Gooka"),
    ("bánh", "Gooka"),
    ("banh", "Gooka"),
    ("sumika", "Sumika"),
    ("sumi", "Sumika"),
]


def _parse_source(source: Union[str, bytes, io.StringIO, io.BytesIO]) -> io.StringIO:
    """Chuyển nhiều loại input về StringIO chứa text CSV."""
    if isinstance(source, str):
        # Heuristic: chuỗi chứa newline hoặc có dấu phẩy -> nội dung CSV; ngược lại -> đường dẫn file.
        if "\n" in source or "," in source:
            return io.StringIO(source)
        with open(source, encoding="utf-8-sig") as f:
            return io.StringIO(f.read())
    if isinstance(source, bytes):
        return io.StringIO(source.decode("utf-8-sig"))
    if isinstance(source, io.BytesIO):
        return io.StringIO(source.read().decode("utf-8-sig"))
    return source  # đã là StringIO


def _synthetic_line(name: str) -> str:
    """Gán synthetic line từ keyword trong tên sản phẩm (lowercase)."""
    nm = (name or "").lower()
    for kw, line in _LINE_KEYWORDS:
        if kw in nm:
            return line
    return "Other"


def assign_line_or_catid(rows: List[Dict[str, Any]]) -> str:
    """Mutate rows: thêm field 'line'.

    Trả kiểu gán: "synthetic" (1 catid -> line từ keyword) hoặc "real_catid" (nhiều catid -> catid thật).
    """
    catids = set()
    for r in rows:
        c = r.get("catid")
        if c not in (None, "", "None"):
            catids.add(str(c))
    if len(catids) <= 1 and rows:
        # 1 catid -> synthetic line từ tên (tránh nhiễu ngành như spec Bibica).
        for r in rows:
            r["line"] = _synthetic_line(r.get("product_name", ""))
        return "synthetic" if len(catids) == 1 else "synthetic_none"  # 0 catid vẫn synthetic nhưng "guessing"
    # nhiều catid -> line = catid thật
    for r in rows:
        r["line"] = str(r.get("catid"))
    return "real_catid"


def load_csv(source: Union[str, bytes, io.StringIO, io.BytesIO]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load products.csv -> (data_pool, snapshots).

    source: đường dẫn str | bytes CSV | StringIO/BytesIO.
    data_pool: 1 SKU/item_id (dedup, giữ row monthly_sold_value lớn nhất).
    snapshots: toàn bộ rows (per ngày) để build_observations cho M1.
    Raise LoaderError nếu thiếu cột bắt buộc.
    """
    sio = _parse_source(source)
    reader = csv.DictReader(sio)
    if reader.fieldnames is None:
        raise LoaderError("CSV rỗng hoặc không đọc được header.")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise LoaderError(f"CSV thiếu cột bắt buộc: {missing}", missing_columns=missing)

    snapshots: List[Dict[str, Any]] = []
    for r in reader:
        iid = r.get("item_id")
        if not iid or iid in ("", "None"):
            continue
        snapshots.append(r)

    if not snapshots:
        raise LoaderError("CSV không có row nào hợp lệ (thiếu item_id).")

    # Gán line (synthetic / real_catid) — mutate snapshots.
    assign_line_or_catid(snapshots)

    # Dedup theo item_id: giữ row có monthly_sold_value lớn nhất.
    best: Dict[str, Dict[str, Any]] = {}
    for r in snapshots:
        iid = r["item_id"]
        ms = to_float(r.get("monthly_sold_value"))
        if iid not in best or ms > to_float(best[iid].get("monthly_sold_value")):
            best[iid] = r
    data_pool = list(best.values())
    return data_pool, snapshots
