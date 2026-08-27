/* ============================================================
   AREA_303 — Pre-live Planner logic
   ============================================================ */
function prelive() {
  return {
    items: [],
    playbook: null,
    selectedIds: [],
    f: { line: "", gift: "", maxPrice: null, heronly: false, minScore: 0 },
    draft: { slot: "", budget: 500000000, maxSingle: 0, maxN: 0, combo: [] },
    voucherResult: { budget: 0, used: 0, remaining: 0, n_selected: 0, total_est_sales: 0, selected: [] },
    slotsSuggested: [],
    heatmapHTML: () => "",

    init() {
      this.AREA303 = AREA303;
      this.num = num; this.vnd = vnd; this.pct = pct;
      this.items = AREA303.buildScoredItems();
      this.playbook = AREA303.DATA.playbook || null;
      const d = AREA303.loadDraft();
      if (d && d.prelive) {
        this.selectedIds = d.prelive.selectedIds || [];
        this.draft = Object.assign(this.draft, d.prelive.draft || {});
        this.voucherResult = d.prelive.voucherResult || this.voucherResult;
      }
      // seed voucher from playbook nếu có
      if (this.playbook && this.playbook.voucher_optimization && !this.voucherResult.selected?.length) {
        this.voucherResult = JSON.parse(JSON.stringify(this.playbook.voucher_optimization));
        this.draft.budget = this.voucherResult.budget || this.draft.budget;
      }
      this.buildSlots();
      this.buildHeatmap();
    },

    /* ----- filter ----- */
    filtered() {
      return this.items.filter(i => {
        if (this.f.line && i.line !== this.f.line) return false;
        if (this.f.gift === "hide" && i.is_gift) return false;
        if (this.f.gift === "only" && !i.is_gift) return false;
        if (this.f.maxPrice && i.price > this.f.maxPrice * 1000) return false;
        if (this.f.heronly && i.hero_score < (this.f.minScore || 0)) return false;
        return true;
      }).sort((a, b) => b.hero_score - a.hero_score);
    },
    filteredSingles() {
      return this.filtered().filter(i => !i.is_combo);
    },
    filteredCombos() {
      return this.filtered().filter(i => i.is_combo);
    },

    toggle(id) {
      const k = this.selectedIds.indexOf(id);
      if (k >= 0) this.selectedIds.splice(k, 1); else this.selectedIds.push(id);
      this.save();
    },
    autoPick(n) {
      const top = this.filtered().filter(i => !i.sold_out).slice(0, n);
      this.selectedIds = top.map(i => i.item_id);
      this.save();
    },

    lineTag(line) {
      const m = {
        "Ăn kiêng / Ít đường": "tag-core",
        "Bánh ăn sáng": "tag-clear",
        "Kẹo": "tag-bundle",
        "Bánh": "tag-hook",
        "Khác": "tag-soldout"
      };
      return m[line] || "tag-soldout";
    },

    /* ----- M3 timeslot ----- */
    buildSlots() {
      const wd = ["T2","T3","T4","T5","T6","T7","CN"];
      // prior: T5 20-21:30 + 12-13 + 20-22 phổ biến
      this.slotsSuggested = [
        { tone: "primary", label: "T5 20:00–21:30", why: "Market daily 2026-07-03 peak; khung vàng Shopee VN tối cuối tuần." },
        { tone: "alt", label: "T7 20:00–21:30", why: "Khung dự phòng cuối tuần, AOV cao sau payday." },
        { tone: "alt", label: "T2/T4 12:00–13:00", why: "Trưa ngày thường: traffic ổn, cạnh tranh thấp." },
      ];
    },
    buildHeatmap() {
      const wd = ["T2","T3","T4","T5","T6","T7","CN"];
      const hours = [0,6,9,12,15,18,20,21,22,23];
      // mock score base trên gam: peak 20-21, dip đêm
      function score(d, h) {
        let s = 0.2;
        if (h >= 19 && h <= 21) s = 0.9;
        else if (h >= 11 && h <= 13) s = 0.55;
        else if (h >= 9 && h <= 11) s = 0.45;
        else if (h >= 14 && h <= 17) s = 0.35;
        else if (h < 7) s = 0.1;
        if (d === 4 || d === 5) s *= 1.08; // T5 T6 boost
        if (d === 6 && h >= 19) s = 0.88;
        return Math.min(1, s);
      }
      function color(s) {
        // 0->trắng, 1->var(--brand)
        const a = (s).toFixed(2);
        return `background:rgba(43,66,87,${a});color:${s > 0.45 ? "#fff":"#374151"}`;
      }
      let html = "<table class='hm'><thead><tr><th>Giờ \\ Ngày</th>";
      wd.forEach(w => html += `<th>${w}</th>`);
      html += "</tr></thead><tbody>";
      hours.forEach(h => {
        html += `<tr><td class='lab'>${String(h).padStart(2,"0")}:00</td>`;
        wd.forEach((_, d) => {
          const s = score(d, h);
          html += `<td title='${wd[d]} ${h}:00 · score ${s.toFixed(2)}' style='${color(s)}'>${s.toFixed(2)}</td>`;
        });
        html += "</tr>";
      });
      html += "</tbody></table>";
      this.heatmapHTML = () => html;
    },

    /* ----- M4 combo ----- */
    suggestCombo() {
      const sel = this.selectedIds.map(id => this.items.find(i => i.item_id === id)).filter(Boolean);
      const find = (kw, anti=[]) => sel.find(i => {
        const n = i.name.toLowerCase();
        return n.includes(kw) && !anti.some(a => n.includes(a));
      });
      let keo = find("kẹo", ["bánh"]);
      let banh = find("bánh", ["kẹo"]);
      if (!keo) keo = sel[0];
      if (!banh && sel.length > 1) banh = sel[1];
      this.draft.combo = [];
      if (keo) this.draft.combo.push({ role: "Hook", item_id: keo.item_id, name: keo.name, price: keo.price });
      if (banh && banh.item_id !== (keo && keo.item_id)) this.draft.combo.push({ role: "Cross-sell", item_id: banh.item_id, name: banh.name, price: banh.price });
      this.save();
    },
    comboTotal() { return this.draft.combo.reduce((s, c) => s + c.price, 0); },
    comboSavingPct() {
      const c = this.draft.combo;
      if (!c.length) return 0;
      const full = c.reduce((s, x) => s + x.price, 0);
      // -15% theo grid bundle (M4)
      return Math.round((1 - (full * 0.85) / full) * 100);
    },

    /* ----- M5 voucher knapsack (client-side, mirror của greedy) ----- */
    runVoucher() {
      const ALPHA = 0.5, BETA = 0.2;
      const budget = this.draft.budget || 0;
      const maxSingle = this.draft.maxSingle || 0;
      const maxN = this.draft.maxN || 0;
      const cand = this.items
        .filter(i => !i.sold_out && !i.is_gift && i.orig > 0)
        .map(i => ({ item_id: i.item_id, name: i.name, orig_price: i.orig, monthly_sold: i.ms, disc_pct: 30, price: Math.round(i.orig * 0.7), voucher_disc: 40000, min_spend: 50000 }))
        .map(c => {
          const A = c.price - c.voucher_disc;
          const B = c.orig_price - A;
          const factor = Math.max(0, 1 + ALPHA * (B / c.orig_price) - BETA * (c.min_spend / 200000));
          c.est_sales = c.monthly_sold * factor;
          c.vcost = c.voucher_disc * c.est_sales;
          if (maxSingle && c.voucher_disc > maxSingle) {
            c.voucher_disc = maxSingle; c.vcost = maxSingle * c.est_sales;
          }
          return c;
        })
        .filter(c => c.est_sales > 0 && c.vcost > 0)
        .sort((a, b) => (b.est_sales / Math.max(b.vcost, 1)) - (a.est_sales / Math.max(a.vcost, 1)));
      let used = 0, total = 0;
      const selected = [];
      for (const c of cand) {
        if (maxN && selected.length >= maxN) break;
        if (used + c.vcost <= budget) {
          selected.push(c); used += c.vcost; total += c.est_sales;
        }
      }
      this.voucherResult = {
        budget, used, remaining: budget - used, n_selected: selected.length,
        total_est_sales: total, selected, method: "greedy",
      };
      this.save();
    },

    /* ----- persistence + nav ----- */
    save() {
      const d = AREA303.loadDraft();
      d.prelive = {
        selectedIds: this.selectedIds,
        draft: this.draft,
        voucherResult: this.voucherResult,
      };
      AREA303.saveDraft(d);
    },
    resetDraft() {
      if (!confirm("Xoá draft pre-live?")) return;
      localStorage.removeItem("area303_session_draft_v1");
      location.reload();
    },
  };
}
