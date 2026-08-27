"""Learner loop — AI học lại sau mỗi phiên (Phase D).

Contract theo DELIVERABLE_SPEC.md §Learner loop.

`update(learning_state, feedback)` cập nhật 3 tham số cho phiên sau:
  1. MAPE = mean(|estimated − actual|/actual) trên SKU có actual>0.
  2. α: nếu estimated_sales thiên cao (mean(est−actual)>0) -> giảm α; ngược lại tăng.
     Bước 0.05, kẹp bounds α [0.1, 1.0].
  3. β: theo redeem_rate. Redeem thấp -> β tăng (phạt ngưỡng khó hơn); cao -> β giảm.
     Bước 0.02, kẹp bounds β [0.05, 0.5].
  4. elasticity_beta_by_line: nếu đủ observation/line (>=5) -> re-estimate per-line
     bằng m1_price.estimate_elasticity_with_fe (build từ feedback-as-experiment).
  5. metrics: n_sessions+1, rolling_mape (EMA), rolling_redeem_rate, lift_vs_hold.

feedback dict khớp FeedbackRequest.model_dump() của server (schemas.py):
  {session_id, date, actual: [{item_id, scenario_used, discount_used_pct,
   estimated_sales, actual_sales, voucher_amount_used, voucher_redeemed, combo_sold}]}

Stdlib thuần.
"""
import math
from typing import Any, Dict, List, Optional

# Bounds theo spec (§Learner metrics bounds).
ALPHA_BOUNDS = [0.1, 1.0]
BETA_BOUNDS = [0.05, 0.5]
DISCOUNT_PCT_BOUNDS = [0, 36]

ALPHA_STEP = 0.05
BETA_STEP = 0.02
REDEEM_LOW = 0.3      # redeem_rate < 0.3 -> voucher ít dùng -> β tăng
REDEEM_HIGH = 0.7     # > 0.7 -> dùng nhiều -> β giảm
EST_BIAS_THRESHOLD = 5.0   # |mean(est-actual)| > 5 mới nâng/ hạ α
MIN_POINTS_PER_LINE = 5

DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 0.2
EMA_LAMBDA = 0.5      # rolling = (1-λ)*old + λ*new


def default_learning_state() -> Dict[str, Any]:
    return {
        "version": 1,
        "last_session_id": None,
        "params": {
            "alpha": DEFAULT_ALPHA,
            "beta": DEFAULT_BETA,
            "elasticity_beta_by_line": {},
        },
        "metrics": {
            "n_sessions": 0,
            "rolling_mape": None,
            "rolling_redeem_rate": None,
            "lift_vs_hold": None,
        },
        "bounds": {
            "alpha": list(ALPHA_BOUNDS),
            "beta": list(BETA_BOUNDS),
            "discount_pct": list(DISCOUNT_PCT_BOUNDS),
        },
    }


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _ema(old: Optional[float], new: float, lam: float = EMA_LAMBDA) -> float:
    if old is None:
        return new
    return (1 - lam) * old + lam * new


def update(learning_state: Optional[Dict[str, Any]],
           feedback: Dict[str, Any]) -> Dict[str, Any]:
    """Cập nhật learning_state từ feedback phiên vừa rồi. Trả dict khớp LearningState."""
    state = learning_state or default_learning_state()
    # zorgen cấu trúc đầy đủ (chống state cũ thiếu field).
    params = state.get("params") or {}
    metrics = state.get("metrics") or {}
    bounds = state.get("bounds") or {
        "alpha": list(ALPHA_BOUNDS), "beta": list(BETA_BOUNDS),
        "discount_pct": list(DISCOUNT_PCT_BOUNDS),
    }
    alpha = float(params.get("alpha", DEFAULT_ALPHA))
    beta = float(params.get("beta", DEFAULT_BETA))
    beta_by_line: Dict[str, float] = dict(params.get("elasticity_beta_by_line") or {})

    actual_items = feedback.get("actual") or []

    # ---- 1. MAPE + bias ----
    mape_vals = []
    est_minus_actual = []
    for it in actual_items:
        est = it.get("estimated_sales")
        act = it.get("actual_sales")
        if est is None or act is None or act <= 0:
            continue
        mape_vals.append(abs(est - act) / act)
        est_minus_actual.append(est - act)
    new_mape = (sum(mape_vals) / len(mape_vals)) if mape_vals else None

    # ---- 2. α ----
    if est_minus_actual:
        bias = sum(est_minus_actual) / len(est_minus_actual)
        if bias > EST_BIAS_THRESHOLD:
            # estimated thiên cao (thực tế thấp hơn dự đoán) -> level giảm đóng góp quá nhiều -> giảm α
            alpha -= ALPHA_STEP
        elif bias < -EST_BIAS_THRESHOLD:
            alpha += ALPHA_STEP
        alpha = _clamp(alpha, ALPHA_BOUNDS[0], ALPHA_BOUNDS[1])

    # ---- 3. β theo redeem_rate ----
    redeem_flags = [it.get("voucher_redeemed") for it in actual_items
                    if it.get("voucher_redeemed") is not None]
    redeem_rate = (sum(1 for f in redeem_flags if f) / len(redeem_flags)) if redeem_flags else None
    if redeem_rate is not None:
        if redeem_rate < REDEEM_LOW:
            beta += BETA_STEP       # ít dùng -> phạt ngưỡng mạnh hơn
        elif redeem_rate > REDEEM_HIGH:
            beta -= BETA_STEP       # dùng nhiều -> nới ngưỡng
        beta = _clamp(beta, BETA_BOUNDS[0], BETA_BOUNDS[1])

    # ---- 4. elasticity_beta_by_line ----
    # Build observation-like per-line từ feedback: mỗi item = 1 điểm thực nghiệm.
    # Cần item_id -> line lookup — feedback KHÔNG chứa 'line'. Mô phỏng: gom theo line
    # nếu feedback item có line (không bắt buộc); nếu không có -> skip (Phase D đơn giản).
    by_line: Dict[str, List[Dict[str, Any]]] = {}
    for it in actual_items:
        line = it.get("line")
        if not line:
            continue
        if (it.get("actual_sales") is not None and it.get("estimated_sales") is not None
                and it.get("discount_used_pct") is not None):
            # tạo observation giả của line: dlog_price ~ disc, dlog_sold ~ actual/estimated
            disc = float(it.get("discount_used_pct") or 0)
            dlp = math.log(1 - disc / 100.0) if disc < 100 else 0.0
            try:
                dls = math.log1p(float(it["actual_sales"])) - math.log1p(float(it["estimated_sales"]))
            except (TypeError, ValueError):
                continue
            by_line.setdefault(str(line), []).append({
                "dlog_price": dlp, "dlog_sold": dls,
                "shop_id": str(feedback.get("session_id", "fb")), "line": str(line),
            })
    if by_line:
        from . import m1_price  # tránh import vòng khi module load
        for line, obs in by_line.items():
            if len(obs) < MIN_POINTS_PER_LINE:
                continue
            res = m1_price.estimate_elasticity_with_fe(obs)
            if res.get("is_real_estimate"):
                beta_by_line[line] = res["beta"]

    # ---- 5. metrics ----
    old_mape = metrics.get("rolling_mape")
    rolling_mape = _ema(old_mape, new_mape) if new_mape is not None else old_mape
    old_redeem = metrics.get("rolling_redeem_rate")
    rolling_redeem = _ema(old_redeem, redeem_rate) if redeem_rate is not None else old_redeem

    # lift_vs_hold: mean((actual - est_hold)/est_hold) nếu có est_hold — feedback không
    # có est_hold trực tiếp; dùng ratio actual/estimated của các scenario_used=='hold'.
    hold_items = [it for it in actual_items if it.get("scenario_used") == "hold"
                  and it.get("actual_sales") is not None and it.get("estimated_sales")
                  and it["estimated_sales"] > 0]
    if hold_items:
        ratios = [it["actual_sales"] / it["estimated_sales"] - 1.0 for it in hold_items]
        new_lift = sum(ratios) / len(ratios)
        old_lift = metrics.get("lift_vs_hold")
        lift_vs_hold = _ema(old_lift, new_lift) if old_lift is not None else new_lift
    else:
        lift_vs_hold = metrics.get("lift_vs_hold")

    return {
        "version": state.get("version", 1),
        "last_session_id": feedback.get("session_id"),
        "params": {
            "alpha": round(alpha, 4),
            "beta": round(beta, 4),
            "elasticity_beta_by_line": beta_by_line,
        },
        "metrics": {
            "n_sessions": int(metrics.get("n_sessions", 0)) + 1,
            "rolling_mape": round(rolling_mape, 4) if rolling_mape is not None else None,
            "rolling_redeem_rate": round(rolling_redeem, 4) if rolling_redeem is not None else None,
            "lift_vs_hold": round(lift_vs_hold, 4) if lift_vs_hold is not None else None,
        },
        "bounds": bounds,
    }


# =====================================================================
# SELF-TEST
# =====================================================================
if __name__ == "__main__":
    # Trường hợp: estimated thiên cao (est=200, actual=50) -> α giảm
    state = default_learning_state()
    fb = {
        "session_id": "s1", "date": "2026-08-26",
        "actual": [
            {"item_id": "a", "scenario_used": "flash", "discount_used_pct": 25,
             "estimated_sales": 200, "actual_sales": 50,
             "voucher_amount_used": 30000, "voucher_redeemed": True, "combo_sold": True},
            {"item_id": "b", "scenario_used": "mild", "discount_used_pct": 10,
             "estimated_sales": 100, "actual_sales": 40,
             "voucher_amount_used": 10000, "voucher_redeemed": False, "combo_sold": False},
        ],
    }
    new = update(state, fb)
    print("[learner test] feedback thiên cao (est>>actual), redeem 1/2:")
    print("  alpha:", state["params"]["alpha"], "->", new["params"]["alpha"], "(phải giảm)")
    print("  beta:", state["params"]["beta"], "->", new["params"]["beta"])
    print("  mape:", new["metrics"]["rolling_mape"], "n_sessions:", new["metrics"]["n_sessions"])
    print("  last_session_id:", new["last_session_id"])
    assert new["params"]["alpha"] < 0.5, "α phải giảm vì estimated thiên cao"
    assert new["metrics"]["n_sessions"] == 1
    assert new["metrics"]["rolling_mape"] is not None and new["metrics"]["rolling_mape"] > 0
    assert new["last_session_id"] == "s1"

    # Trường hợp 2: redeem_rate thấp -> β tăng
    fb2 = {"session_id": "s2", "date": "2026-08-27",
           "actual": [{"item_id": "a", "scenario_used": "hold", "discount_used_pct": 0,
                       "estimated_sales": 50, "actual_sales": 50,
                       "voucher_amount_used": 10000, "voucher_redeemed": False}]}
    new2 = update(new, fb2)
    print("\n[learner test 2] redeem_rate 0 -> β tăng:", new["params"]["beta"], "->", new2["params"]["beta"])
    assert new2["params"]["beta"] >= new["params"]["beta"], "β tăng khi redeem thấp"
    assert new2["metrics"]["n_sessions"] == 2
    print("✓ learner OK (MAPE, α theo bias, β theo redeem, n_sessions)")
