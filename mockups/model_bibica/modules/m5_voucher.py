"""Module 5 — Đề xuất voucher (knapsack ngân sách).

Contract theo DELIVERABLE_SPEC.md §B/Module 5.

Công thức đề bài (không học hàm máy):
  estimated_sales = ms × (1 + α·B/price_original − β·C/200000)
    A = price − voucher_discount    (giá thực trả)
    B = price_original − A          (mức giảm vs gốc)
    C = voucher_min_spend            (độ để xài voucher)

knapsack multiple-choice 0/1 — mỗi SKU chọn tối đa 1 config, max Σestimated_sales,
ràng buộc Σ(voucher_discount × estimated_sales) + gift_cost ≤ budget.
Viết MỚI (không port bibica_methods): dict DP `dp{weight:(value,picks)}`.

α,β lấy từ learner / shop_config. gift_cost truyền từ Module 4 (proxy 0).

Stdlib thuần.
"""
from typing import Any, Dict, List, Tuple

from ._helpers import to_float

# Lưới cấu hình (spec: 7×6×4 = 168 config/SKU).
DISCOUNTS = [0, 5, 10, 15, 20, 25, 30]              # %
VOUCHERS = [0, 10_000, 20_000, 30_000, 40_000, 50_000]   # VND
MIN_SPENDS = [50_000, 100_000, 150_000, 200_000]    # VND

DISCOUNT_CAP_PCT = 36.0     # M1 cap: skip config disc > 36%
SCALE = 100_000.0           # voucher_cost / SCALE = integer weight (VND/100k).
                           # budget 500M -> W = 5000 (DP nhỏ, chạy nhanh trong stdlib).


def estimated_sales(ms: float, price: float, voucher_disc: float,
                    price_original: float, voucher_min_spend: float,
                    alpha: float, beta: float) -> float:
    if price_original <= 0:
        return ms
    A = price - voucher_disc
    B = price_original - A
    C = voucher_min_spend or 0.0
    factor = 1.0 + alpha * (B / price_original) - beta * (C / 200_000.0)
    factor = max(0.0, factor)
    return ms * factor


def gen_config_grid(orig_price: float) -> List[Dict[str, Any]]:
    """168 config cho 1 SKU. Mỗi config: discount_pct, price (sau disc), voucher_disc, min_spend."""
    cfgs = []
    for d in DISCOUNTS:
        price = round(orig_price * (1 - d / 100.0))
        for v in VOUCHERS:
            for mn in MIN_SPENDS:
                cfgs.append({
                    "discount_pct": float(d),
                    "price": price,
                    "voucher_disc": float(v),
                    "min_spend": float(mn),
                })
    return cfgs


def knapsack(data_pool: List[Dict[str, Any]],
             budget: float, alpha: float, beta: float,
             gift_cost: float = 0.0,
             max_configs_per_sku: int = 5) -> Dict[str, Any]:
    """Multiple-choice 0/1 knapsack. Trả skus (selected) + totals.

    Bỏ SKUs không hợp lệ (orig<=0, sold<=0). Mỗi SKU giữ top-K config theo est_sales
    (filter disc<=cap, est_sales>0) để giới hạn bùng nổ tổ hợp.
    """
    # Build groups: mỗi SKU = list of (value, weight, cfg)
    groups: List[List[Tuple[float, int, Dict[str, Any], Dict[str, Any]]]] = []
    sku_meta: List[Dict[str, Any]] = []
    for r in data_pool:
        orig = to_float(r.get("price_original"))
        ms = to_float(r.get("monthly_sold_value"))
        if orig <= 0 or ms <= 0:
            continue
        cfgs = gen_config_grid(orig)
        # lọc + tính est_sales
        scored = []
        for c in cfgs:
            if c["discount_pct"] > DISCOUNT_CAP_PCT:
                continue
            es = estimated_sales(ms, c["price"], c["voucher_disc"], orig,
                                 c["min_spend"], alpha, beta)
            if es <= 0:
                continue
            vcost = c["voucher_disc"] * es
            scored.append((es, int(round(vcost / SCALE)), c, r))
        if not scored:
            continue
        # top-K theo est_sales
        scored.sort(key=lambda t: t[0], reverse=True)
        scored = scored[:max_configs_per_sku]
        groups.append(scored)
        sku_meta.append(r)

    if not groups:
        return {
            "skus": [],
            "totals": {"budget": budget, "used": 0.0, "remaining": budget - gift_cost,
                       "total_est_sales": 0.0, "n_selected": 0},
        }

    # Trừ gift_cost khỏi ngân sách trước DP.
    effective_budget = max(0.0, budget - gift_cost)
    W = int(effective_budget / SCALE)

    # DP multiple-choice 0/1: dp[weight] = (max_value, picks_tuple)
    dp: Dict[int, Tuple[float, Tuple]] = {0: (0.0, ())}
    for gi, group in enumerate(groups):
        ndp = dict(dp)  # choice "skip" SKU này (kế thừa dp cũ)
        for w, (val, picks) in dp.items():
            for ci, (v, wt, cfg, _r) in enumerate(group):
                nw = w + wt
                if nw > W:
                    continue
                nv = val + v
                cur = ndp.get(nw)
                if cur is None or nv > cur[0]:
                    ndp[nw] = (nv, picks + ((gi, ci),))
        dp = ndp

    # best weight
    if not dp:
        return {
            "skus": [],
            "totals": {"budget": budget, "used": 0.0, "remaining": budget - gift_cost,
                       "total_est_sales": 0.0, "n_selected": 0},
        }
    best_w = max(dp, key=lambda w: dp[w][0])
    best_val, best_picks = dp[best_w]

    # khôi phục selected
    selected_skus = []
    seen_gi = set()
    total_used = 0.0
    total_sales = 0.0
    for gi, ci in best_picks:
        if gi in seen_gi:  # chống trùng (không nên xãy ra)
            continue
        seen_gi.add(gi)
        _v, _wt, cfg, r = groups[gi][ci]
        es = _v
        vcost = cfg["voucher_disc"] * es
        total_used += vcost
        total_sales += es
        selected_skus.append({
            "item_id": r["item_id"],
            "name": r.get("product_name", ""),
            "discount_pct": cfg["discount_pct"],
            "voucher_amount": cfg["voucher_disc"],
            "min_spend": cfg["min_spend"],
            "price_final": cfg["price"],
            "expected_sales": round(es, 2),
            "voucher_cost": round(vcost, 2),
            "is_selected": True,
        })

    # DP theo weight = vcost/SCALE (làm tròn) -> tổng thực có thể lệch vài SCALE.
    # Fit budget: nếu used > budget thì bỏ SKU có hiệu quả (est_sales/vcost) thấp nhất.
    while selected_skus and total_used + gift_cost > budget:
        selected_skus.sort(key=lambda s: s["expected_sales"] / max(s["voucher_cost"], 1.0))
        removed = selected_skus.pop()
        total_used -= removed["voucher_cost"]
        total_sales -= removed["expected_sales"]

    used = total_used + gift_cost
    return {
        "skus": selected_skus,
        "totals": {
            "budget": budget,
            "used": round(used, 2),
            "remaining": round(budget - used, 2),
            "total_est_sales": round(total_sales, 2),
            "n_selected": len(selected_skus),
        },
    }


# =====================================================================
# SELF-TEST
# =====================================================================
if __name__ == "__main__":
    pool = [
        {"item_id": "a", "product_name": "Kẹo A", "price_original": 50000, "monthly_sold_value": 200},
        {"item_id": "b", "product_name": "Kẹo B", "price_original": 100000, "monthly_sold_value": 50},
        {"item_id": "c", "product_name": "Kẹo C", "price_original": 30000, "monthly_sold_value": 0},  # skip (sold 0)
    ]
    out = knapsack(pool, budget=50_000_000, alpha=0.5, beta=0.2, gift_cost=0)
    print("[M5 test] skus selected:", len(out["skus"]), "totals:", out["totals"])
    assert out["totals"]["n_selected"] >= 1, "chọn ít nhất 1 SKU"
    assert out["totals"]["used"] <= 50_000_000, "không vượt budget"
    assert out["totals"]["remaining"] == round(50_000_000 - out["totals"]["used"], 2)
    for s in out["skus"]:
        assert s["is_selected"] is True
        assert s["discount_pct"] <= 36
    # gift_cost trừ budget
    out2 = knapsack(pool, budget=10_000_000, alpha=0.5, beta=0.2, gift_cost=5_000_000)
    # hiệp lực budget 10M - gift 5M = 5M khả dụng
    assert out2["totals"]["used"] <= 10_000_000
    print("✓ m5_voucher OK (knapsack DP chạy, cap 36%, budget+giftCost)")
