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

"""Pipeline Orchestrator — Executes M1 to M5 Decision Engine."""

import datetime
import uuid
from typing import Any, Callable, Dict, List, Optional

from ._helpers import to_float
from .m1_price import decide_sku_pricing, estimate_elasticity_with_fe
from .m2_heroscore import calculate_hero_scores
from .m3_timeslot import optimize_timeslot
from .m4_combo import generate_combos
from .m5_voucher import optimize_voucher_budget


def run_pipeline(
    data_pool: List[Dict[str, Any]],
    observations: List[Dict[str, Any]],
    shop_config: Optional[Dict[str, Any]] = None,
    learning_state: Optional[Dict[str, Any]] = None,
    snapshots: Optional[List[Dict[str, Any]]] = None,
    now: Optional[datetime.datetime] = None,
) -> Dict[str, Any]:
    """
    Executes the full 5-module AI livestream strategist pipeline.
    """
    if now is None:
        now = datetime.datetime.now(datetime.timezone.utc)

    cfg = dict(shop_config or {})
    shop_id = str(cfg.get("shop_id") or (data_pool[0]["shop_id"] if data_pool else "unknown"))
    shop_name = str(cfg.get("shop_name") or "")

    # Inject learned parameters if available
    alpha = float(cfg.get("alpha", 0.5))
    beta = float(cfg.get("beta", 0.2))
    if learning_state and "params" in learning_state:
        learned_params = learning_state["params"]
        if "alpha" in learned_params:
            alpha = float(learned_params["alpha"])
        if "beta" in learned_params:
            beta = float(learned_params["beta"])

    budget = float(cfg.get("budget_voucher_month", 500_000_000.0))
    session_id = str(uuid.uuid4())
    snaps = snapshots if snapshots is not None else data_pool

    # Module 1: Price Strategy & Elasticity
    elasticity_info = estimate_elasticity_with_fe(observations)
    pricing_list: List[Dict[str, Any]] = []
    for r in data_pool:
        iid = str(r["item_id"])
        name = str(r.get("product_name", ""))
        orig = to_float(r.get("price_original")) or to_float(r.get("price"))
        ms = to_float(r.get("monthly_sold_value"))
        cur_disc = to_float(r.get("discount_percent"))

        pricing_decision = decide_sku_pricing(
            item_id=iid,
            name=name,
            orig_price=orig,
            ms_baseline=ms,
            elasticity_info=elasticity_info,
            current_discount_pct=cur_disc,
        )
        pricing_list.append(pricing_decision)

    # Module 2: Hero Score Ranking
    hero_scores = calculate_hero_scores(data_pool, now=now)

    # Module 3: Timeslot Optimization
    timeslot_decision = optimize_timeslot(snaps, shop_id=shop_id)

    # Module 4: Smart Combo & GWP Bundles
    combos = generate_combos(data_pool, hero_ranked_items=hero_scores, now=now)
    total_gift_cost = sum(float(c.get("gift_cost", 0.0)) for c in combos)

    # Module 5: Voucher Knapsack Allocation
    voucher_plan = optimize_voucher_budget(
        data_pool=data_pool,
        budget_vnd=budget,
        alpha=alpha,
        beta=beta,
        gift_cost=total_gift_cost,
    )

    # Summary KPI lift estimation
    baseline_gmv = sum(to_float(r.get("monthly_sold_value")) for r in data_pool)
    projected_gmv = float(voucher_plan.get("total_estimated_sales", baseline_gmv))
    estimated_lift_pct = round(((projected_gmv - baseline_gmv) / baseline_gmv) * 100.0, 1) if baseline_gmv > 0 else 0.0

    return {
        "shop_id": shop_id,
        "shop_name": shop_name,
        "session_id": session_id,
        "created_at": now.isoformat(),
        "summary": {
            "total_skus": len(data_pool),
            "selected_skus": voucher_plan.get("n_selected_skus", 0),
            "budget_used": voucher_plan.get("total_used", 0),
            "total_budget": budget,
            "budget_utilization_pct": voucher_plan.get("budget_utilization_pct", 0.0),
            "projected_sales_units": projected_gmv,
            "projected_lift_pct": estimated_lift_pct,
            "recommended_timeslot": timeslot_decision.get("recommended_slot", "20:00 – 22:00"),
        },
        "m1_pricing": {
            "elasticity_info": elasticity_info,
            "items": pricing_list,
        },
        "m2_heros": hero_scores,
        "m3_timeslot": timeslot_decision,
        "m4_combos": combos,
        "m5_voucher": voucher_plan,
        "learning_params_used": {
            "alpha": alpha,
            "beta": beta,
        },
    }
