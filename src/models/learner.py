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

"""Online Learner Loop — Model Adaptation from Actual Livestream Outcomes."""

from typing import Any, Dict, List, Optional

ALPHA_BOUNDS = (0.1, 1.0)
BETA_BOUNDS = (0.05, 0.5)
ALPHA_STEP = 0.05
BETA_STEP = 0.02
REDEEM_LOW = 0.30
REDEEM_HIGH = 0.70
EST_BIAS_THRESHOLD = 5.0
EMA_LAMBDA = 0.5


def default_learning_state() -> Dict[str, Any]:
    """Returns initial fresh learning state dictionary."""
    return {
        "version": 1,
        "last_session_id": None,
        "params": {
            "alpha": 0.5,
            "beta": 0.2,
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
        },
        "history": [],
    }


def update_learning_state(
    current_state: Optional[Dict[str, Any]], feedback: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Updates model parameters (alpha, beta, elasticity) from actual livestream performance.
    """
    state = dict(current_state or default_learning_state())
    params = state.setdefault("params", {"alpha": 0.5, "beta": 0.2, "elasticity_beta_by_line": {}})
    metrics = state.setdefault("metrics", {"n_sessions": 0, "rolling_mape": None, "rolling_redeem_rate": None, "lift_vs_hold": None})
    history = state.setdefault("history", [])

    actual_rows: List[Dict[str, Any]] = feedback.get("actual", [])
    session_id = feedback.get("session_id", "unknown")
    date_str = feedback.get("date", "")

    if not actual_rows:
        return state

    # 1. Calculate Session MAPE & Mean Bias
    errors: List[float] = []
    biases: List[float] = []
    redeemed_count = 0
    voucher_opportunities = 0

    for r in actual_rows:
        est = float(r.get("estimated_sales", 0.0))
        act = float(r.get("actual_sales", 0.0))
        if act > 0:
            errors.append(abs(est - act) / act)
            biases.append(est - act)

        if float(r.get("voucher_amount_used", 0.0)) > 0:
            voucher_opportunities += 1
            if bool(r.get("voucher_redeemed", False)):
                redeemed_count += 1

    session_mape = (sum(errors) / len(errors)) if errors else 0.0
    mean_bias = (sum(biases) / len(biases)) if biases else 0.0
    redeem_rate = (redeemed_count / voucher_opportunities) if voucher_opportunities > 0 else 0.5

    # 2. Update Alpha (Price discount sensitivity)
    alpha = float(params.get("alpha", 0.5))
    if mean_bias > EST_BIAS_THRESHOLD:
        alpha = max(ALPHA_BOUNDS[0], alpha - ALPHA_STEP)
    elif mean_bias < -EST_BIAS_THRESHOLD:
        alpha = min(ALPHA_BOUNDS[1], alpha + ALPHA_STEP)
    params["alpha"] = round(alpha, 3)

    # 3. Update Beta (Voucher minimum spend barrier)
    beta = float(params.get("beta", 0.2))
    if redeem_rate < REDEEM_LOW:
        # Vouchers rarely redeemed -> min spend is too punishing -> increase beta penalty
        beta = min(BETA_BOUNDS[1], beta + BETA_STEP)
    elif redeem_rate > REDEEM_HIGH:
        # Vouchers frequently redeemed -> ease beta barrier
        beta = max(BETA_BOUNDS[0], beta - BETA_STEP)
    params["beta"] = round(beta, 3)

    # 4. Update Rolling Metrics
    n_sessions = int(metrics.get("n_sessions", 0)) + 1
    metrics["n_sessions"] = n_sessions

    old_mape = metrics.get("rolling_mape")
    if old_mape is None:
        metrics["rolling_mape"] = round(session_mape, 3)
    else:
        metrics["rolling_mape"] = round((1.0 - EMA_LAMBDA) * float(old_mape) + EMA_LAMBDA * session_mape, 3)

    old_redeem = metrics.get("rolling_redeem_rate")
    if old_redeem is None:
        metrics["rolling_redeem_rate"] = round(redeem_rate, 3)
    else:
        metrics["rolling_redeem_rate"] = round((1.0 - EMA_LAMBDA) * float(old_redeem) + EMA_LAMBDA * redeem_rate, 3)

    state["last_session_id"] = session_id
    history.append({
        "session_id": session_id,
        "date": date_str,
        "session_mape": round(session_mape, 3),
        "mean_bias": round(mean_bias, 1),
        "redeem_rate": round(redeem_rate, 3),
        "alpha": params["alpha"],
        "beta": params["beta"],
    })

    return state
