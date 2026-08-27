/* ============================================================
   AREA_303 — JS chung (dùng cho cả 3 trang)
   - Helpers: format VND, normalize, hero-score tính client-side
     (model_input.json chưa chứa hero_score; tái tạo logic từ
     bibica_playbook.py score_skus() để UI có score ngay)
   -.localStorage lưu state phiên live (draft)
   ============================================================ */
(function () {
  "use strict";

  const DATA = window.AREA303_DATA || { products: [], pricing: [], daily: [], playbook: null, meta: {} };

  /* ---------- format helpers ---------- */
  function vnd(n) {
    n = Number(n || 0);
    if (Math.abs(n) >= 1e6) return (n / 1e6).toFixed(2).replace(/\.00$/, "") + "M ₫";
    if (Math.abs(n) >= 1e3) return Math.round(n / 1000) + "k ₫";
    return Math.round(n).toLocaleString("vi-VN") + " ₫";
  }
  function num(n) { return Math.round(Number(n || 0)).toLocaleString("vi-VN"); }
  function pct(n) { return (Number(n || 0)).toFixed(1).replace(/\.0$/, "") + "%"; }
  function clamp01(x) { return Math.max(0, Math.min(1, x)); }
  function ageDays(ctime) {
    // model_base date 2026-07-03 în playbook.py
    const base = Date.UTC(2026, 6, 3);
    let c = Number(ctime);
    if (!c) return 365;
    return Math.max(0, Math.floor((base - c * 1000) / 86400000));
  }

  /* ---------- normalize / score (mirror của score_skus) ---------- */
  function norm(vals) {
    if (!vals.length) return [];
    const mx = Math.max(...vals), mn = Math.min(...vals);
    if (mx === mn) return vals.map(() => 0.5);
    return vals.map(v => (v - mn) / (mx - mn));
  }
  function buildScoredItems() {
    const prods = DATA.products || [];
    // pricing en rich:rapid lookup theo item_id (ms/rc có thể thiếu trong product)
    const px = {};
    (DATA.pricing || []).forEach(p => { px[p.item_id] = p; });
    // daily avg_daily
    const dailyByItem = {};
    (DATA.daily || []).forEach(d => {
      (dailyByItem[d.item_id] = dailyByItem[d.item_id] || []).push(Number(d.daily_sold || 0));
    });

    const items = prods.map(r => {
      const iid = r.item_id;
      const ms = Number(r.monthly_sold_value || 0);
      const rc = Number(r.rating_count || 0);
      const rating = Number(r.rating || 4.5);
      const liked = Number(r.liked_count || 0);
      const disc = Number(r.discount_percent || 0);
      const soldOut = String(r.is_sold_out || "").toLowerCase() === "true";
      const headroom = Math.max(0, 0.35 - disc / 100);
      const ad = dailyByItem[iid] || [];
      const avgDaily = ad.length ? ad.reduce((a, b) => a + b, 0) / ad.length : 0;
      const nm = (r.product_name || "").toUpperCase();
      const isGift = nm.includes("QUÀ TẶNG KHÔNG BÁN") || nm.includes("QUA TANG KHONG BAN");
      // line gợi ý từ tên được phân loại lại theo yêu cầu loại sản phẩm (không dùng tên riêng thương hiệu)
      let line = "Khác";
      const N = (r.product_name || "").normalize("NFC").toLowerCase();
      if (
        N.includes("quasure") ||
        N.includes("ăn kiêng") ||
        N.includes("không đường") ||
        N.includes("ít đường") ||
        N.includes("sugar free") ||
        N.includes("no sugar") ||
        N.includes("giảm đường") ||
        N.includes("giảm 40% đường")
      ) {
        line = "Ăn kiêng / Ít đường";
      } else if (
        N.includes("bánh ăn sáng") ||
        N.includes("bánh tươi olive") ||
        N.includes("bánh mì") ||
        N.includes("sandwich") ||
        N.includes("chà bông") ||
        N.includes("olive")
      ) {
        line = "Bánh ăn sáng";
      } else if (
        N.includes("kẹo") ||
        N.includes("thạch") ||
        N.includes("zoo") ||
        N.includes("sumika") ||
        N.includes("cheery") ||
        N.includes("welly") ||
        N.includes("migita") ||
        N.includes("michoco") ||
        N.includes("tứ quý")
      ) {
        line = "Kẹo";
      } else if (
        N.includes("bánh") ||
        N.includes("gooka") ||
        N.includes("hura") ||
        N.includes("goody") ||
        N.includes("jamy") ||
        N.includes("cookies") ||
        N.includes("cracker") ||
        N.includes("bông lan") ||
        N.includes("cuộn") ||
        N.includes("swissroll") ||
        N.includes("layercake") ||
        N.includes("ngũ cốc") ||
        N.includes("bột ngũ cốc")
      ) {
        line = "Bánh";
      }

      return {
        item_id: iid,
        name: r.product_name,
        price: Number(r.price || 0),
        orig: Number(r.price_original || 0),
        disc_pct: disc,
        ms, rc, rating, liked, sold_out: soldOut, is_gift: isGift, line,
        is_combo: N.includes("combo"),
        age_days: ageDays(r.ctime),
        discount_headroom: headroom,
        avg_daily: avgDaily,
        url: r.url || `https://shopee.vn/product/213989179/${iid}`,
        voucher: r.voucher_code || "",
        v_disc: Number(r.voucher_discount || 0),
        v_min: Number(r.voucher_min_spend || 0),
      };
    });

    const msN = norm(items.map(i => i.ms));
    const rcN = norm(items.map(i => i.rc));
    const rtN = norm(items.map(i => i.rating));
    const hdN = norm(items.map(i => i.discount_headroom));
    const ageN = norm(items.map(i => -i.age_days)); /* newer -> higher */

    const soldMs = items.map(i => i.ms).sort((a, b) => a - b);
    const threshSlow = soldMs[Math.max(0, Math.floor(soldMs.length * 0.20) - 1)] || 0;

    items.forEach((i, idx) => {
      i.hero_score = +(0.30 * msN[idx] + 0.25 * rcN[idx] + 0.15 * rtN[idx] + 0.15 * hdN[idx] + 0.15 * ageN[idx]).toFixed(4);
      i.slow_mover = i.ms <= threshSlow;
      i.clearance_candidate = i.slow_mover && !i.sold_out;
      i.margin_unsafe = i.disc_pct >= 40;
    });
    return items;
  }

  /* ---------- storage draft (state phiên live) ---------- */
  const STORE_KEY = "area303_session_draft_v1";
  function loadDraft() {
    try { return JSON.parse(localStorage.getItem(STORE_KEY) || "{}"); } catch { return {}; }
  }
  function saveDraft(d) {
    try { localStorage.setItem(STORE_KEY, JSON.stringify(d || {})); } catch {}
  }

  /* ---------- expose ---------- */
  // Gắn cả lên window để Alpine x-text dùng trực tiếp (num(...), vnd(...), pct(...))
  // và dưới window.AREA303.* cho JS.
  window.AREA303 = {
    DATA,
    vnd, num, pct, clamp01,
    buildScoredItems,
    loadDraft, saveDraft,
  };
  window.num = num;
  window.vnd = vnd;
  window.pct = pct;
  window.clamp01 = clamp01;
})();
