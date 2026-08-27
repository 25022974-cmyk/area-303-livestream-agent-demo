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

"""Data loader and preprocessing module using Pandas for Shopee datasets."""

import io
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from ._helpers import to_float, to_int

REQUIRED_COLUMNS = [
    "shop_id",
    "item_id",
    "product_name",
    "price",
    "price_original",
    "discount_percent",
    "monthly_sold_value",
    "rating_count",
    "rating",
    "ctime",
    "voucher_discount",
    "voucher_min_spend",
    "voucher_start_time",
    "voucher_end_time",
    "catid",
    "date",
]

_LINE_PATTERNS = [
    (re.compile(r"\b(zoo|em\s*b[eé]|kid|tr[eẻ]\s*em)\b", re.IGNORECASE), "Zoo"),
    (re.compile(r"\b(quasure|sure|ti[eể]u\s*[dđ][uư][oờ]ng)\b", re.IGNORECASE), "Quasure"),
    (re.compile(r"\b(gooka|b[aá]nh\s*quy|wafer)\b", re.IGNORECASE), "Gooka"),
    (re.compile(r"\b(sumika|sumi|k[eẹ]o\s*d[eẻ]o)\b", re.IGNORECASE), "Sumika"),
    (re.compile(r"\b(hura)\b", re.IGNORECASE), "Hura"),
]


class LoaderError(Exception):
    """Exception raised for errors during dataset loading and validation."""

    def __init__(self, message: str, missing_columns: Optional[List[str]] = None):
        super().__init__(message)
        self.missing_columns = missing_columns or []


def assign_product_line(product_name: str, catid: Any = None, total_distinct_catids: int = 1) -> str:
    """Categorizes product into a product line using taxonomy or keyword heuristics."""
    if total_distinct_catids > 1 and catid not in (None, "", "None", "nan"):
        return f"Cat_{catid}"

    name = str(product_name or "")
    for pattern, line_name in _LINE_PATTERNS:
        if pattern.search(name):
            return line_name
    return "Other"


def load_products_dataframe(source: Union[str, Path, bytes, io.StringIO, io.BytesIO]) -> pd.DataFrame:
    """Loads raw Shopee products data into a cleaned Pandas DataFrame."""
    try:
        if isinstance(source, (str, Path)) and (isinstance(source, Path) or Path(source).exists()):
            df = pd.read_csv(source, dtype=str)
        elif isinstance(source, bytes):
            df = pd.read_csv(io.BytesIO(source), dtype=str)
        elif isinstance(source, io.StringIO):
            df = pd.read_csv(source, dtype=str)
        elif isinstance(source, io.BytesIO):
            df = pd.read_csv(source, dtype=str)
        elif isinstance(source, str):
            df = pd.read_csv(io.StringIO(source), dtype=str)
        else:
            raise LoaderError("Unsupported source format.")
    except Exception as exc:
        raise LoaderError(f"Failed to parse CSV: {exc}") from exc

    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise LoaderError(f"Missing required columns in CSV: {missing}", missing_columns=missing)

    # Clean and standardize types
    df = df.dropna(subset=["item_id"]).copy()
    df["item_id"] = df["item_id"].astype(str).str.strip()
    df["shop_id"] = df["shop_id"].astype(str).str.strip()
    df["product_name"] = df["product_name"].fillna("").astype(str)

    numeric_cols = [
        "price",
        "price_original",
        "discount_percent",
        "monthly_sold_value",
        "rating_count",
        "rating",
        "ctime",
        "voucher_discount",
        "voucher_min_spend",
        "voucher_start_time",
        "voucher_end_time",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    # Line assignment
    distinct_catids = df["catid"].dropna().replace("", None).nunique()
    df["line"] = df.apply(
        lambda r: assign_product_line(r["product_name"], r.get("catid"), distinct_catids),
        axis=1,
    )

    return df


def load_csv_data(
    source: Union[str, Path, bytes, io.StringIO, io.BytesIO]
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Parses CSV data into (data_pool, snapshots).
    - snapshots: list of all raw snapshot records across time
    - data_pool: deduplicated list of unique SKUs for the shop
    """
    df = load_products_dataframe(source)
    snapshots = df.to_dict(orient="records")

    # Dedup by item_id (keeping row with max monthly_sold_value)
    df_sorted = df.sort_values(by=["monthly_sold_value", "price"], ascending=[False, False])
    df_dedup = df_sorted.drop_duplicates(subset=["item_id"], keep="first")
    data_pool = df_dedup.to_dict(orient="records")

    return data_pool, snapshots


def build_observations_from_snapshots(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Builds cross-time observation pairs for price elasticity estimation."""
    by_item: Dict[str, List[Dict[str, Any]]] = {}
    for r in snapshots:
        iid = str(r.get("item_id", ""))
        if not iid:
            continue
        by_item.setdefault(iid, []).append(r)

    observations: List[Dict[str, Any]] = []
    for iid, rows in by_item.items():
        if len(rows) < 2:
            continue
        # Sort chronologically by date if available
        rows_sorted = sorted(rows, key=lambda x: str(x.get("date", "")))
        for i in range(1, len(rows_sorted)):
            prev = rows_sorted[i - 1]
            curr = rows_sorted[i]

            p_prev = to_float(prev.get("price"))
            p_curr = to_float(curr.get("price"))
            s_prev = to_float(prev.get("monthly_sold_value"))
            s_curr = to_float(curr.get("monthly_sold_value"))

            if p_prev <= 0 or p_curr <= 0 or p_prev == p_curr:
                continue

            delta_log_p = math.log(p_curr) - math.log(p_prev)
            delta_log_s = math.log1p(s_curr) - math.log1p(s_prev)

            observations.append({
                "item_id": iid,
                "shop_id": str(curr.get("shop_id", "")),
                "line": str(curr.get("line", "Other")),
                "delta_log_p": delta_log_p,
                "delta_log_s": delta_log_s,
                "price": p_curr,
                "monthly_sold_value": s_curr,
            })

    return observations
