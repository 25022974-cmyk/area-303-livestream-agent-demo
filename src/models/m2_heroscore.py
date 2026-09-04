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

"""Module 2 — Hero Score Multi-Factor Ranking per Product Line."""

import datetime
import math
from typing import Any, Dict, List, Optional

from ._helpers import norm, to_float, ts_to_dt
from .loader import is_gift_product

W_MS = 0.2
W_RC = 0.2
W_RATING = 0.2
W_HEADROOM = 0.2
W_FRESHNESS = 0.2

HEADROOM_CAP = 0.36
FRESHNESS_LAMBDA_DAYS = 30.0


def calculate_freshness(ctime_epoch: Any, now: datetime.datetime) -> float:
    """Calculates freshness score exp(-delta_days / 30)."""
    dt = ts_to_dt(ctime_epoch)
    if dt is None:
        return 0.0
    delta_days = max(0, (now - dt).days)
    return math.exp(-delta_days / FRESHNESS_LAMBDA_DAYS)


def calculate_hero_scores(
    data_pool: List[Dict[str, Any]], now: Optional[datetime.datetime] = None
) -> List[Dict[str, Any]]:
    """
    Computes normalized Hero Score per product line for all SKUs.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    # Extract raw sub-scores
    raw_items: List[Dict[str, Any]] = []
    for r in data_pool:
        disc = to_float(r.get("discount_percent"))
        raw_items.append({
            "item_id": str(r["item_id"]),
            "name": str(r.get("product_name", "")),
            "line": str(r.get("line") or "Other"),
            "price": to_float(r.get("price")),
            "price_original": to_float(r.get("price_original")),
            "discount_percent": disc,
            "raw_ms": to_float(r.get("monthly_sold_value")),
            "raw_rc": to_float(r.get("rating_count")),
            "raw_rating": to_float(r.get("rating"), 4.5),
            "raw_headroom": max(0.0, HEADROOM_CAP - disc / 100.0),
            "raw_freshness": calculate_freshness(r.get("ctime"), now),
            "image_url": str(r.get("image_url", "")),
        })

    # Group by line for intra-line min-max normalization
    by_line: Dict[str, List[Dict[str, Any]]] = {}
    for it in raw_items:
        by_line.setdefault(it["line"], []).append(it)

    scored_items: List[Dict[str, Any]] = []
    for line, items in by_line.items():
        ms_norm = norm([it["raw_ms"] for it in items])
        rc_norm = norm([it["raw_rc"] for it in items])
        rating_norm = norm([it["raw_rating"] for it in items])
        headroom_norm = norm([it["raw_headroom"] for it in items])
        freshness_norm = norm([it["raw_freshness"] for it in items])

        for idx, it in enumerate(items):
            score = (
                W_MS * ms_norm[idx]
                + W_RC * rc_norm[idx]
                + W_RATING * rating_norm[idx]
                + W_HEADROOM * headroom_norm[idx]
                + W_FRESHNESS * freshness_norm[idx]
            )
            # Hàng quà tặng không bán được giảm điểm để thấp hơn các SKU bán thông thường
            if it["line"] == "Quà Tặng" or is_gift_product(it["name"]):
                score = score * 0.05

            scored_items.append({
                "item_id": it["item_id"],
                "name": it["name"],
                "line": it["line"],
                "price": it["price"],
                "price_original": it["price_original"],
                "discount_percent": it["discount_percent"],
                "hero_score": round(score, 4),
                "components": {
                    "ms": round(ms_norm[idx], 3),
                    "rc": round(rc_norm[idx], 3),
                    "rating": round(rating_norm[idx], 3),
                    "headroom": round(headroom_norm[idx], 3),
                    "freshness": round(freshness_norm[idx], 3),
                },
                "raw_values": {
                    "monthly_sold": it["raw_ms"],
                    "rating_count": it["raw_rc"],
                    "rating": it["raw_rating"],
                    "headroom": round(it["raw_headroom"], 3),
                    "freshness": round(it["raw_freshness"], 3),
                },
                "image_url": it["image_url"],
            })

    # Sort descending by hero_score and assign rank
    scored_items.sort(key=lambda x: x["hero_score"], reverse=True)
    for rank, it in enumerate(scored_items, 1):
        it["rank"] = rank

    return scored_items
