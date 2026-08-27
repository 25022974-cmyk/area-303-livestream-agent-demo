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

"""Module 1 — Price Elasticity & Pricing Strategy (Hold / Mild / Flash Sale)."""

import math
from typing import Any, Dict, List, Optional, Tuple

MIN_POINTS = 5
NO_DATA_BETA = -1.0
DISCOUNT_CAP_PCT = 36.0
MILD_DISCOUNT = 10.0
FLASH_DISCOUNT = 25.0
FLASH_MARGIN = 1.03  # Flash revenue must beat mild by at least 3%


def _gauss_solve(A: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """Solves A x = b using Gauss-Jordan elimination with partial pivoting."""
    n = len(A)
    if n == 0 or len(b) != n:
        return None

    # Augmented matrix [A | b]
    M = [A[i][:] + [b[i]] for i in range(n)]

    for i in range(n):
        # Pivot selection
        pivot = i
        for r in range(i + 1, n):
            if abs(M[r][i]) > abs(M[pivot][i]):
                pivot = r
        if pivot != i:
            M[i], M[pivot] = M[pivot], M[i]

        diag = M[i][i]
        if abs(diag) < 1e-12:
            return None  # Singular matrix

        # Normalize pivot row
        for c in range(i, n + 1):
            M[i][c] /= diag

        # Eliminate other rows
        for r in range(n):
            if r != i:
                factor = M[r][i]
                if abs(factor) > 1e-12:
                    for c in range(i, n + 1):
                        M[r][c] -= factor * M[i][c]

    return [M[i][n] for i in range(n)]


def estimate_elasticity_with_fe(observations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Estimates price elasticity beta using log-log OLS with shop and product-line fixed effects.
    """
    if len(observations) < MIN_POINTS:
        return {
            "beta": NO_DATA_BETA,
            "n_observations": len(observations),
            "is_real_estimate": False,
            "note": f"Insufficient data ({len(observations)} < {MIN_POINTS}), using baseline beta={NO_DATA_BETA}.",
        }

    # Collect distinct levels for fixed effects (omitting base category for dummy full rank)
    shops = sorted({str(o["shop_id"]) for o in observations})
    lines = sorted({str(o["line"]) for o in observations})

    shop_dummies = shops[1:] if len(shops) > 1 else []
    line_dummies = lines[1:] if len(lines) > 1 else []

    k = 1 + 1 + len(shop_dummies) + len(line_dummies)  # intercept + log_p + FE dummies
    N = len(observations)
    if N < k:
        return {
            "beta": NO_DATA_BETA,
            "n_observations": N,
            "is_real_estimate": False,
            "note": "Degrees of freedom too low, fallback to baseline.",
        }

    # Build X and y
    X: List[List[float]] = []
    y: List[float] = []

    for o in observations:
        row = [1.0, float(o["delta_log_p"])]
        for s in shop_dummies:
            row.append(1.0 if str(o["shop_id"]) == s else 0.0)
        for l in line_dummies:
            row.append(1.0 if str(o["line"]) == l else 0.0)
        X.append(row)
        y.append(float(o["delta_log_s"]))

    # Normal equations: (X'X) beta = X'y
    XtX = [[0.0] * k for _ in range(k)]
    Xty = [0.0] * k
    for i in range(N):
        xi = X[i]
        yi = y[i]
        for r in range(k):
            Xty[r] += xi[r] * yi
            for c in range(r, k):
                val = xi[r] * xi[c]
                XtX[r][c] += val
                if r != c:
                    XtX[c][r] += val

    sol = _gauss_solve(XtX, Xty)
    if sol is None:
        return {
            "beta": NO_DATA_BETA,
            "n_observations": N,
            "is_real_estimate": False,
            "note": "Collinear design matrix, fallback to baseline.",
        }

    beta_est = round(sol[1], 3)
    if beta_est >= 0:
        return {
            "beta": NO_DATA_BETA,
            "raw_beta": beta_est,
            "n_observations": N,
            "is_real_estimate": False,
            "note": f"Estimated positive elasticity beta={beta_est} (economically invalid), fallback to {NO_DATA_BETA}.",
        }

    return {
        "beta": beta_est,
        "n_observations": N,
        "is_real_estimate": True,
        "note": f"OLS Fixed Effects estimated beta={beta_est} from {N} observation pairs.",
    }


def demand_curve(price: float, ms_baseline: float, price_ref: float, beta: float = -1.0) -> float:
    """Calculates expected demand at price point p based on elasticity beta."""
    if price <= 0 or price_ref <= 0 or ms_baseline <= 0:
        return 0.0
    try:
        ratio = price / price_ref
        return ms_baseline * math.pow(ratio, beta)
    except Exception:
        return 0.0


def decide_sku_pricing(
    item_id: str,
    name: str,
    orig_price: float,
    ms_baseline: float,
    elasticity_info: Dict[str, Any],
    current_discount_pct: float = 0.0,
) -> Dict[str, Any]:
    """Evaluates Hold / Mild / Flash sale scenarios for a given SKU."""
    beta = float(elasticity_info.get("beta", NO_DATA_BETA))
    is_real = bool(elasticity_info.get("is_real_estimate", False))

    if orig_price <= 0:
        return {
            "item_id": item_id,
            "name": name,
            "scenario": "hold",
            "discount_pct": 0.0,
            "expected_revenue_hold": 0.0,
            "expected_revenue_mild": 0.0,
            "expected_revenue_flash": 0.0,
            "elasticity_beta": beta,
            "confidence": "low",
            "used_fallback": True,
            "current_discount_pct": current_discount_pct,
        }

    p_hold = orig_price
    p_mild = orig_price * (1.0 - MILD_DISCOUNT / 100.0)
    p_flash = orig_price * (1.0 - min(FLASH_DISCOUNT, DISCOUNT_CAP_PCT) / 100.0)

    rev_hold = p_hold * demand_curve(p_hold, ms_baseline, orig_price, beta)
    rev_mild = p_mild * demand_curve(p_mild, ms_baseline, orig_price, beta)
    rev_flash = p_flash * demand_curve(p_flash, ms_baseline, orig_price, beta)

    # If fallback beta is used or confidence is low, default safely to hold
    if not is_real or ms_baseline <= 0:
        scenario = "hold"
        disc = 0.0
        conf = "low"
    else:
        conf = "high" if elasticity_info.get("n_observations", 0) >= 15 else "medium"
        if rev_flash > rev_mild * FLASH_MARGIN and rev_flash > rev_hold:
            scenario = "flash"
            disc = FLASH_DISCOUNT
        elif rev_mild > rev_hold:
            scenario = "mild"
            disc = MILD_DISCOUNT
        else:
            scenario = "hold"
            disc = 0.0

    return {
        "item_id": item_id,
        "name": name,
        "scenario": scenario,
        "discount_pct": disc,
        "expected_revenue_hold": round(rev_hold, 2),
        "expected_revenue_mild": round(rev_mild, 2),
        "expected_revenue_flash": round(rev_flash, 2),
        "elasticity_beta": beta,
        "confidence": conf,
        "used_fallback": not is_real,
        "current_discount_pct": current_discount_pct,
    }
