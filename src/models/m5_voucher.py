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

"""Module 5 — 0/1 Multiple-Choice DP Knapsack Voucher Optimization."""

from typing import Any, Dict, List, Tuple

from ._helpers import to_float

DISCOUNTS = [0, 5, 10, 15, 20, 25, 30]  # %
VOUCHERS = [0, 10_000, 20_000, 30_000, 40_000, 50_000]  # VND
MIN_SPENDS = [50_000, 100_000, 150_000, 200_000]  # VND

DISCOUNT_CAP_PCT = 36.0
SCALE = 100_000.0  # Discretization scale (VND / 100k) for fast DP


def calculate_estimated_sales(
    ms: float,
    price: float,
    voucher_disc: float,
    price_original: float,
    voucher_min_spend: float,
    alpha: float = 0.5,
    beta: float = 0.2,
) -> float:
    """Calculates customer demand multiplier from discount and voucher attractiveness."""
    if price_original <= 0 or ms <= 0:
        return max(0.0, ms)

    real_price = max(0.0, price - voucher_disc)
    total_savings = max(0.0, price_original - real_price)
    min_spend = max(0.0, voucher_min_spend)

    # Customer attraction equation
    factor = 1.0 + alpha * (total_savings / price_original) - beta * (min_spend / 200_000.0)
    factor = max(0.0, factor)
    return ms * factor


def generate_sku_config_grid(orig_price: float) -> List[Dict[str, Any]]:
    """Generates 168 configuration points for a given SKU."""
    configs: List[Dict[str, Any]] = []
    for d in DISCOUNTS:
        p = round(orig_price * (1.0 - d / 100.0))
        for v in VOUCHERS:
            for mn in MIN_SPENDS:
                configs.append({
                    "discount_pct": float(d),
                    "price": float(p),
                    "voucher_disc": float(v),
                    "min_spend": float(mn),
                })
    return configs


def optimize_voucher_budget(
    data_pool: List[Dict[str, Any]],
    budget_vnd: float = 500_000_000.0,
    alpha: float = 0.5,
    beta: float = 0.2,
    gift_cost: float = 0.0,
) -> Dict[str, Any]:
    """
    Solves Multiple-Choice 0/1 Knapsack to select optimal voucher & discount configuration
    for each SKU to maximize estimated sales under monthly budget constraint.
    """
    effective_budget = max(0.0, float(budget_vnd) - float(gift_cost))
    max_w = int(effective_budget / SCALE)

    sku_groups: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []

    for r in data_pool:
        orig = to_float(r.get("price_original")) or to_float(r.get("price"))
        ms = to_float(r.get("monthly_sold_value"))
        if orig <= 0 or ms <= 0:
            continue

        configs = generate_sku_config_grid(orig)
        candidates: List[Dict[str, Any]] = []

        # Baseline (no voucher, 0% discount)
        base_sales = calculate_estimated_sales(ms, orig, 0.0, orig, 0.0, alpha, beta)
        candidates.append({
            "discount_pct": 0.0,
            "voucher_disc": 0.0,
            "min_spend": 0.0,
            "price_final": orig,
            "est_sales": base_sales,
            "cost_vnd": 0.0,
            "cost_w": 0,
        })

        for cfg in configs:
            if cfg["discount_pct"] > DISCOUNT_CAP_PCT:
                continue
            est_s = calculate_estimated_sales(
                ms, cfg["price"], cfg["voucher_disc"], orig, cfg["min_spend"], alpha, beta
            )
            cost_vnd = cfg["voucher_disc"] * est_s
            cost_w = int(cost_vnd / SCALE)

            if cost_w <= max_w:
                candidates.append({
                    "discount_pct": cfg["discount_pct"],
                    "voucher_disc": cfg["voucher_disc"],
                    "min_spend": cfg["min_spend"],
                    "price_final": cfg["price"] - cfg["voucher_disc"],
                    "est_sales": est_s,
                    "cost_vnd": cost_vnd,
                    "cost_w": cost_w,
                })

        sku_groups.append((r, candidates))

    # Multiple-Choice Knapsack DP: dp[w] = (max_value, [chosen_config_per_sku])
    dp: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {0: (0.0, [])}

    for sku, candidates in sku_groups:
        new_dp: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
        for w_curr, (val_curr, picks_curr) in dp.items():
            for cand in candidates:
                w_next = w_curr + cand["cost_w"]
                if w_next <= max_w:
                    val_next = val_curr + cand["est_sales"]
                    if w_next not in new_dp or val_next > new_dp[w_next][0]:
                        new_dp[w_next] = (val_next, picks_curr + [dict(cand, sku=sku)])
        if new_dp:
            dp = new_dp

    best_w = max(dp.keys(), key=lambda w: dp[w][0]) if dp else 0
    best_val, best_picks = dp.get(best_w, (0.0, []))

    sku_results: List[Dict[str, Any]] = []
    total_cost_vnd = 0.0

    for pick in best_picks:
        sku = pick["sku"]
        cost_v = pick["cost_vnd"]
        total_cost_vnd += cost_v

        sku_results.append({
            "item_id": str(sku["item_id"]),
            "name": str(sku.get("product_name", "")),
            "line": str(sku.get("line", "Other")),
            "price_original": to_float(sku.get("price_original")),
            "discount_pct": pick["discount_pct"],
            "voucher_amount": pick["voucher_disc"],
            "min_spend": pick["min_spend"],
            "price_final": pick["price_final"],
            "expected_sales": round(pick["est_sales"], 1),
            "voucher_cost": round(cost_v),
            "is_selected": pick["voucher_disc"] > 0 or pick["discount_pct"] > 0,
        })

    return {
        "budget": budget_vnd,
        "used_voucher_cost": round(total_cost_vnd),
        "gift_cost": round(gift_cost),
        "total_used": round(total_cost_vnd + gift_cost),
        "remaining_budget": round(max(0.0, budget_vnd - total_cost_vnd - gift_cost)),
        "budget_utilization_pct": round(min(100.0, ((total_cost_vnd + gift_cost) / budget_vnd) * 100.0), 1)
        if budget_vnd > 0
        else 0.0,
        "total_estimated_sales": round(best_val),
        "n_selected_skus": len([s for s in sku_results if s["is_selected"]]),
        "sku_allocations": sku_results,
    }
