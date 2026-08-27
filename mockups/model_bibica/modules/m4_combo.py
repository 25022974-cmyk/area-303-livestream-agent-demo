"""Module 4 — Ghép combo (hero + SKU bán chậm + quà tặng).

Contract theo DELIVERABLE_SPEC.md §B/Module 4.

2 kiểu song song:
  - bundled          : hero + SKU bán chậm cùng line, giảm nhẹ trên tổng.
  - gift_with_purchase: mua hero tặng kèm SKU "QUÀ TẶNG KHÔNG BÁN" (gift_cost=0 proxy).

Quy tắc:
  - group_by_line: chỉ ghép cùng line (Zoo+Zoo, Gooka+Gooka... không ghép Zoo ↔ Quasure).
  - pick_slow_sku: SKU freshness thấp nhất (tồn kho lâu) + monthly_sold thấp.
  - parse_existing_combos(name): regex "Combo <n> ...".

gift_cost đi chung ngân sách voucher ở Module 5 — nhưng thiếu cost data thật -> 0 proxy
(spec cho phép; Phase 2 có giá vốn thì thay).

Stdlib thuần.
"""
import datetime
import re
from typing import Any, Dict, List, Optional

from ._helpers import to_float, ts_to_dt

_COMBO_RE = re.compile(r"Combo\s*(\d+)\s*(.+)", re.IGNORECASE)
_GIFT_RE = re.compile(r"QUÀ?\s*TẶNG\s*KHÔNG\s*BÁN", re.IGNORECASE)
_GIFT_RE_ASCII = re.compile(r"QUA\s*TANG\s*KHONG\s*BAN", re.IGNORECASE)

BUNDLE_DISCOUNT_PCT = 15.0   # giảm nhẹ trên tổng (spec Bibica: bundle ~15%)


def parse_existing_combos(name: str) -> Optional[Dict[str, Any]]:
    """Trích combo có sẵn từ tên 'Combo 3 Kẹo Tứ Quý...'. Trả None nếu không phải combo."""
    if not name:
        return None
    m = _COMBO_RE.search(name)
    if not m:
        return None
    try:
        count = int(m.group(1))
    except ValueError:
        return None
    return {"count": count, "rest": m.group(2).strip()}


def _is_gift(name: str) -> bool:
    if not name:
        return False
    return bool(_GIFT_RE.search(name) or _GIFT_RE_ASCII.search(name))


def _freshness(ctime_epoch: Any, now: datetime.datetime) -> float:
    import math
    dt = ts_to_dt(ctime_epoch)
    if dt is None:
        return 0.0
    delta = max(0, (now - dt).days)
    return math.exp(-delta / 30.0)


def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def pick_slow_sku(candidates: List[Dict[str, Any]],
                  now: datetime.datetime) -> Optional[Dict[str, Any]]:
    """SKU bán chậm + freshness thấp nhất (tồn kho lâu nhất) ưu tiên trước."""
    if not candidates:
        return None
    scored = []
    for c in candidates:
        ms = to_float(c.get("monthly_sold_value"))
        fr = _freshness(c.get("ctime"), now)
        scored.append((ms, fr, c))
    # sort: ms asc, rồi freshness asc (ms=0 + freshness thấp = chậm nhất)
    scored.sort(key=lambda t: (t[0], t[1]))
    return scored[0][2]


def combo(data_pool: List[Dict[str, Any]],
          hero_list: List[Dict[str, Any]],
          now_ts: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
    """Trả list combo. Mỗi hero top -> 1 combo (bundled + gift nếu có).

    hero_list: output của Module 2 (đã sort, gán rank, có line).
    """
    now = now_ts or _utcnow()
    if not data_pool or not hero_list:
        return []

    # Tách gift SKUs (QUÀ TẶNG KHÔNG BÁN) khỏi pool slow.
    normal_pool = []
    gifts_by_line: Dict[str, List[Dict[str, Any]]] = {}
    for r in data_pool:
        name = r.get("product_name", "")
        if _is_gift(name):
            gifts_by_line.setdefault(str(r.get("line") or "Other"), []).append(r)
        else:
            normal_pool.append(r)

    results = []
    seen_hero = set()
    # Giới hạn top hero để không spam combo (top 8 hoặc toàn bộ nếu ít).
    top_heroes = hero_list[:8] if len(hero_list) > 8 else hero_list
    item_by_id = {r["item_id"]: r for r in data_pool}

    for h in top_heroes:
        hero_id = h["item_id"]
        if hero_id in seen_hero:
            continue
        seen_hero.add(hero_id)
        hero_row = item_by_id.get(hero_id)
        if not hero_row:
            continue
        line = h.get("line") or str(hero_row.get("line") or "Other")
        hero_name = h.get("name", hero_row.get("product_name", ""))

        # Slow candidate cùng line, không trùng hero, không phải gift.
        slow_cands = [
            r for r in normal_pool
            if r["item_id"] != hero_id and str(r.get("line") or "Other") == line
        ]
        slow = pick_slow_sku(slow_cands, now)

        # Gift cùng line nếu có.
        gift = gifts_by_line.get(line, [None])[0] if gifts_by_line.get(line) else None

        if slow is None and gift is None:
            continue  # không có gì ghép

        slow_id = slow["item_id"] if slow else None
        slow_name = slow.get("product_name", "") if slow else ""
        slow_fr = _freshness(slow.get("ctime"), now) if slow else None

        hero_price = to_float(hero_row.get("price"))
        slow_price = to_float(slow.get("price")) if slow else 0.0
        bundle_price = round(hero_price + slow_price)
        bundle_discount_pct = round(
            BUNDLE_DISCOUNT_PCT + max(0, (1 - (slow_fr or 1.0)) * 10), 1  # slow càng cũ giảm thêm
        ) if slow else 0.0

        # Kiểu: có gift + slow? -> gift_with_purchase (mua hero tặng quà);
        #       chỉ slow           -> bundled.
        if gift is not None and slow is not None:
            ctype = "gift_with_purchase"
        elif gift is not None:
            ctype = "gift_with_purchase"
        else:
            ctype = "bundled"

        results.append({
            "combo_id": f"c{len(results)+1}",
            "type": ctype,
            "hero_item_id": hero_id,
            "hero_name": hero_name,
            "slow_item_id": slow_id,
            "slow_name": slow_name,
            "slow_freshness": round(slow_fr, 4) if slow_fr is not None else None,
            "gift_item_id": gift["item_id"] if gift else None,
            "gift_name": gift.get("product_name", "") if gift else None,
            "bundle_price": bundle_price,
            "bundle_discount_pct": bundle_discount_pct,
            "gift_cost": 0,   # proxy: thiếu cost data (spec cho phép 0)
        })

    return results


# =====================================================================
# SELF-TEST
# =====================================================================
if __name__ == "__main__":
    import datetime as _dt
    now = _dt.datetime(2026, 8, 26, tzinfo=_dt.timezone.utc)
    pool = [
        {"item_id": "h1", "product_name": "Kẹo Zoo Hero", "line": "Zoo",
         "price": 30000, "monthly_sold_value": 500, "ctime": str(int(now.timestamp()))},
        {"item_id": "s1", "product_name": "Kẹo Zoo Chậm", "line": "Zoo",
         "price": 10000, "monthly_sold_value": 2,
         "ctime": str(int(now.timestamp()) - 120 * 86400)},   # 120 ngày -> freshness thấp
        {"item_id": "g1", "product_name": "QUÀ TẶNG KHÔNG BÁN Zoo", "line": "Zoo",
         "price": 0, "monthly_sold_value": 0, "ctime": str(int(now.timestamp()))},
        {"item_id": "x1", "product_name": "Sữa Quasure", "line": "Quasure",
         "price": 50000, "monthly_sold_value": 30, "ctime": str(int(now.timestamp()))},
    ]
    # parse_existing_combos
    print("parse 'Combo 3 Kẹo Tứ Quý':", parse_existing_combos("Combo 3 Kẹo Tứ Quý Bibica"))
    assert parse_existing_combos("Combo 3 Kẹo")["count"] == 3
    assert parse_existing_combos("Kẹo thường") is None

    heros = [
        {"item_id": "h1", "name": "Kẹo Zoo Hero", "line": "Zoo", "hero_score": 0.9, "rank": 1},
        {"item_id": "x1", "name": "Sữa Quasure", "line": "Quasure", "hero_score": 0.4, "rank": 2},
    ]
    out = combo(pool, heros, now_ts=now)
    print("[M4 test] combos:")
    for c in out:
        print(" ", c["combo_id"], c["type"], "hero=", c["hero_item_id"], "slow=", c["slow_item_id"], "gift=", c["gift_item_id"], "disc=", c["bundle_discount_pct"])
    # h1 (Zoo) -> slow s1 (Zoo, freshness thấp) + gift g1 (Zoo) -> gift_with_purchase
    z = [c for c in out if c["hero_item_id"] == "h1"][0]
    assert z["type"] == "gift_with_purchase", "có gift -> gift_with_purchase"
    assert z["slow_item_id"] == "s1", "slow cùng line Zoo"
    assert z["gift_item_id"] == "g1", "gift Zoo ghép"
    assert z["gift_cost"] == 0
    # x1 (Quasure) -> không slow cùng line -> skip (chỉ gift? quasure không gift)
    print("✓ m4_combo OK (gift_with_purchase + slow cùng line, không ghép cross-line)")
