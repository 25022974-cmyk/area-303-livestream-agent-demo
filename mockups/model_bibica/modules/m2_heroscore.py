"""Module 2 — Hero Score (xếp hạng SKU lên live).

Contract theo DELIVERABLE_SPEC.md §B/Module 2.

  hero_score = 0.30·ms + 0.25·rc + 0.15·rating + 0.15·headroom + 0.15·freshness
  freshness  = exp(-Δngày/30), Δngày từ ctime

Quan trọng: **chuẩn hoá min-max theo từng line** (Zoo/Quasure/Gooka/Sumika/Other)
trước khi nhân trọng số — tránh dòng Zoo (trẻ em, bán chạy) lấn át Quasure trong
mọi phiên. min==max -> 0.5 (xem `_helpers.norm`).

Stdlib thuần.
"""
import datetime
import math
from typing import Any, Dict, List, Optional

from ._helpers import norm, to_float, ts_to_dt
from .loader import is_gift_product

# Trọng số đề bài (spec E: lấy từ docx, không tự chế).
W_MS = 0.2
W_RC = 0.2
W_RATING = 0.2
W_HEADROOM = 0.2
W_FRESHNESS = 0.2

HEADROOM_CAP = 0.36          # M1 cap 36% -> headroom max(0, 0.36 - disc/100)
FRESHNESS_LAMBDA_DAYS = 30   # freshness = exp(-Δdays/30)

def _utcnow() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def _freshness(ctime_epoch: Any, now: datetime.datetime) -> float:
    """exp(-Δdagen/30). Δdagen=0 -> 1.0 (mới ra); Δdagen lớn -> ->0 (tồn kho lâu)."""
    dt = ts_to_dt(ctime_epoch)
    if dt is None:
        # Không có ctime hợp lệ -> freshness 0 (xấu nhất) để không đè SKU có data.
        return 0.0
    delta_days = max(0, (now - dt).days)
    return math.exp(-delta_days / FRESHNESS_LAMBDA_DAYS)


def _build_features(data_pool: List[Dict[str, Any]],
                    now: datetime.datetime) -> List[Dict[str, Any]]:
    """Tính 5 sub-feature thô cho mỗi SKU (chưa chuẩn hoá)."""
    feats = []
    for r in data_pool:
        disc = to_float(r.get("discount_percent"))
        feats.append({
            "item_id": r["item_id"],
            "name": r.get("product_name", ""),
            "line": str(r.get("line") or "Other"),
            "ms": to_float(r.get("monthly_sold_value")),
            "rc": to_float(r.get("rating_count")),
            "rating": to_float(r.get("rating"), 4.5),
            "headroom": max(0.0, HEADROOM_CAP - disc / 100.0),
            "freshness": _freshness(r.get("ctime"), now),
        })
    return feats


def hero_score(data_pool: List[Dict[str, Any]],
               now_ts: Optional[datetime.datetime] = None) -> List[Dict[str, Any]]:
    """Trả list SKU đã sort theo hero_score desc, gán rank.

    Chuẩn hoá min-max theo từng line trước khi nhân trọng số.
    """
    now = now_ts or _utcnow()
    feats = _build_features(data_pool, now)
    if not feats:
        return []

    # Group theo line, chuẩn hoá min-max riêng mỗi nhóm.
    by_line: Dict[str, List[int]] = {}
    for i, f in enumerate(feats):
        by_line.setdefault(f["line"], []).append(i)

    for key in ("ms", "rc", "rating", "headroom", "freshness"):
        for indices in by_line.values():
            vals = [feats[i][key] for i in indices]
            nrm = norm(vals)
            for j, idx in enumerate(indices):
                feats[idx][f"_{key}"] = nrm[j]

    results = []
    for f in feats:
        score = round(
            W_MS * f["_ms"] + W_RC * f["_rc"] + W_RATING * f["_rating"]
            + W_HEADROOM * f["_headroom"] + W_FRESHNESS * f["_freshness"], 4)
        if f["line"] == "Quà Tặng" or is_gift_product(f["name"]):
            score = round(score * 0.05, 4)
        results.append({
            "item_id": f["item_id"],
            "name": f["name"],
            "line": f["line"],
            "hero_score": score,
            "components": {
                "ms": round(f["_ms"], 4),
                "rc": round(f["_rc"], 4),
                "rating": round(f["_rating"], 4),
                "headroom": round(f["_headroom"], 4),
                "freshness": round(f["_freshness"], 4),
            },
        })

    results.sort(key=lambda x: x["hero_score"], reverse=True)
    for i, r in enumerate(results, 1):
        r["rank"] = i
    return results


# =====================================================================
# SELF-TEST
# =====================================================================
if __name__ == "__main__":
    fake = []
    # Zoo: 2 SKU ms cao; Quasure: 2 SKU ms thấp -> phải không bị Zoo lấn sạch.
    for i in range(2):
        fake.append({"item_id": f"zoo{i}", "product_name": "Kẹo Zoo", "line": "Zoo",
                     "monthly_sold_value": 500 - i, "rating_count": 100,
                     "rating": 4.8, "discount_percent": 10,
                     "ctime": str(int(_utcnow().timestamp()) - i * 86400)})
    for i in range(2):
        fake.append({"item_id": f"qua{i}", "product_name": "Sữa Quasure", "line": "Quasure",
                     "monthly_sold_value": 20 - i, "rating_count": 5,
                     "rating": 4.2, "discount_percent": 5,
                     "ctime": str(int(_utcnow().timestamp()) - 40 * 86400)})
    out = hero_score(fake)
    print("[M2 test] 4 SKU, 2 Zoo 2 Quasure:")
    for r in out:
        print(f"  rank {r['rank']} | {r['line']:8s} {r['item_id']:5s} score={r['hero_score']:.3f} fresh={r['components']['freshness']:.3f}")
    assert out[0]["line"] == "Zoo", "Zoo (ms cao) phải rank 1"
    # Quasure ít nhất 1 SKU trong top và score > 0 (không bị lấn sạch về 0 thô).
    qua_scores = [r["hero_score"] for r in out if r["line"] == "Quasure"]
    assert qua_scores and max(qua_scores) > 0.1, f"Quasure bị lấn sạch? {qua_scores}"
    print("✓ m2_heroscore OK (Quasure không bị Zoo lấn sạch nhờ chuẩn hoá theo line)")
