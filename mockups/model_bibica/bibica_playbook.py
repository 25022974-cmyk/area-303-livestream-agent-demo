"""
AI Livestream Strategist — Playbook generator cho Bibica (Shopee VN)
Chay: python bibica_playbook.py
Output: playbook_bibica.json + playbook_bibica.md

Dung 100% stdlib (khong pandas/numpy) de tranh xung dot inspect.py co san trong thu muc.
Data input:
  - dataset=products/shop_id=213989179/products.csv   (287 SKU)
  - pricing.json  (287 items Bibica)
  - daily.json    (item_daily Bibica)
"""
import csv, json, os, math, datetime, re
from collections import defaultdict, Counter
import bibica_methods as M  # M2b ham cung cau + M2c voucher

BASE = os.path.dirname(os.path.abspath(__file__))
SHOP_ID = "213989179"
SHOP_NAME = "Bibica Official Store"
SHOP_SLUG = "bibica-corporation"

# Tham so (co the sua)
BUDGET_VOUCHER_MONTH = 500_000_000   # VND/thang (that te: tong voucher that ~2.1B/thang -> 500M la 1/4)
ALPHA = 0.5    # he so thuong gia (tu docx)
BETA = 0.2     # he so phat min_spend (tu docx)
USE_DP_KNAPSACK = True  # True=DP day du, False=greedy

# ---------- helpers ----------
def to_float(v, default=0.0):
    if v is None or v == "" or v in ("None", "0", "0.0"):
        try:
            if v in ("0", "0.0"):
                return 0.0
        except Exception:
            pass
        return default
    try:
        return float(v)
    except Exception:
        return default

def ts_to_dt(s):
    try:
        if not s or s in ("", "None", "0", "0.0"):
            return None
        return datetime.datetime.fromtimestamp(float(s), tz=datetime.timezone.utc)
    except Exception:
        return None

def norm(values):
    """min-max normalize list -> [0,1]; luon 0 neu max==min"""
    if not values:
        return []
    mx = max(values); mn = min(values)
    if mx == mn:
        return [0.5 for _ in values]
    return [(v - mn) / (mx - mn) for v in values]

def fmt_money(v):
    try:
        return f"{int(round(v)):,}"
    except Exception:
        return str(v)

# ---------- load data ----------
def load_products():
    path = os.path.join(BASE, "dataset=products", f"shop_id={SHOP_ID}", "products.csv")
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    # dedup theo item_id: giu row co monthly_sold_value cao nhat (tranh snapshot trung)
    best = {}
    for r in rows:
        iid = r["item_id"]
        ms = to_float(r.get("monthly_sold_value"))
        if iid not in best or ms > to_float(best[iid].get("monthly_sold_value")):
            best[iid] = r
    return list(best.values())

def _load_raw_products():
    """Load tat ca rows (chua dedup) de estimate elasticity cross-time."""
    path = os.path.join(BASE, "dataset=products", f"shop_id={SHOP_ID}", "products.csv")
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def load_pricing_bibica():
    with open(os.path.join(BASE, "pricing.json"), encoding="utf-8") as f:
        d = json.load(f)
    return [it for it in d["items"] if it.get("shop") == "Bibica Official Store "]

def load_item_daily_bibica():
    with open(os.path.join(BASE, "daily.json"), encoding="utf-8") as f:
        d = json.load(f)
    return [it for it in d["item_daily"] if it["shop"] == "Bibica Official Store "]

# ---------- M1: SKU scoring ----------
def score_skus(products, daily_items):
    """Tra ve dict item_id -> {score, slow_mover, clearance, hero_ok, fields...}"""
    # build lookup daily sold trung binh
    daily_by_item = defaultdict(list)
    for it in daily_items:
        daily_by_item[it["item_id"]].append(to_float(it.get("daily_sold", 0)))
    avg_daily = {k: (sum(v)/len(v) if v else 0.0) for k, v in daily_by_item.items()}

    items = []
    for r in products:
        item_id = r["item_id"]
        ms = to_float(r.get("monthly_sold_value"))
        rc = to_float(r.get("rating_count"))
        rating = to_float(r.get("rating"), 4.5)
        liked = to_float(r.get("liked_count"))
        disc = to_float(r.get("discount_percent"))
        sold_out = str(r.get("is_sold_out")).lower() == "true"
        ctime = ts_to_dt(r.get("ctime"))
        age_days = (datetime.datetime(2026, 7, 3, tzinfo=datetime.timezone.utc) - ctime).days if ctime else 365
        # discount headroom: khoang cach toi nguong toi uu 35%
        headroom = max(0.0, 0.35 - disc / 100.0)
        items.append({
            "item_id": item_id,
            "name": r["product_name"],
            "price": to_float(r.get("price")),
            "orig": to_float(r.get("price_original")),
            "disc_pct": disc,
            "voucher": r.get("voucher_code") or "",
            "v_disc": to_float(r.get("voucher_discount")),
            "v_min": to_float(r.get("voucher_min_spend")),
            "ms": ms,
            "rc": rc,
            "rating": rating,
            "liked": liked,
            "sold_out": sold_out,
            "age_days": age_days,
            "discount_headroom": headroom,
            "avg_daily": avg_daily.get(item_id, 0.0),
            "url": r.get("url", f"https://shopee.vn/product/{SHOP_ID}/{item_id}"),
        })

    # normalize
    ms_n  = norm([i["ms"] for i in items])
    rc_n  = norm([i["rc"] for i in items])
    rt_n  = norm([i["rating"] for i in items])
    hd_n  = norm([i["discount_headroom"] for i in items])
    age_n = norm([-i["age_days"] for i in items])  # newer (negative age) -> higher
    like_n= norm([i["liked"] for i in items])

    thresh_slow = sorted(i["ms"] for i in items)[max(0, int(len(items)*0.20)-1)]

    for idx, i in enumerate(items):
        i["hero_score"] = round(0.30*ms_n[idx] + 0.25*rc_n[idx] + 0.15*rt_n[idx] + 0.15*hd_n[idx] + 0.15*age_n[idx], 4)
        i["live_affinity_proxy"] = round(like_n[idx], 4)
        i["slow_mover"] = (i["ms"] <= thresh_slow and i["ms"] > 0) or (i["ms"] == 0 and i["ms"] <= 0)
        i["slow_mover"] = i["ms"] <= thresh_slow
        i["clearance_candidate"] = i["slow_mover"] and not i["sold_out"]
        i["margin_unsafe"] = i["disc_pct"] >= 40  # nguong nghich doanh thu
    return items, thresh_slow

# ---------- M3: orchestrator ----------
PROMO_PRIOR = {
    "0":      (728,  "baseline, khong nen de mac dinh"),
    "10-19":  (1570, "hook: giu margin + hero tu nhien"),
    "20-29":  (1900, "core: lift manh"),
    "30-39":  (2509, "tipping -> da den nguong toi uu"),
    "40+":    (678,  "NGHICH doanh thu -> CAM"),
}

def build_playbook(items, thresh_slow, daily_items):
    # sort
    by_hero = sorted([i for i in items if not i["sold_out"]],
                     key=lambda x: x["hero_score"], reverse=True)

    hero = by_hero[0]
    core = [i for i in by_hero[1:6] if i["item_id"] != hero["item_id"]][:5]
    # clearance: slow movers khong sold_out, khong phai "QUÀ TẶNG KHÔNG BÁN", sort ms asc
    def is_real_product(i):
        nm = i["name"].upper()
        return "QUÀ TẶNG KHÔNG BÁN" not in nm and "QUA TANG KHONG BAN" not in nm
    clearance_pool = sorted([i for i in items if i["clearance_candidate"] and is_real_product(i)],
                            key=lambda x: x["ms"])
    clearance = clearance_pool[:3]
    # bundle: 1 core (kẹo) + 1 slow-mover non-critical (bánh) cross-category
    bundle = pick_bundle(items, hero, core, clearance)

    # price/promo grid per phase (ap dung tipping)
    def grid_for(i, role):
        cur_disc = i["disc_pct"]
        if role == "hook":
            target = min(max(cur_disc, 10), 19)
        elif role == "core":
            target = min(max(cur_disc, 20), 29)
        elif role == "bundle":
            target = 15
        elif role == "clearance":
            target = min(max(cur_disc, 25), 35)  # KHONG qua 39
        else:
            target = 0
        # price hieu qua
        if cur_disc and cur_disc > 0:
            base = i["orig"]
        else:
            base = i["orig"]
        eff_price = round(base * (1 - target/100.0))
        return {"target_disc_pct": target, "eff_price": eff_price,
                "current_disc": cur_disc, "orig": i["orig"]}

    phases = []
    # Phase 1: Hook
    g = grid_for(hero, "hook")
    phases.append({
        "phase": 1, "role": "hook",
        "skus": [short(hero)],
        "price_grid": g,
        "voucher": voucher_for(hero, g),
        "rationale": explain(hero, "hook", thresh_slow),
    })
    # Phase 2: Core
    core_grid = []
    for c in core:
        gc = grid_for(c, "core")
        core_grid.append({"sku": short(c), "grid": gc, "voucher": voucher_for(c, gc)})
    phases.append({
        "phase": 2, "role": "core",
        "skus": [short(c) for c in core],
        "grids": core_grid,
        "rationale": f"Top {len(core)} core theo hero_score; discount 20–29% (lift prior 1900). Voucher 17GIAM30K1 (min 50k) match.",
    })
    # Phase 3: Bundle
    phases.append({
        "phase": 3, "role": "bundle",
        "bundle": bundle,
        "price_grid": {"target_disc_pct": 15},
        "rationale": "Bundle cross-category (kẹo + bánh) tang AOV; discount 15% bundle.",
    })
    # Phase 4: Clearance
    clr_grid = []
    for c in clearance:
        gcl = grid_for(c, "clearance")
        clr_grid.append({"sku": short(c), "grid": gcl})
    phases.append({
        "phase": 4, "role": "clearance",
        "skus": [short(c) for c in clearance],
        "grids": clr_grid,
        "rationale": f"Slow-movers (ms <= {int(thresh_slow)}) flash 25–35%; KHONG vuot 40% (nghich doanh thu). Dọn kho.",
    })

    playbook = {
        "shop": SHOP_NAME,
        "shop_id": SHOP_ID,
        "shop_slug": SHOP_SLUG,
        "recommended_window": "T5 20:00–21:30 (prior: market_daily 2026-07-03 peak; verify sau)",
        "n_sku_total": len(items),
        "slow_mover_count": sum(1 for i in items if i["slow_mover"]),
        "promo_prior": [{"band": k, "mean_ms": v[0], "note": v[1]} for k, v in PROMO_PRIOR.items()],
        "phases": phases,
        "guardrails": [
            "Khong de xuat SKU discount >= 40% (nghich doanh thu - verified report).",
            "Khong hero khi is_sold_out.",
            "Clearance <= 35% de tranh vuot tipping.",
            "Prefer voucher non-overlap (v_state=active).",
            "Margin unsafe flag tuong duong disc>=40% (proxy, khong co cost that).",
        ],
        "caveats": [
            "Khong co data viewer/engagement live that - đo bang monthly_sold/daily_sold.",
            "daily.json chi 2 ngay -> daypart market prior, chua rieng Bibica.",
            "Khong margin/cost -> guardrail la proxy.",
            "Hero score heuristic, chua ML trained (can feedback loop 6-8 tuan).",
        ],
    }
    return playbook

def short(i):
    return {
        "item_id": i["item_id"],
        "name": i["name"],
        "price": i["price"],
        "orig": i["orig"],
        "disc_pct": i["disc_pct"],
        "ms": i["ms"],
        "rc": int(i["rc"]),
        "hero_score": i["hero_score"],
        "url": i["url"],
    }

def pick_bundle(items, hero, core, clearance):
    # don gian: 1 kẹo (word 'Kẹo') + 1 bánh (word 'Bánh') tu slow-movers hoac core
    keo = None; banh = None
    # uu tien core/slow-mover co ton kho
    pool = [i for i in items if not i["sold_out"]]
    for i in pool:
        nm = i["name"].lower()
        if not keo and "kẹo" in nm and i["hero_score"] > 0.3 and i["item_id"] != hero["item_id"]:
            keo = i
    for i in pool:
        nm = i["name"].lower()
        if not banh and "bánh" in nm and i["slow_mover"]:
            banh = i
    if keo and banh:
        return {"kẹo": short(keo), "bánh": short(banh)}
    # fallback
    return {"item_A": short(hero)}

def voucher_for(i, g):
    # voi grid moi, voucher hien co co con hop le?
    target_eff = g["eff_price"]
    if i["v_min"] and i["v_min"] > 0 and target_eff >= i["v_min"]:
        return {"code": i["voucher"], "discount": i["v_disc"], "min_spend": i["v_min"], "status": "applicable"}
    return {"code": "", "status": "no_active_voucher_for_new_price"}

def explain(i, role, thresh_slow):
    feats = []
    if i["ms"] > 0:
        feats.append(f"monthly_sold={int(i['ms'])}")
    feats.append(f"rating_count={int(i['rc'])}")
    feats.append(f"disc_hien={i['disc_pct']}%")
    feats.append(f"hero_score={i['hero_score']:.2f}")
    if role == "hook":
        return f"Hook vi {', '.join(feats)}; disc hien {i['disc_pct']}% con room toi tipping 30-39% (KHONG vuot 40%)."
    if role == "core":
        return f"Core vi {', '.join(feats)}; dua vao phase 2 voi discount 20-29% (lift prior 1900)."
    if role == "clearance":
        return f"Clearance vi ms={int(i['ms'])} <= {int(thresh_slow)} (slow-mover), KHONG sold_out; flash 25-35%."
    return ", ".join(feats)

# ---------- render markdown ----------
def to_markdown(pb):
    L = []
    L.append(f"# Playbook phiên sale kế tiếp — {pb['shop']}")
    L.append(f"**Shop:** {pb['shop']} (`{pb['shop_id']}`)  |  **slug:** {pb['shop_slug']}")
    L.append(f"**Cửa sổ khuyến nghị:** {pb['recommended_window']}")
    L.append(f"**Tổng SKU:** {pb['n_sku_total']}  |  **Slow-mover:** {pb['slow_mover_count']}")
    L.append("")
    L.append("## Promo depth prior (đã verify từ báo cáo)")
    L.append("| Band | mean monthly_sold | Ghi chú |")
    L.append("|---|---|---|")
    for p in pb["promo_prior"]:
        L.append(f"| {p['band']} | {p['mean_ms']} | {p['note']} |")
    L.append("")
    for ph in pb["phases"]:
        L.append(f"## Phase {ph['phase']} — {ph['role'].upper()}")
        if "skus" in ph:
            for s in ph["skus"]:
                L.append(f"- **{s['name']}**  |  item `{s['item_id']}`  |  giá {fmt_money(s['price'])}₫ (orig {fmt_money(s['orig'])}₫, -{s['disc_pct']}%)  |  ms={int(s['ms'])} rc={s['rc']}  |  hero={s['hero_score']}")
        if "price_grid" in ph:
            g = ph["price_grid"]
            L.append(f"  - Grid: target **-{g.get('target_disc_pct',0)}%**  →  eff price ≈ {fmt_money(g.get('eff_price',0))}₫")
        if "grids" in ph:
            for c in ph["grids"]:
                g = c["grid"]
                vstat = c.get("voucher", {}).get("status", "-") if isinstance(c.get("voucher"), dict) else "-"
                L.append(f"  - {c['sku']['name'][:50]}: target **-{g.get('target_disc_pct',0)}%** → {fmt_money(g.get('eff_price',0))}₫ | voucher: {vstat}")
        if "bundle" in ph:
            b = ph["bundle"]
            for k, v in b.items():
                L.append(f"- Bundle {k}: **{v['name']}** (item `{v['item_id']}`, {fmt_money(v['price'])}₫)")
        L.append(f"> **Lý giải:** {ph['rationale']}")
        L.append("")
    L.append("## Guardrails")
    for g in pb["guardrails"]:
        L.append(f"- {g}")
    L.append("")
    L.append("## Caveats")
    for c in pb["caveats"]:
        L.append(f"- ⚠️ {c}")
    return "\n".join(L)

# ---------- main ----------
def main():
    print("[load] products.csv ...")
    products = load_products()
    print(f"  rows: {len(products)}")
    print("[load] pricing.json Bibica ...")
    pricing = load_pricing_bibica()
    print(f"  rows: {len(pricing)}")
    print("[load] daily.json Bibica ...")
    daily = load_item_daily_bibica()
    print(f"  rows: {len(daily)}")

    print("[M1] scoring SKUs ...")
    items, thresh = score_skus(products, daily)
    top5 = sorted(items, key=lambda x: x["hero_score"], reverse=True)[:5]
    print(f"  slow-mover threshold ms <= {thresh:.0f}")
    for i in top5:
        print(f"  HERO {i['hero_score']:.3f} | ms={int(i['ms'])} rc={int(i['rc'])} disc={i['disc_pct']}% | {i['name'][:50]}")

    # ===== NHANH 1: HAM CUNG CAU (M2b) =====
    print("[M2b] ham cung cau -> ước lượng elasticity tu data ...")
    # dung TAT CA rows (chua dedup) de co nhieu diem cross-time cho elasticity
    all_rows = _load_raw_products()
    est_elastic = M.estimate_elasticity_from_data(all_rows)
    E = est_elastic["E"]
    print(f"  elasticity: E={E} ({est_elastic['note']}) - is_real_estimate={est_elastic['is_real_estimate']}")
    # tinh p* cho moi SKU
    for i in items:
        if i["ms"] > 0 and i["orig"] > 0:
            opt = M.find_optimal_price(i["orig"], i["ms"], elasticity=E, n_steps=100)
            i["opt_price"] = opt["best_price"]
            i["opt_disc_pct"] = opt["best_disc_pct"]
            i["opt_revenue"] = opt["best_revenue"]
            i["opt_demand"] = opt["best_demand"]
            # cap 35% (KHONG vuot tipping 39%)
            if i["opt_disc_pct"] > 35:
                i["opt_disc_pct_capped"] = 35
                i["opt_price_capped"] = round(i["orig"] * 0.65)
            else:
                i["opt_disc_pct_capped"] = i["opt_disc_pct"]
                i["opt_price_capped"] = i["opt_price"]
        else:
            i["opt_price"] = i["orig"]; i["opt_disc_pct"] = 0
            i["opt_revenue"] = 0; i["opt_demand"] = 0
            i["opt_disc_pct_capped"] = 0; i["opt_price_capped"] = i["orig"]
    h = max(items, key=lambda x: x["hero_score"])
    print(f"  Hero p*: {fmt_money(h['opt_price_capped'])} dur (-{h['opt_disc_pct_capped']}%), demand={h['opt_demand']:.0f}, E={E}")

    # ===== NHANH 2: VOUCHER (M2c - tu docx) =====
    print(f"[M2c] voucher knapsack (budget {fmt_money(BUDGET_VOUCHER_MONTH)}/thang) ...")
    def is_real_prod(i):
        nm = i["name"].upper()
        return not i["sold_out"] and "QUÀ TẶNG KHÔNG BÁN" not in nm and "QUA TANG KHONG BAN" not in nm
    cand = [{"item_id": i["item_id"], "name": i["name"], "orig_price": i["orig"],
             "monthly_sold": i["ms"]} for i in items if is_real_prod(i)]
    if USE_DP_KNAPSACK:
        knap = M.knapsack_voucher_dp(cand, BUDGET_VOUCHER_MONTH, ALPHA, BETA, scale=100000.0)
        # scale 100000 -> W = 5000 (budget 500M / 100k), DP nho va nhanh
    else:
        knap = M.knapsack_voucher(cand, BUDGET_VOUCHER_MONTH, ALPHA, BETA)
    print(f"  voucher: da dung {fmt_money(knap['used'])}/{fmt_money(knap['budget'])} | SKUs={knap['n_selected']} | est_sales sum={knap['total_est_sales']:.0f} | method={knap['method']}")

    print("[M3] building playbook ...")
    pb = build_playbook(items, thresh, daily)
    # gan them 2 nhanh vao playbook
    pb["supply_demand"] = {
        "elasticity_E": E,
        "is_real_estimate": est_elastic["is_real_estimate"],
        "elasticity_note": est_elastic["note"],
        "n_points_fit": est_elastic["n_points"],
        "hero_p_star": {"name": h["name"], "price": h["opt_price_capped"],
                        "disc_pct": h["opt_disc_pct_capped"], "demand": h["opt_demand"]},
    }
    pb["voucher_optimization"] = {
        "budget_month": knap["budget"], "used": knap["used"], "remaining": knap["remaining"],
        "n_selected": knap["n_selected"], "total_est_sales": knap["total_est_sales"],
        "method": knap["method"], "alpha": ALPHA, "beta": BETA,
        "selected": knap["selected"][:20],  # top 20 de file nho
    }
    pb["parameters"] = {"budget_voucher_month": BUDGET_VOUCHER_MONTH,
                         "alpha": ALPHA, "beta": BETA, "use_dp": USE_DP_KNAPSACK}
    pb["caveats"].extend([
        f"Elasticity E={E} la {'buoc that' if est_elastic['is_real_estimate'] else 'gia dinh -1'} "
        f"(fit {est_elastic['n_points']} diem cross-time snapshot).",
        f"Voucher method: budget {fmt_money(BUDGET_VOUCHER_MONTH)}/thang, alpha={ALPHA}, beta={BETA}. "
        f"Neu chay het voucher that se tieu {fmt_money(2_128_058_810)} (42x budget).",
        "estimated_sales la ước tinh (do hap dan) - KHONG phai so ban that.",
    ])

    out_json = os.path.join(BASE, "playbook_bibica.json")
    out_md = os.path.join(BASE, "playbook_bibica.md")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(pb, f, ensure_ascii=False, indent=2)
    with open(out_md, "w", encoding="utf-8") as f:
        f.write(to_markdown(pb))
    print(f"[done] wrote {out_json}")
    print(f"[done] wrote {out_md}")

if __name__ == "__main__":
    main()
