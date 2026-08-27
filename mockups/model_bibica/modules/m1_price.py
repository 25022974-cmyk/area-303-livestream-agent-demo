"""
Module 1 — Quyết định giá: GIỮ / GIẢM NHẸ / FLASH SALE
=====================================================

Contract theo DELIVERABLE_SPEC.md (Module 1).

Câu trả lời: SKU nên giữ giá hay giảm, bao nhiêu %?

Hai thành phần:

(A) estimate_elasticity_with_fe(rows)
    Hồi quy log-log OLS *fixed effects* (stdin thuần, không numpy/sklearn):

        log(Δsold) = β·log(Δprice) + Σ_k γ_k·shop_fe[shop_id=k]
                                  + Σ_l δ_l·cat_fe[line_or_catid=l] + ε

    - shop_fe: dummy shop_id (10 shop) -> tách đặc thù shop.
    - cat_fe:  dummy line_or_catid (Zoo/Quasure/Gooka/Sumika cho Bibica,
              catid thật cho 9 đối thủ) -> tách nhiễu ngành (DiD đơn giản).
    - β = độ co giãn giá RIÊNG Bibica sau khi kể shop & ngành.
    - Input: danh sách observation = mỗi cặp (shop, item, ngày t, ngày t-1)
             mà price đổi giữa 2 ngày -> ghi (Δlog price, Δlog sold, shop_id, line).

    OLS giải bằng khử Gauss-Jordan trên ma trận thường (X'X) β = X'y.
    Stdlib: chỉ dùng math + list. ~50 dòng.

    Fallback: nếu < MIN_POINTS điểm, hoặc β >= 0 (vô lý), trả β = NO_DATA_BETA (-1.0)
    và used_fallback=True (giữ đúng hành vi bibica_methods.estimate_elasticity_from_data).

(B) decide(sku, beta)
    So 3 kịch bản:
      - hold:     discount 0%
      - mild:     discount 10% (trong khoảng 10-15)
      - flash:    discount 25% (≥25%)
    Tính doanh thu kỳ vọng ở mỗi mức qua demand_curve(revenue = price * demand),
    chọn kịch bản doanh thu cao nhất, kẹp trong cap 36% (cao nhất Bibica từng thấy).
    Flash sale chỉ chọn nếu expected_revenue_flash > expected_revenue_mild
    + biên an toàn FLASH_MARGIN.

Output mỗi SKU Bibica: contract JSON giống DELIVERABLE_SPEC mục B/Module 1.
"""
import math
from typing import List, Dict, Any, Optional, Tuple

# ---- tham số (lấy từ đề bài) ----
MIN_POINTS = 5                 # đủ điểm mới ước β thật
NO_DATA_BETA = -1.0             # fallback elasticity khi thiếu data
DISCOUNT_CAP_PCT = 36.0         # cao nhất Bibica từng thấy (data: max=36, median=19)
MILD_DISCOUNT = 10.0            # giảm nhẹ (10-15%)
FLASH_DISCOUNT = 25.0           # flash sale (≥25%)
FLASH_MARGIN = 1.03             # flash phải > mild 3% doanh thu mới được chọn


# =====================================================================
# (A) OLS FIXED EFFECTS — stdlib thuần
# =====================================================================

def _gauss_solve(A: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """
    Giải hệ A x = b bằng khử Gauss-Jordan với partial pivoting.
    A: n×n (list of lists), b: n. Trả nghiệm list hoặc None (singular).
    Thuần stdlib, không numpy.
    """
    n = len(A)
    # bản sao ma trận mở rộng [A | b]
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for col in range(n):
        # pivoting: chọn hàng có |A[i][col]| lớn nhất từ col..n-1
        piv = max(range(col, n), key=lambda i: abs(M[i][col]))
        if abs(M[piv][col]) < 1e-12:
            return None  # singular
        if piv != col:
            M[col], M[piv] = M[piv], M[col]
        # khử các hàng khác
        pivval = M[col][col]
        for r in range(n):
            if r == col:
                continue
            factor = M[r][col] / pivval
            if factor == 0.0:
                continue
            for c in range(col, n + 1):
                M[r][c] -= factor * M[col][c]
    # rút nghiệm
    return [M[i][n] / M[i][i] for i in range(n)]


def _xtx_xty(X: List[List[float]], y: List[float]) -> Tuple[List[List[float]], List[float]]:
    """Tính X'X và X'y. X: m×n, y: m. Trả (XtX n×n, Xty n)."""
    m, n = len(X), len(X[0])
    XtX = [[0.0] * n for _ in range(n)]
    Xty = [0.0] * n
    for i in range(m):
        xi, yi = X[i], y[i]
        for a in range(n):
            Xty[a] += xi[a] * yi
            xa = xi[a]
            row = XtX[a]
            for b in range(a, n):
                row[b] += xa * xi[b]
    # đối xứng
    for a in range(n):
        for b in range(a):
            XtX[a][b] = XtX[b][a]
    return XtX, Xty


def estimate_elasticity_with_fe(observations: List[Dict[str, Any]],
                                ridge_lambda: float = 1e-6) -> Dict[str, Any]:
    """
    Hồi quy log-log OLS fixed effects.

    observations: mỗi dict có:
        dlog_price : float   (log(price_t) - log(price_{t-1}))
        dlog_sold  : float   (log(sold_t+1) - log(sold_{t-1}+1))  -- log1p để tránh log 0
        shop_id    : str/int
        line       : str     (Zoo/Quasure/Gooka/Sumika cho Bibica, catid thật cho đối thủ)

    Trả:
        {
          "beta": float,           # độ co giãn giá (âm = co giãn bình thường)
          "n_points": int,
          "is_real_estimate": bool,
          "n_shops": int, "n_lines": int,
          "note": str
        }
    """
    rows = [o for o in observations
            if o.get("dlog_price") is not None and o.get("dlog_sold") is not None
            and o.get("shop_id") is not None and o.get("line")]
    n = len(rows)
    if n < MIN_POINTS:
        return {"beta": NO_DATA_BETA, "n_points": n, "is_real_estimate": False,
                "n_shops": 0, "n_lines": 0,
                "note": f"khong du diem ({n}<{MIN_POINTS}), dung fallback β={NO_DATA_BETA}"}

    # ánh xạ shop_id / line -> index dummy
    shop_ids = sorted({str(r["shop_id"]) for r in rows})
    lines = sorted({str(r["line"]) for r in rows})
    # rớt 1 cấp mỗi nhóm (baseline) để tránh multi-collinearity hoàn toàn
    shop_levels = shop_ids[:-1]
    line_levels = lines[:-1]

    # cột: [intercept, log(Δprice), shop_fe..., cat_fe...]
    ncol = 1 + 1 + len(shop_levels) + len(line_levels)
    smap = {s: i for i, s in enumerate(shop_levels)}
    lmap = {l: i for i, l in enumerate(line_levels)}

    X, y = [], []
    for r in rows:
        xrow = [1.0, float(r["dlog_price"])]
        for s in shop_levels:
            xrow.append(1.0 if str(r["shop_id"]) == s else 0.0)
        for l in line_levels:
            xrow.append(1.0 if str(r["line"]) == l else 0.0)
        X.append(xrow)
        y.append(float(r["dlog_sold"]))

    XtX, Xty = _xtx_xty(X, y)
    # Ridge nhẹ (đường chéo λ) để tránh ma trận suy biến khi dummies spare quá nhiều
    # so với observation có Δprice (cache tuần Shopee). KHÔNG bias intercept.
    if ridge_lambda > 0:
        for i in range(1, ncol):  # bỏ intercept (index 0)
            XtX[i][i] += ridge_lambda
    sol = _gauss_solve(XtX, Xty)
    if sol is None:
        return {"beta": NO_DATA_BETA, "n_points": n, "is_real_estimate": False,
                "n_shops": len(shop_ids), "n_lines": len(lines),
                "note": "ma tran suy bien (X'X singular), dung fallback"}

    beta = sol[1]  # cột thứ 1 = log(price)
    if beta >= 0:
        # β ≥ 0 vô lý với đường cầu (giá tăng cầu cũng tăng) -> nhiễu/cache
        return {"beta": NO_DATA_BETA, "n_points": n, "is_real_estimate": False,
                "n_shops": len(shop_ids), "n_lines": len(lines),
                "note": f"β tính = {beta:.3f} (≥0, vo ly) -> fallback {NO_DATA_BETA}"}
    return {"beta": round(beta, 3), "n_points": n, "is_real_estimate": True,
            "n_shops": len(shop_ids), "n_lines": len(lines),
            "note": f"fit tu {n} diem, β={beta:.3f}, {len(shop_ids)} shop, {len(lines)} line"}


# =====================================================================
# (B) QUYẾT ĐỊNH: GIỮ / MILD / FLASH
# =====================================================================

def demand_curve(price: float, ms_baseline: float, price_ref: float,
                 elasticity: float) -> float:
    """demand(p) = ms * (p/p_ref)^β, β<0."""
    if price <= 0 or price_ref <= 0:
        return ms_baseline
    return ms_baseline * (price / price_ref) ** elasticity


def expected_revenue(discount_pct: float, orig_price: float, ms_baseline: float,
                     elasticity: float) -> float:
    """Doanh thu kỳ vọng ở một mức giảm. price = orig*(1-discount/100)."""
    price = orig_price * (1 - discount_pct / 100.0)
    d = demand_curve(price, ms_baseline, orig_price, elasticity)
    return price * d


def decide_sku(item_id: str, name: str, orig_price: float, ms_baseline: float,
               elasticity_info: Dict[str, Any], current_discount_pct: float = 0.0) -> Dict[str, Any]:
    """
    So 3 kịch bản, chọn doanh thu kỳ vọng cao nhất (kẹp cap 36%).

    Trả contract Module 1:
      {
        item_id, scenario {'hold'|'mild'|'flash'}, discount_pct,
        expected_revenue_hold, expected_revenue_mild, expected_revenue_flash,
        elasticity_beta, confidence, used_fallback
      }
    """
    beta = elasticity_info.get("beta", NO_DATA_BETA)
    is_real = bool(elasticity_info.get("is_real_estimate", False))
    used_fallback = not is_real

    r_hold = expected_revenue(0.0, orig_price, ms_baseline, beta)
    r_mild = expected_revenue(MILD_DISCOUNT, orig_price, ms_baseline, beta)
    r_flash = expected_revenue(FLASH_DISCOUNT, orig_price, ms_baseline, beta)

    # QUY ƯỚC AN TOÀN (chốt 2026-08-24):
    # Khi không đủ data ước β chính xác (confidence low / fallback), KHÔNG đề xuất
    # giảm giá dựa trên dữ liệu mơ hồ -> ép hold. Vẫn báo cáo 3 doanh thu kỳ vọng
    # để dashboard hiển thị, nhưng scenario luôn = hold.
    if used_fallback:
        scenario, chosen_disc = "hold", 0.0
    elif r_flash > r_mild * FLASH_MARGIN:
        scenario, chosen_disc = "flash", FLASH_DISCOUNT
    elif r_mild > r_hold:
        scenario, chosen_disc = "mild", MILD_DISCOUNT
    else:
        scenario, chosen_disc = "hold", 0.0

    # kẹp cap: nếu kịch bản chọn vượt cap, đưa về cap (flash 25 < 36 nên safe;
    # nhưng vẫn chốt để an toàn nếu MILD/FLASH đổi threshold)
    if chosen_disc > DISCOUNT_CAP_PCT:
        chosen_disc = DISCOUNT_CAP_PCT
        scenario = "flash" if chosen_disc >= FLASH_DISCOUNT else "mild"

    # Confidence:
    #  - high: ước β thật + đủ điểm + β đủ âm (co giãn mạnh)
    #  - medium: ước β thật nhưng sát 0 (co giãn yếu)
    #  - low: dùng fallback
    if used_fallback:
        confidence = "low"
    elif beta < -1.5:
        confidence = "high"
    elif beta < -0.8:
        confidence = "medium"
    else:
        confidence = "medium"

    return {
        "item_id": item_id,
        "name": name,
        "scenario": scenario,
        "discount_pct": round(chosen_disc, 1),
        "expected_revenue_hold": round(r_hold, 2),
        "expected_revenue_mild": round(r_mild, 2),
        "expected_revenue_flash": round(r_flash, 2),
        "elasticity_beta": beta,
        "confidence": confidence,
        "used_fallback": used_fallback,
        "current_discount_pct": current_discount_pct,
    }


# =====================================================================
# BUILD OBSERVATIONS TỪ DATA POOL (helper cho pipeline)
# =====================================================================

def build_observations(snapshots: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Chuyển snapshot/SKU theo ngày thành observation Δgiá/Δsold.

    snapshots: list dict mỗi dòng = 1 SKU 1 ngày, có:
        shop_id, item_id, line, date (sortable str), price (>0), monthly_sold_value (>=0)

    Trả observation cho estimate_elasticity_with_fe:
        {dlog_price, dlog_sold, shop_id, line}

    Quy tắc (theo đề bài Step 1): mỗi lần price HOẶC discount đổi giữa 2 ngày liên tiếp
    -> 1 quan sát. Ở đây dùng price (đơn giản, đủ cho elasticity); nếu không đổi price
    thì Δlog_price=0 -> không đóng góp β -> vẫn đưa vào cho fixed effects (intercept).
    Nhưng để β sạch, chỉ giữ cặp Δprice != 0.
    """
    # gom theo (shop_id, item_id), sắp theo date
    by_key: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for s in snapshots:
        try:
            p = float(s.get("price") or 0)
            ms = float(s.get("monthly_sold_value") or 0)
        except (TypeError, ValueError):
            continue
        if p <= 0 or ms < 0:
            continue
        key = (str(s.get("shop_id")), str(s.get("item_id")))
        by_key.setdefault(key, []).append({
            "date": s.get("date", ""),
            "price": p, "monthly_sold_value": ms,
            "line": str(s.get("line") or "Unknown"),
            "discount_percent": float(s.get("discount_percent") or 0),
        })
    obs = []
    for (shop_id, item_id), recs in by_key.items():
        if len(recs) < 2:
            continue
        recs.sort(key=lambda r: r["date"])
        for i in range(1, len(recs)):
            a, b = recs[i - 1], recs[i]
            if a["price"] <= 0 or b["price"] <= 0:
                continue
            dlp = math.log(b["price"]) - math.log(a["price"])
            dls = math.log1p(b["monthly_sold_value"]) - math.log1p(a["monthly_sold_value"])
            # theo đề bài: chỉ giữ cặp price HOẶC discount đổi
            if dlp == 0.0 and b["discount_percent"] == a["discount_percent"]:
                continue
            obs.append({
                "dlog_price": dlp,
                "dlog_sold": dls,
                "shop_id": shop_id,
                "line": b["line"],
            })
    return obs


# =====================================================================
# SELF-TEST / DEMO (chạy file để smoke test)
# =====================================================================
if __name__ == "__main__":
    # 1) test OLS: y = -2*x + noise, fixed effects -> phải thu beta ~ -2
    import random as _r
    _r.seed(7)
    shops = ["S1", "S2", "S3"]
    lines = ["Zoo", "Quasure"]
    test_obs = []
    for shop in shops:
        for line in lines:
            for _ in range(8):
                dlp = _r.uniform(-0.4, 0.4)
                base = {"S1": 0.1, "S2": -0.05, "S3": 0.2}[shop]
                base += {"Zoo": 0.0, "Quasure": 0.15}[line]
                dls = -2.0 * dlp + base + _r.gauss(0, 0.05)  # β = -2 + nhiễu
                test_obs.append({"dlog_price": dlp, "dlog_sold": dls,
                                 "shop_id": shop, "line": line})
    res = estimate_elasticity_with_fe(test_obs)
    print("[OLS fixed-effects test]")
    print(f"  expected beta ~ -2.0 | got beta = {res['beta']}, "
          f"real={res['is_real_estimate']}, n={res['n_points']}, "
          f"shops={res['n_shops']}, lines={res['n_lines']}")
    print(f"  note: {res['note']}")
    assert res["is_real_estimate"] and abs(res["beta"] - (-2.0)) < 0.3, "OLS sai kha"

    # 2) test decide_sku: SKU co giãn (β=-1.8) -> flash co doanh thu cao nhat
    ei = {"beta": -1.8, "is_real_estimate": True}
    out = decide_sku("X", "Kẹo test", orig_price=43000, ms_baseline=200,
                     elasticity_info=ei, current_discount_pct=19)
    print("\n[decide test] elastic β=-1.8, orig 43k, ms 200:")
    for k in ["scenario", "discount_pct", "expected_revenue_hold",
              "expected_revenue_mild", "expected_revenue_flash", "confidence"]:
        print(f"  {k}: {out[k]}")

    # 3) fallback: β=-1 (no data) -> flash van duoc chon (revenue tang khi giam gia)
    ei2 = {"beta": NO_DATA_BETA, "is_real_estimate": False}
    out2 = decide_sku("Y", "SKU khong data", orig_price=43000, ms_baseline=200,
                      elasticity_info=ei2)
    print(f"\n[fallback test] used_fallback={out2['used_fallback']}, "
          f"confidence={out2['confidence']}, scenario={out2['scenario']}")
    assert out2["scenario"] == "hold", "fallback phai ep hold"

    print("\n✓ m1_price smoke test OK")
