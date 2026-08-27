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

"""Module 4 — Smart Combo Generation & Gift-with-Purchase (GWP) Pairing."""

import datetime
import math
import re
from typing import Any, Dict, List, Optional

from ._helpers import to_float, ts_to_dt

_COMBO_RE = re.compile(r"Combo\s*(\d+)\s*(.+)", re.IGNORECASE)
_GIFT_RE = re.compile(r"QU[AÀ]?\s*T[AẶ]?NG\s*KH[OÔ]?NG\s*B[AÁ]?N", re.IGNORECASE)

DEFAULT_BUNDLE_DISCOUNT_PCT = 15.0


def is_gift_sku(name: str) -> bool:
    """Checks if an item is a promotional non-sale gift item."""
    return bool(_GIFT_RE.search(name or ""))


def generate_combos(
    data_pool: List[Dict[str, Any]],
    hero_ranked_items: List[Dict[str, Any]],
    now: Optional[datetime.datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Generates high-conversion combos by pairing high HeroScore items with slow-moving inventory
    and gift-with-purchase promotional items.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    # Separate gift items, heroes, and inventory
    gift_items: List[Dict[str, Any]] = []
    normal_items: List[Dict[str, Any]] = []

    for r in data_pool:
        name = str(r.get("product_name", ""))
        if is_gift_sku(name):
            gift_items.append(r)
        else:
            normal_items.append(r)

    # Group normal items by line
    by_line: Dict[str, List[Dict[str, Any]]] = {}
    for r in normal_items:
        line = str(r.get("line") or "Other")
        by_line.setdefault(line, []).append(r)

    # Pick top heroes (top 1-5 from M2 ranking)
    top_heroes = [h for h in hero_ranked_items if not is_gift_sku(h.get("name", ""))][:5]

    combos: List[Dict[str, Any]] = []
    combo_id = 1

    for hero in top_heroes:
        h_id = hero["item_id"]
        h_line = hero["line"]
        h_price = float(hero.get("price") or hero.get("price_original") or 0.0)

        # 1. Bundled with slow-moving item in same line
        candidates = by_line.get(h_line, [])
        slow_candidates = [
            c for c in candidates if str(c.get("item_id")) != h_id and not is_gift_sku(c.get("product_name", ""))
        ]

        if slow_candidates:
            # Sort by lowest monthly sold & oldest ctime (lowest freshness)
            slow_candidates.sort(
                key=lambda x: (
                    to_float(x.get("monthly_sold_value")),
                    to_float(x.get("ctime", 0)),
                )
            )
            slow_item = slow_candidates[0]
            s_price = to_float(slow_item.get("price")) or to_float(slow_item.get("price_original")) or 0.0

            total_orig = h_price + s_price
            bundle_price = round(total_orig * (1.0 - DEFAULT_BUNDLE_DISCOUNT_PCT / 100.0))

            combos.append({
                "combo_id": f"combo_{combo_id}",
                "combo_name": f"Combo Đột Phá: {hero['name'][:35]}... + {slow_item.get('product_name', '')[:30]}...",
                "type": "bundled",
                "type_label": "Combo Thoát Hàng Tồn",
                "line": h_line,
                "hero_item_id": h_id,
                "hero_name": hero["name"],
                "hero_price": h_price,
                "slow_item_id": str(slow_item.get("item_id")),
                "slow_name": str(slow_item.get("product_name")),
                "slow_price": s_price,
                "gift_item_id": None,
                "gift_name": None,
                "original_total_price": total_orig,
                "bundle_price": bundle_price,
                "bundle_discount_pct": DEFAULT_BUNDLE_DISCOUNT_PCT,
                "savings": total_orig - bundle_price,
                "gift_cost": 0.0,
                "reason": f"Ghép sản phẩm bán chạy nhất dòng {h_line} với SKU tồn kho lâu nhất để đẩy hàng.",
            })
            combo_id += 1

        # 2. Gift-With-Purchase (GWP) if gift items exist
        if gift_items:
            gift = gift_items[(combo_id - 1) % len(gift_items)]
            combos.append({
                "combo_id": f"combo_{combo_id}",
                "combo_name": f"Mua {hero['name'][:40]} TẶNG {gift.get('product_name', '')[:30]}",
                "type": "gift_with_purchase",
                "type_label": "Quà Tặng Tri Ân",
                "line": h_line,
                "hero_item_id": h_id,
                "hero_name": hero["name"],
                "hero_price": h_price,
                "slow_item_id": None,
                "slow_name": None,
                "slow_price": 0.0,
                "gift_item_id": str(gift.get("item_id")),
                "gift_name": str(gift.get("product_name")),
                "original_total_price": h_price,
                "bundle_price": h_price,
                "bundle_discount_pct": 0.0,
                "savings": 0.0,
                "gift_cost": 0.0,
                "reason": f"Tăng tỷ lệ chốt đơn cho Hero SKU với quà tặng độc quyền khi mua tại phiên live.",
            })
            combo_id += 1

    return combos
