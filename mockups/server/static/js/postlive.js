/* ============================================================
   AREA_303 — Post-live Review logic
   Tính GMV/AOV ước tính, learner loop giả lập (reweight theo feedback).
   ============================================================ */
function postlive() {
  return {
    items: [],
    playbook: null,
    draft: {},
    skuResults: [],
    cost: { ads: 0, voucher: 0, staff: 0, other: 0, notes: "" },
    learned: false,

    init() {
      this.AREA303 = AREA303;
      this.num = num; this.vnd = vnd; this.pct = pct;
      this.items = AREA303.buildScoredItems();
      this.playbook = AREA303.DATA.playbook || null;
      const d = AREA303.loadDraft();
      this.draft = (d.prelive && d.prelive.draft) || {};
      const onair = d.onair || {};
      this.hasSession = !!onair.endedAt || !!onair.log?.length || (d.prelive && (d.prelive.selectedIds||[]).length);
      this.ordersCount = (onair.log || []).filter(x => x.includes("order")).length;
      // build sku results từ show hiện có
      this.buildSKUResults(onair);
      const pc = d.postlive;
      if (pc) {
        this.cost = Object.assign(this.cost, pc.cost || {});
        this.learned = !!pc.learned;
        if (pc.skuResults) this.skuResults = pc.skuResults;
      }
      this.keepers = pc?.keepers || [];
      this.droppers = pc?.droppers || [];
      this.nextSlot = pc?.nextSlot || this.draft.slot || (this.playbook?.recommended_window || "T5 20:00–21:30").split("(")[0].trim();
      this.recalcAll();
    },

    get hasSession() { return this._hs || false; },
    set hasSession(v) { this._hs = v; },

    buildSKUResults(onair) {
      const ids = new Set();
      // ưa SKU trong playbook
      (this.playbook?.phases || []).forEach(p => {
        (p.skus || []).forEach(s => ids.add(s.item_id));
        if (p.bundle) Object.values(p.bundle).forEach(v => { if (v && v.item_id) ids.add(v.item_id); });
      });
      // + SKU draft pre-live chọn
      const preSel = this.draft ? null : null;
      const selIds = (AREA303.loadDraft().prelive?.selectedIds) || [];
      selIds.forEach(id => ids.add(id));
      const list = [...ids].map(id => this.items.find(i => i.item_id === id)).filter(Boolean);
      // ước tính đơn = ms * một tỷ lệ (mặc định dự đoán្លោះ)
      const totalOrderEst = list.reduce((s, i) => s + (i.ms / 100), 0) || 1;
      this.skuResults = list.map(i => ({
        item_id: i.item_id, name: i.name, price: i.price, ms: i.ms, hero_score: i.hero_score,
        orders: Math.max(0, Math.round(i.ms * 0.05)), // heuristic
        revenue: 0, feedback: "",
      }));
      if (!this.skuResults.length && this.items.length) {
        // fallback: top 8 theo hero
        this.skuResults = this.items.slice().sort((a,b)=>b.hero_score-a.hero_score).slice(0,8).map(i=>({
          item_id:i.item_id,name:i.name,price:i.price,ms:i.ms,hero_score:i.hero_score,orders:0,revenue:0,feedback:""
        }));
      }
    },

    get skusInShow() { return this.skuResults; },
    get gmv() {
      return this.skuResults.reduce((s, r) => s + (r.orders || 0) * (r.price || 0), 0);
    },
    get aov() {
      const n = this.skuResults.reduce((s, r) => s + (r.orders || 0), 0);
      return n > 0 ? this.gmv / n : 0;
    },
    get totalCost() {
      return (this.cost.ads||0)+(this.cost.voucher||0)+(this.cost.staff||0)+(this.cost.other||0);
    },
    get profit() { return this.gmv - this.totalCost; },

    recalc(r) { r.revenue = (r.orders || 0) * (r.price || 0); this.save(); },
    recalcAll() { this.skuResults.forEach(r => this.recalc(r)); },

    /* ----- learner mock: reweight hero_score theo feedback ----- */
    runLearner() {
      // wind: win/under -> score+, over -> score++, skip -> demote
      const counts = { win: 0, over: 0, under: 0, skip: 0 };
      this.skuResults.forEach(r => {
        if (!r.feedback) return;
        counts[r.feedback] = (counts[r.feedback] || 0) + 1;
        const adj = { win: +0.02, over: +0.05, under: -0.02, skip: -0.10 }[r.feedback] || 0;
        r.hero_score = Math.max(0, Math.min(1, +(r.hero_score + adj).toFixed(4)));
      });
      this.learned = true;
      // dựng lại đề xuất
      this.buildNext();
      this.save();
    },

    buildNext() {
      // keepers: top by adj hero_score, không skip
      const all = [...this.skuResults].sort((a,b)=>b.hero_score-a.hero_score);
      this.keepers = all.filter(r => r.feedback !== "skip").slice(0, 5);
      // droppers: skip hoặc under
      this.droppers = this.skuResults
        .filter(r => r.feedback === "skip" || r.feedback === "under")
        .map(r => ({ item_id: r.item_id, name: r.name, reason: r.feedback === "skip" ? "bỏ live sau" : "dưới dự đoán" }));
      if (!this.droppers.length) {
        this.droppers = this.items
          .filter(i => i.slow_mover && i.ms < 50 && !this.skuResults.some(r => r.item_id === i.item_id))
          .slice(0, 3)
          .map(i => ({ item_id: i.item_id, name: i.name, reason: "slow-mover" }));
      }
      this.nextSlot = this.draft.slot || this.playbook?.recommended_window || "T5 20:00–21:30";
    },

    save() {
      const d = AREA303.loadDraft();
      d.postlive = {
        cost: this.cost,
        learned: this.learned,
        skuResults: this.skuResults,
        keepers: this.keepers, droppers: this.droppers, nextSlot: this.nextSlot,
      };
      AREA303.saveDraft(d);
    },
  };
}
