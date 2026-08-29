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
    """Hàm tính toán doanh số ước tính dựa trên các thông số đầu vào, bao gồm giá gốc, giá sau giảm giá, mức giảm giá của voucher, điều kiện sử dụng voucher, và các hệ số alpha, beta để điều chỉnh nhu cầu khách hàng."""
    if price_original <= 0 or ms <= 0:
        return max(0.0, ms)

    real_price = max(0.0, price - voucher_disc)
    total_savings = max(0.0, price_original - real_price)
    min_spend = max(0.0, voucher_min_spend)

    # Customer attraction equation
    factor = (1.0 / 30) + alpha * (total_savings / price_original) - beta * (min_spend / 200_000.0)
    factor = max(0.0, factor)       # factor là nhân tố tăng/giảm nhu cầu khách hàng dựa trên mức giảm giá và điều kiện sử dụng voucher
    return ms * factor


def generate_sku_config_grid(orig_price: float) -> List[Dict[str, Any]]:
    """Hàm tạo lưới cấu hình cho một SKU dựa trên giá gốc. Mỗi cấu hình bao gồm discount_pct, price (sau giảm giá), voucher_disc, min_spend."""
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
    must_select_all: bool = False,
) -> Dict[str, Any]:
    """
    Hàm tối ưu hóa việc phân bổ voucher cho các SKU dựa trên ngân sách, chi phí quà tặng, và các thông số alpha, beta.
    Sử dụng thuật toán Multiple-Choice Knapsack DP để chọn cấu hình tốt nhất cho mỗi SKU nhằm tối đa hóa doanh số ước tính trong khi tuân thủ ngân sách.

    Tham số must_select_all:
      - False (mặc định): giữ hành vi cũ — cho phép bỏ qua một SKU (chọn tập con các SKU).
      - True: bắt buộc chọn đúng một cấu hình voucher cho mỗi SKU hợp lệ trong đầu vào.
        Nếu không thể chọn đủ tất cả SKU (vì có SKU hợp lệ không có cấu hình nào, hoặc
        vượt ngân sách), trả về kết quả có trường `error` mô tả lý do và `sku_allocations` rỗng.
    """
    effective_budget = max(0.0, float(budget_vnd) - float(gift_cost))
    max_w = int(effective_budget / SCALE)

    sku_groups: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = [] #lưu cấu hính của từng SKU

    for r in data_pool:
        orig = to_float(r.get("price_original")) or to_float(r.get("price"))    # giá gốc
        ms = to_float(r.get("monthly_sold_value"))                              # doanh số trung bình hàng tháng
        if orig <= 0 or ms <= 0:
            continue

        configs = generate_sku_config_grid(orig)
        candidates: List[Dict[str, Any]] = []

        # đây là doanh thu kỳ vọng khi không áp dụng voucher hay giảm giá, để đảm bảo rằng luôn có một lựa chọn mặc định cho mỗi SKU
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

            # Tính toán doanh số ước tính dựa trên cấu hình hiện tại
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

        # Khi must_select_all=True, một SKU hợp lệ mà không còn cấu hình nào thỏa
        # (danh sách scored rỗng) là vô nghiệm: không thể "chọn tất cả" được nữa.
        if must_select_all and not candidates:
            return {
                "budget": budget_vnd,
                "used_voucher_cost": 0,
                "gift_cost": round(gift_cost),
                "total_used": round(gift_cost),
                "remaining_budget": round(max(0.0, budget_vnd - gift_cost)),
                "budget_utilization_pct": 0.0,
                "total_estimated_sales": 0,
                "n_selected_skus": 0,
                "sku_allocations": [],
                "error": f"SKU {r.get('item_id')} has no valid voucher config",
            }

        sku_groups.append((r, candidates))

    # Multiple-Choice Knapsack DP: dp[w] = (max_value, [chosen_config_per_sku])
    dp: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {0: (0.0, [])}

    for sku, candidates in sku_groups:
        if must_select_all:
            # Bắt buộc chọn đúng một cấu hình cho SKU này — không còn lựa chọn "bỏ qua SKU".
            # DP mới rỗng, chỉ chứa các trạng thái sinh ra khi chọn một cấu hình của nhóm này.
            new_dp: Dict[int, Tuple[float, List[Dict[str, Any]]]] = {}
        else:
            # Hành vi cũ: cho phép giữ nguyên trạng thái DP cũ (skip nhóm này).
            # Bắt đầu từ bản sao DP cũ để "không chọn SKU đó" vẫn là lựa chọn hợp lệ.
            new_dp = {w: (v, list(p)) for w, (v, p) in dp.items()}

        for w_curr, (val_curr, picks_curr) in dp.items():
            for cand in candidates:
                w_next = w_curr + cand["cost_w"]
                if w_next <= max_w:
                    val_next = val_curr + cand["est_sales"]
                    if w_next not in new_dp or val_next > new_dp[w_next][0]:
                        new_dp[w_next] = (val_next, picks_curr + [dict(cand, sku=sku)])
        if new_dp:
            dp = new_dp
        elif must_select_all:
            # Không thể chọn bất kỳ cấu hình nào của SKU này trong ngân sách.
            return {
                "budget": budget_vnd,
                "used_voucher_cost": 0,
                "gift_cost": round(gift_cost),
                "total_used": round(gift_cost),
                "remaining_budget": round(max(0.0, budget_vnd - gift_cost)),
                "budget_utilization_pct": 0.0,
                "total_estimated_sales": 0,
                "n_selected_skus": 0,
                "sku_allocations": [],
                "error": "cannot select all SKUs within budget",
            }

    best_w = max(dp.keys(), key=lambda w: dp[w][0]) if dp else 0
    best_val, best_picks = dp.get(best_w, (0.0, []))

    # Khi must_select_all=True, kiểm tra số SKU được chọn có đúng bằng số nhóm (số SKU hợp lệ) hay không.
    if must_select_all and len(best_picks) != len(sku_groups):
        return {
            "budget": budget_vnd,
            "used_voucher_cost": 0,
            "gift_cost": round(gift_cost),
            "total_used": round(gift_cost),
            "remaining_budget": round(max(0.0, budget_vnd - gift_cost)),
            "budget_utilization_pct": 0.0,
            "total_estimated_sales": 0,
            "n_selected_skus": 0,
            "sku_allocations": [],
            "error": "cannot select all SKUs within budget",
        }

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
            "expected_sales": round(pick["est_sales"]),
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
