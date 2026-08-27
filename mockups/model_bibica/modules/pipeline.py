"""Pipeline orchestrator AREA_303.

run_pipeline(data_pool, observations, shop_config, learner_state, progress_cb) -> dict
chạy 5 module theo thứ tự M1 -> M2 -> M3 -> M4 -> M5 và trả 1 dict đề xuất lớn.

KHÔNG ghi file (file IO là trách nhiệm của server). Model thuần tính toán.
Model KHÔNG biết WebSocket — `progress_cb(event, payload)` là callback do server cung cấp.

Phase B: M1-M5 đều có logic thật, tách ra file riêng trong modules/:
  m1_price.py, m2_heroscore.py, m3_timeslot.py, m4_combo.py, m5_voucher.py.
Learner loop ở modules/learner.py, wire qua server/CLI (Phase D).

Stdlib thuần.
"""
import uuid
from typing import Any, Callable, Dict, List, Optional

from . import m1_price
from . import m2_heroscore, m3_timeslot, m4_combo, m5_voucher
from ._helpers import to_float


def _default_shop_config(shop_id: str, shop_name: str = None) -> Dict[str, Any]:
    return {
        "shop_id": str(shop_id),
        "shop_name": shop_name or "",
        "budget_voucher_month": 500_000_000.0,
        "alpha": 0.5,
        "beta": 0.2,
        "use_dp_knapsack": True,
    }


def run_module1(data_pool: List[Dict[str, Any]], observations: List[Dict[str, Any]],
                 progress_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """Module 1: ước elasticity (OLS fixed effects) + decide_sku cho mỗi SKU.

    Trả dict `m1_pricing` là danh sách theo spec §B/Module 1 + `elasticity_info`.
    """
    if progress_cb:
        progress_cb("module1", {"stage": "estimate_elasticity", "n_observations": len(observations)})
    elasticity_info = m1_price.estimate_elasticity_with_fe(observations)

    if progress_cb:
        progress_cb("module1", {
            "stage": "decide_skus", "n_items": len(data_pool),
            "elasticity_beta": elasticity_info["beta"],
            "is_real_estimate": elasticity_info["is_real_estimate"],
        })

    pricing = []
    for r in data_pool:
        item_id = r["item_id"]
        name = r.get("product_name", "")
        orig = to_float(r.get("price_original"))
        ms = to_float(r.get("monthly_sold_value"))
        cur_disc = to_float(r.get("discount_percent"))
        if orig <= 0:
            # Không đủ data giá -> trả hold an toàn.
            pricing.append({
                "item_id": item_id, "name": name, "scenario": "hold", "discount_pct": 0.0,
                "expected_revenue_hold": 0.0, "expected_revenue_mild": 0.0,
                "expected_revenue_flash": 0.0, "elasticity_beta": elasticity_info["beta"],
                "confidence": "low", "used_fallback": not elasticity_info["is_real_estimate"],
                "current_discount_pct": cur_disc,
            })
            continue
        decision = m1_price.decide_sku(
            item_id, name, orig, ms, elasticity_info, current_discount_pct=cur_disc,
        )
        pricing.append(decision)
    return {"m1_pricing": pricing, "elasticity_info": elasticity_info}


def run_module2(data_pool: List[Dict[str, Any]],
                 now_ts=None,
                 progress_cb: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Module 2: Hero Score (xếp hạng SKU lên live). Chuẩn hoá theo line."""
    if progress_cb:
        progress_cb("module2", {"stage": "hero_score", "n_items": len(data_pool), "status": "computing"})
    heros = m2_heroscore.hero_score(data_pool, now_ts=now_ts)
    if progress_cb:
        progress_cb("module2", {"stage": "done", "n_heros": len(heros), "status": "computed"})
    return heros


def run_module3(snapshots: List[Dict[str, Any]], shop_id: str,
                progress_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """Module 3: chọn khung giờ live. confidence luôn 'low' (suy luận gián tiếp).

    Dùng `snapshots` (toàn bộ rows, có thể nhiều shop_id) cho tín hiệu ngành.
    Nếu chỉ 1 shop -> fallback histogram + confidence low.
    """
    if progress_cb:
        progress_cb("module3", {"stage": "timeslot", "status": "computing"})
    ts = m3_timeslot.timeslot(snapshots, shop_id=shop_id)
    if progress_cb:
        progress_cb("module3", {"stage": "done", "start_hour": ts["start_hour"], "status": "computed"})
    return ts


def run_module4(data_pool: List[Dict[str, Any]], m2_heros: List[Dict[str, Any]],
                now_ts=None,
                progress_cb: Optional[Callable] = None) -> List[Dict[str, Any]]:
    """Module 4: ghép combo (hero + slow + gift). dùng hero_list từ Module 2."""
    if progress_cb:
        progress_cb("module4", {"stage": "combo", "status": "computing"})
    combos = m4_combo.combo(data_pool, m2_heros, now_ts=now_ts)
    if progress_cb:
        progress_cb("module4", {"stage": "done", "n_combos": len(combos), "status": "computed"})
    return combos


def run_module5(data_pool: List[Dict[str, Any]], shop_config: Dict[str, Any],
                m1_pricing: List[Dict[str, Any]],
                gift_cost: float = 0.0,
                progress_cb: Optional[Callable] = None) -> Dict[str, Any]:
    """Module 5: voucher knapsack (multiple-choice 0/1 DP). α,β từ shop_config."""
    if progress_cb:
        progress_cb("module5", {"stage": "voucher", "status": "computing",
                                "budget": shop_config.get("budget_voucher_month")})
    alpha = float(shop_config.get("alpha", 0.5))
    beta = float(shop_config.get("beta", 0.2))
    budget = float(shop_config.get("budget_voucher_month", 500_000_000.0))
    result = m5_voucher.knapsack(data_pool, budget, alpha, beta, gift_cost=gift_cost)
    if progress_cb:
        progress_cb("module5", {"stage": "done", "n_selected": result["totals"]["n_selected"],
                                "used": result["totals"]["used"], "status": "computed"})
    return result


def run_pipeline(data_pool: List[Dict[str, Any]],
                 observations: List[Dict[str, Any]],
                 shop_config: Optional[Dict[str, Any]] = None,
                 learner_state: Optional[Dict[str, Any]] = None,
                 progress_cb: Optional[Callable] = None,
                 snapshots: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """Chạy cả pipeline. `progress_cb(event_name, payload)` để server emit WS events.

    `snapshots` (toàn bộ rows, có thể nhiều shop_id) cho Module 3 tín hiệu ngành.
    Nếu None -> dùng data_pool (fallback, M3 confidence low).

    Trả dict đề xuất:
      {shop_id, shop_name, session_id, m1_pricing, elasticity_info,
       m2_heros, m3_timeslot, m4_combos, m5_voucher, guardrails}
    """
    if shop_config is None:
        shop_config = _default_shop_config(shop_id=(data_pool[0]["shop_id"] if data_pool else "unknown"))
    # learner_state override alpha/beta (Phase D).
    if learner_state:
        params = (learner_state or {}).get("params", {})
        if "alpha" in params:
            shop_config["alpha"] = params["alpha"]
        if "beta" in params:
            shop_config["beta"] = params["beta"]

    shop_id = str(shop_config.get("shop_id", ""))
    session_id = str(uuid.uuid4())
    snaps = snapshots if snapshots is not None else data_pool

    if progress_cb:
        progress_cb("loading", {"n_items": len(data_pool), "n_observations": len(observations), "shop_id": shop_id})

    # M1: giá
    m1 = run_module1(data_pool, observations, progress_cb)
    m1_pricing = m1["m1_pricing"]
    elasticity_info = m1["elasticity_info"]

    # M2: hero score
    m2_heros = run_module2(data_pool, progress_cb=progress_cb)
    # M3: khung giờ (cần snapshots cho ngành, không phải data_pool 1 shop)
    m3_timeslot = run_module3(snaps, shop_id, progress_cb=progress_cb)
    # M4: combo (cần hero list từ M2)
    m4_combos = run_module4(data_pool, m2_heros, progress_cb=progress_cb)
    # M5: voucher (gift_cost tổng từ M4)
    gift_cost = sum((c.get("gift_cost") or 0.0) for c in m4_combos)
    m5_voucher = run_module5(data_pool, shop_config, m1_pricing,
                             gift_cost=gift_cost, progress_cb=progress_cb)

    guardrails = [
        "Không đề xuất SKU discount >= 36% (cap cao nhất từng thấy).",
        "Confidence low / used_fallback -> ép hold (KHÔNG đề xuất giảm giá trên dữ liệu mơ hồ).",
        "Flash sale chỉ khi expected_revenue_flash > expected_revenue_mild * 1.03 (FLASH_MARGIN).",
    ]

    # Lưu ý: KHÔNG gọi progress_cb("done") ở đây — runner chịu trách nhiệm push
    # event "done" cùng với recommendation dict đầy đủ (xem pipeline_runner.py).

    return {
        "shop_id": shop_id,
        "shop_name": shop_config.get("shop_name", ""),
        "session_id": session_id,
        "elasticity_info": elasticity_info,
        "m1_pricing": m1_pricing,
        "m2_heros": m2_heros,
        "m3_timeslot": m3_timeslot,
        "m4_combos": m4_combos,
        "m5_voucher": m5_voucher,
        "guardrails": guardrails,
    }
