"""
Mo rong pipeline Bibica: them 2 phuong phap
  M2b - Dinh gia theo ham cung cau (supply-demand, tim gia toi uu)
  M2c - Phuong phap voucher (tu Phuong_phap_AI_toi_uu_voucher.docx):
        estimated_sales (do hap dan) + louri config + knapsack ngan sach

File nay la module, duoc bibica_playbook_v2.py import.
"""
import math
from collections import defaultdict

# ============ M2b: HAM CUNG CAU ============

# ---- Mo rong: estimate elasticity THAT tu cross-time signal ----
def estimate_elasticity_from_data(rows):
    """
    rows: list dict, moi row gom item_id, price (or price_before_promo), monthly_sold_value
    Cung item_id co nhieu dong (3 ngay snapshot) -> hoi quy log để ước E.
    Cau: demand ~ p^E  ->  log(demand) = E * log(p) + const.
    Giai bang Least Squares dong nhat:
        E = (N*sum(xy) - sum(x)*sum(y)) / (N*sum(x^2) - sum(x)^2)
    voi x = log(price), y = log(monthly_sold + 1)
    Tra ve {E, n_points, is_real_estimate, note}
    Chi dung items co >=2 (price, ms) khac nhau.
    """
    xs, ys = [], []
    for r in rows:
        try:
            p = float(r.get("price") or r.get("price_before_promo") or 0)
            ms = float(r.get("monthly_sold_value") or 0)
        except Exception:
            continue
        if p <= 0 or ms < 0:
            continue
        # log1p de tranh log(0)
        xs.append(math.log(p))
        ys.append(math.log1p(ms))
    n = len(xs)
    if n < 5:
        return {"E": -1.0, "n_points": n, "is_real_estimate": False,
                "note": "khong du diem, dung gia dinh E=-1"}
    sx = sum(xs); sy = sum(ys); sxx = sum(x*x for x in xs); sxy = sum(x*y for x,y in zip(xs,ys))
    denom = n*sxx - sx*sx
    if denom == 0:
        return {"E": -1.0, "n_points": n, "is_real_estimate": False,
                "note": "bien = 0, dung gia dinh"}
    E = (n*sxy - sx*sy) / denom
    # E hop ly cho duong cau phai am. Neu duong -> data loi/wen -> fallback
    if E >= 0:
        return {"E": -1.0, "n_points": n, "is_real_estimate": False,
                "note": f"E tinh = {E:.3f} (duong, vo ly) -> dung gia dinh -1"}
    return {"E": round(E, 3), "n_points": n, "is_real_estimate": True,
            "note": f"fit tu {n} diem, E={E:.3f}"}


def demand_curve(price, ms_baseline, price_ref, elasticity=-1.0):
    """
    Duong cau don gian: demand(p) = ms_baseline * (price/price_ref)^E
    E < 0 (elastic): gia tang -> demand giam
    """
    if price <= 0 or price_ref <= 0:
        return ms_baseline
    return ms_baseline * (price / price_ref) ** elasticity

def revenue_curve(price, ms_baseline, price_ref, elasticity=-1.0):
    """revenue = price * demand"""
    return price * demand_curve(price, ms_baseline, price_ref, elasticity)

def find_optimal_price(orig_price, ms_baseline, elasticity=-1.0,
                       n_steps=100, p_floor=None):
    """
    Quet gia tu (orig*0.5) -> (orig*1.0) tim revenue max.
    Tra ve {best_price, best_revenue, best_demand, best_disc_pct}
    p_floor: gia san (vd cost) - khong di duoi.
    """
    lo = orig_price * 0.5
    hi = orig_price
    if p_floor:
        lo = max(lo, p_floor)
    best = None
    for i in range(n_steps + 1):
        p = lo + (hi - lo) * i / n_steps
        d = demand_curve(p, ms_baseline, orig_price, elasticity)
        r = p * d
        if best is None or r > best["best_revenue"]:
            best = {
                "best_price": round(p),
                "best_revenue": r,
                "best_demand": d,
                "best_disc_pct": round((1 - p / orig_price) * 100, 1),
            }
    return best

def profit_curve(price, ms_baseline, price_ref, cost, elasticity=-1.0):
    """Neu co cost: profit = (price - cost) * demand"""
    return (price - cost) * demand_curve(price, ms_baseline, price_ref, elasticity)

def find_optimal_price_profit(orig_price, ms_baseline, cost, elasticity=-1.0, n_steps=100):
    """Tim price max profit (neu co cost)."""
    lo = max(cost, orig_price * 0.5)
    hi = orig_price
    best = None
    for i in range(n_steps + 1):
        p = lo + (hi - lo) * i / n_steps
        pr = profit_curve(p, ms_baseline, orig_price, cost, elasticity)
        if best is None or pr > best["best_profit"]:
            best = {
                "best_price": round(p),
                "best_profit": pr,
                "best_demand": demand_curve(p, ms_baseline, orig_price, elasticity),
                "best_disc_pct": round((1 - p / orig_price) * 100, 1),
                "margin_pct": round((p - cost) / p * 100, 1) if p > 0 else 0,
            }
    return best


# ============ M2c: VOUCHER METHOD (tu docx) ============
# Ký hiệu theo docx:
#   A = price - voucher_discount        (gia thuc tra)
#   B = price_original - A              (muc giam vs goc)
#   C = voucher_min_spend               (do de xai voucher)
def estimated_sales(monthly_sold, price, voucher_disc, price_original, voucher_min_spend,
                    alpha=0.5, beta=0.2):
    """
    estimated_sales = ms * (1 + alpha*B/orig - beta*C/200000)
    """
    A = price - voucher_disc
    B = price_original - A
    C = voucher_min_spend or 0
    if price_original <= 0:
        return monthly_sold
    factor = 1 + alpha * (B / price_original) - beta * (C / 200000.0)
    factor = max(0.0, factor)  # khong am
    return monthly_sold * factor

def voucher_cost_per_sku(voucher_disc, est_sales):
    """Chi phi voucher 1 SKU = voucher_disc * estimated_sales"""
    return voucher_disc * est_sales

def gen_config_grid(orig_price):
    """
    Luoi cau hinh theo docx:
      discount: [0,5,10,15,20,25,30] %
      voucher:  [0,10k,20k,30k,40k,50k] VND
      min_spend: [50,100,150,200] k VND
    Tra ve list dict config.
    """
    discs = [0, 5, 10, 15, 20, 25, 30]
    vouchers = [0, 10000, 20000, 30000, 40000, 50000]
    mins = [50000, 100000, 150000, 200000]
    cfgs = []
    for d in discs:
        price = round(orig_price * (1 - d / 100.0))
        for v in vouchers:
            for mn in mins:
                cfgs.append({
                    "disc_pct": d, "price": price,
                    "voucher_disc": v, "min_spend": mn,
                })
    return cfgs  # 7*6*4 = 168 config

def evaluate_configs(monthly_sold, orig_price, alpha=0.5, beta=0.2):
    """Cho 1 SKU: tinh estimated_sales + voucher_cost cho 168 config."""
    cfgs = gen_config_grid(orig_price)
    for c in cfgs:
        es = estimated_sales(monthly_sold, c["price"], c["voucher_disc"],
                             orig_price, c["min_spend"], alpha, beta)
        c["estimated_sales"] = es
        c["voucher_cost"] = voucher_cost_per_sku(c["voucher_disc"], es)
    return cfgs

# ---- Knapsack ngan sach voucher ----
def knapsack_voucher(skus, budget, alpha=0.5, beta=0.2):
    """
    skus: list {item_id, name, orig_price, monthly_sold}
    Moi SKU chon 1 config tot nhat (max estimated_sales) - greedy don gian:
      voi moi SKU, lay config co estimated_sales cao nhat (max 1/SKU).
    Roi sort theo (est_sales voucher_efficiency = est_sales / voucher_cost) desc,
    chon dung bat ky khi nao tong voucher_cost <= budget.

    Luu y: day la GREEDY khong phai optimal knapsack 0/1 day du; dam bao de hieu.
    Tra ve: list selected {item_id, disc_pct, voucher_disc, min_spend, est_sales, vcost}
    """
    # moi sku: best config
    candidates = []
    for s in skus:
        cfgs = evaluate_configs(s["monthly_sold"], s["orig_price"], alpha, beta)
        # chon config co estimated_sales cao nhat (gioi han disc <= 35% de on tipping)
        cfgs = [c for c in cfgs if c["disc_pct"] <= 35]
        if not cfgs:
            continue
        best = max(cfgs, key=lambda c: c["estimated_sales"])
        candidates.append({
            "item_id": s["item_id"], "name": s["name"],
            "orig_price": s["orig_price"], "monthly_sold": s["monthly_sold"],
            "disc_pct": best["disc_pct"], "price": best["price"],
            "voucher_disc": best["voucher_disc"], "min_spend": best["min_spend"],
            "est_sales": best["estimated_sales"], "vcost": best["voucher_cost"],
        })
    # sort theo hieu qua voucher (est_sales / max(vcost,1)) desc
    candidates.sort(key=lambda c: c["est_sales"] / max(c["vcost"], 1.0), reverse=True)
    # chon cho den khi het budget
    selected = []
    total_v = 0.0
    total_sales = 0.0
    for c in candidates:
        if total_v + c["vcost"] <= budget:
            selected.append(c)
            total_v += c["vcost"]
            total_sales += c["est_sales"]
    return {
        "budget": budget, "used": total_v, "remaining": budget - total_v,
        "total_est_sales": total_sales, "n_selected": len(selected),
        "selected": selected,
        "method": "greedy",
    }


# ---- Knapsack DP day du (0/1, gia tri gather) ----
def knapsack_voucher_dp(skus, budget, alpha=0.5, beta=0.2, scale=1000.0):
    """
    Version DP满满 đủ hon: voi moi SKU giu tat ca config (168), cho DP chon.
    De giam tinh toan: bo config có estimated_sales <= 0 hoac disc > 39%.
    Viet chi phí voucher theo don vi `scale` (vd 1000d) lam integer cho DP.
    Moi SKU chi duoc chon TOI DA 1 config (0/1 theo item).
    Tra ve: {selected, used, remaining, total_est_sales, method:'dp'}
    """
    # Build items: (item_idx, cfg_dict, value, weight)
    item_groups = []  # list of list of (value, weight, cfg, sku)
    for s in skus:
        cfgs = evaluate_configs(s["monthly_sold"], s["orig_price"], alpha, beta)
        cfgs = [c for c in cfgs if c["disc_pct"] <= 39 and c["estimated_sales"] > 0]
        if not cfgs:
            continue
        # de giam: giu top 5 config/SKU theo est_sales
        cfgs.sort(key=lambda c: c["estimated_sales"], reverse=True)
        cfgs = cfgs[:5]
        group = []
        for c in cfgs:
            val = c["estimated_sales"]
            w = int(round(c["voucher_cost"] / scale))
            group.append((val, w, c, s))
        item_groups.append(group)
    if not item_groups:
        return {"budget": budget, "used": 0, "remaining": budget,
                "total_est_sales": 0, "n_selected": 0, "selected": [], "method": "dp"}
    W = int(budget / scale)
    # DP: multiple-choice knapsack (moi SKU = 1 nhom, chon toi da 1 config)
    # dp[w] = (max_value, picks)  picks = tuple gom (group_idx, choice_idx)
    dp = {0: (0.0, ())}
    for gi, group in enumerate(item_groups):
        ndp = {}
        for w, (val, picks) in dp.items():
            # choice: khong chon SKU nay
            if w not in ndp or val > ndp[w][0]:
                ndp[w] = (val, picks)
            # choice: chon 1 config cua group
            for ci, (v, wt, cfg, s) in enumerate(group):
                nw = w + wt
                if nw > W:
                    continue
                nv = val + v
                if nw not in ndp or nv > ndp[nw][0]:
                    ndp[nw] = (nv, picks + ((gi, ci),))
        dp = ndp
    # Lay ket qua best
    best_w = max(dp, key=lambda w: dp[w][0])
    best_val, best_picks = dp[best_w]
    # khoi phuc selected
    gi_cfg = {}
    for gi, ci in best_picks:
        gi_cfg.setdefault(gi, ci)
    selected = []
    for gi, ci in gi_cfg.items():
        s, cfg = item_groups[gi][ci][3], item_groups[gi][ci][2]
        selected.append({
            "item_id": s["item_id"], "name": s["name"],
            "orig_price": s["orig_price"], "monthly_sold": s["monthly_sold"],
            "disc_pct": cfg["disc_pct"], "price": cfg["price"],
            "voucher_disc": cfg["voucher_disc"], "min_spend": cfg["min_spend"],
            "est_sales": cfg["estimated_sales"], "vcost": cfg["voucher_cost"],
        })
    used = sum(x["vcost"] for x in selected)
    total_sales = sum(x["est_sales"] for x in selected)
    # fit budget: bo phan vuot (do scale, DP co the vuot nhe)
    while selected and used > budget:
        # bo SKU co hieu qua thap nhat (est_sales/vcost)
        selected.sort(key=lambda c: c["est_sales"] / max(c["vcost"], 1), reverse=True)
        removed = selected.pop()
        used -= removed["vcost"]; total_sales -= removed["est_sales"]
    return {
        "budget": budget, "used": used, "remaining": budget - used,
        "total_est_sales": total_sales, "n_selected": len(selected),
        "selected": selected, "method": "dp",
    }
