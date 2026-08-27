/* ============================================================
   AREA_303 — On-air Assistant logic
   Dựng run-of-show từ playbook (4 phase) + draft pre-live.
   ============================================================ */
function onair() {
  return {
    items: [],
    playbook: null,
    selectedItems: [],
    draft: {},
    voucherResult: null,
    show: [],
    current: 0,
    live: false,
    startedAt: 0,
    log: [],

    init() {
      this.AREA303 = AREA303;
      this.num = num; this.vnd = vnd; this.pct = pct;
      this.items = AREA303.buildScoredItems();
      this.playbook = AREA303.DATA.playbook || null;
      const d = AREA303.loadDraft();
      const pre = d.prelive || {};
      this.selectedItems = (pre.selectedIds || []).map(id => this.items.find(i => i.item_id === id)).filter(Boolean);
      this.draft = pre.draft || {};
      this.voucherResult = pre.voucherResult || (this.playbook && this.playbook.voucher_optimization) || null;
      this.log = (d.onair && d.onair.log) || [];
      this.current = (d.onair && d.onair.current) || 0;
      this.buildShow();
    },

    /* ----- dựng run-of-show từ playbook phases ----- */
    buildShow() {
      const slots = [];
      let t0 = 20 * 60; // 20:00
      function lbl(mins) { const h = Math.floor(mins/60)%24, m = mins%60; return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`; }
      function push(role, title, subtitle, dur, skus, bundle, disc) {
        const s = lbl(t0), e = lbl(t0 + dur);
        slots.push({ role, title, subtitle, startLabel: s, endLabel: e, skus, bundle, disc });
        t0 += dur;
      }
      const pb = this.playbook;
      const byId = id => this.items.find(i => i.item_id === id);
      if (pb && pb.phases) {
        pb.phases.forEach(ph => {
          let skus = [];
          if (ph.role === "bundle" && ph.bundle) {
            const b = [];
            Object.entries(ph.bundle).forEach(([k, v]) => {
              if (v && v.item_id) { skus.push(byId(v.item_id) || v); b.push([k, v]); }
            });
            push("bundle", "Combo cross-category", "Ghép kẹo + bánh tăng AOV", 15, skus, ph.bundle, 15);
          } else {
            const sl = ph.skus || [];
            skus = sl.map(s => byId(s.item_id) || s).filter(Boolean);
            const title = ph.role === "hook" ? "Mở đầu — Hook hero"
                       : ph.role === "core" ? "Core — top bán chạy"
                       : "Clearance — dọn kho slow-mover";
            dur = ph.role === "hook" ? 18 : ph.role === "core" ? 35 : 22;
            push(ph.role, title, ph.rationale ? ph.rationale.slice(0, 80) : "", dur, skus, null, (ph.price_grid || {}).target_disc_pct);
          }
        });
      } else if (this.selectedItems.length) {
        this.selectedItems.slice(0, 5).forEach((it, i) => {
          push(i === 0 ? "hook" : "core", it.name.slice(0, 50), it.line, 15, [it], null, 0);
        });
      }
      // nếu draft có combo riêng, chèn 1 slot bundle cuối
      if (!this.show.length && this.draft.combo && this.draft.combo.length) {
        push("bundle", "Combo của phiên", "Bundle draft", 15, this.draft.combo, null, 15);
      }
      this.show = slots;
    },

    get cur() { return this.show[this.current]; },

    selectSlot(i) { this.current = i; this.save(); },
    nextSlot() { if (this.current < this.show.length - 1) { this.current++; this.save(); } },
    prevSlot() { if (this.current > 0) { this.current--; this.save(); } },

    toggleLive() {
      this.live = !this.live;
      if (this.live) this.startedAt = Date.now();
      this.logPush(this.live ? "live_start" : "live_pause");
      this.save();
    },
    endLive(e) {
      if (this.live) { this.live = false; this.logPush("live_end"); }
      const d = AREA303.loadDraft();
      d.onair = { current: this.current, log: this.log, endedAt: Date.now(), live: false };
      AREA303.saveDraft(d);
      // để postlive.html xử lý
      if (e) e.preventDefault();
      location.href = "postlive.html";
    },

    recordOrder() { this.logPush("order"); },
    dash(kind) { this.logPush(kind); this.save(); },

    logPush(name) {
      const stamp = this.elapsedLabel();
      this.log.push(`${stamp}:${name}`);
      if (this.log.length > 30) this.log.shift();
      this.save();
    },

    elapsedLabel() {
      if (!this.live && !this.log.length) return "00:00";
      const base = this.startedAt || (Date.now() - 1000);
      const s = Math.floor((Date.now() - base) / 1000);
      const m = Math.floor(s / 60), ss = s % 60;
      return `${String(m).padStart(2,"0")}:${String(ss).padStart(2,"0")}`;
    },

    hints(s) {
      if (!s) return [];
      const r = s.role;
      if (r === "hook") return [
        "Hook: mở bằng hero, giật tít giá tốt nhất.",
        "Demo thử/nếm thử để giữ viewer 30-45s đầu.",
        "Nhấn hero_score cao + số đã bán/tháng.",
      ];
      if (r === "core") return [
        "Core: giới thiệu 2-3 SKU liên tiếp cùng line.",
        "Tung voucher min_spend ngay lúc cart đầy.",
        "Lặp lại deal mỗi 5 phút cho viewer mới.",
      ];
      if (r === "bundle") return [
        "Bundle: ghép kẹo + bánh → tiết kiệm ~15%.",
        "Push AOV: ‘mua combo rẻ hơn mua lẻ’.",
      ];
      return [
        "Clearance: flash 25-35%, KHÔNG quá 40%.",
        "Tạo khan hiếm: ‘còn X hộp’.",
        "Dọn kho slow-mover, freespace cho SKU mới.",
      ];
    },

    roleLabel(r) { return { hook: "Hook", core: "Core", bundle: "Bundle", clearance: "Clearance" }[r] || r; },
    roleTag(r) { return { hook: "tag-hook", core: "tag-core", bundle: "tag-bundle", clearance: "tag-clear" }[r]; },

    save() {
      const d = AREA303.loadDraft();
      d.onair = Object.assign(d.onair || {}, { current: this.current, log: this.log, live: this.live });
      AREA303.saveDraft(d);
    },
  };
}
