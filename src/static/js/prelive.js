/* ============================================================
   AREA_303 — Pre-live Planner Logic
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const shopId = window.__SHOP_ID__ || "213989179";

  // State
  let pipelineData = null;
  let allSkus = [];
  let selectedSkuIds = new Set();
  let selectedComboIds = new Set();
  let filters = {
    line: "",
    gift: "",
    maxPrice: null,
    minScore: 0,
    search: "",
  };

  // Elements
  const loadingEl = document.getElementById("loading-state");
  const mainContentEl = document.getElementById("main-content");
  const skuTableBody = document.getElementById("sku-table-body");
  const timeslotBadge = document.getElementById("timeslot-badge");
  const timeslotReason = document.getElementById("timeslot-reason");
  const combosContainer = document.getElementById("combos-container");
  const vouchersContainer = document.getElementById("vouchers-container");

  // KPI Elements
  const statSkus = document.getElementById("stat-skus");
  const statLift = document.getElementById("stat-lift");
  const statBudgetUsed = document.getElementById("stat-budget-used");
  const statSelectedCount = document.getElementById("selected-sku-count");

  // Fetch pipeline recommendation
  async function loadPipeline(customBudget = null) {
    if (loadingEl) loadingEl.style.display = "flex";
    if (mainContentEl) mainContentEl.style.display = "none";

    try {
      const budgetVal = customBudget !== null ? customBudget : 500000000;
      const resp = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shopId,
          budget_voucher_month: budgetVal,
        }),
      });

      const res = await resp.json();
      if (res.status === "ok") {
        pipelineData = res.recommendation;
        allSkus = pipelineData.m2_heros || [];

        // Auto-select top 8 SKUs initially
        selectedSkuIds.clear();
        allSkus.slice(0, 8).forEach(s => selectedSkuIds.add(s.item_id));

        // Auto-select top 2 combos
        selectedComboIds.clear();
        (pipelineData.m4_combos || []).slice(0, 2).forEach(c => selectedComboIds.add(c.combo_id));

        renderUI();
      } else {
        AREA303.toast("Lỗi tải dữ liệu: " + res.message, "error");
      }
    } catch (err) {
      console.error(err);
      AREA303.toast("Lỗi kết nối máy chủ", "error");
    } finally {
      if (loadingEl) loadingEl.style.display = "none";
      if (mainContentEl) mainContentEl.style.display = "flex";
    }
  }

  function renderUI() {
    renderKPIs();
    renderTimeslot();
    renderSkusTable();
    renderCombos();
    renderVouchers();
  }

  function renderKPIs() {
    if (!pipelineData) return;
    if (statSkus) statSkus.textContent = allSkus.length;
    if (statLift) statLift.textContent = `+${pipelineData.summary.projected_lift_pct}%`;
    if (statBudgetUsed) statBudgetUsed.textContent = AREA303.vnd(pipelineData.m5_voucher.total_used);
    if (statSelectedCount) statSelectedCount.textContent = selectedSkuIds.size;
  }

  function renderTimeslot() {
    const ts = pipelineData.m3_timeslot || {};
    if (timeslotBadge) timeslotBadge.textContent = ts.recommended_slot || "20:00 – 22:00";
    if (timeslotReason) timeslotReason.textContent = ts.reason || "";
  }

  function renderSkusTable() {
    if (!skuTableBody) return;
    skuTableBody.innerHTML = "";

    const filtered = allSkus.filter(s => {
      if (filters.line && s.line !== filters.line) return false;
      if (filters.gift === "hide" && s.name.toUpperCase().includes("QUÀ TẶNG")) return false;
      if (filters.gift === "only" && !s.name.toUpperCase().includes("QUÀ TẶNG")) return false;
      if (filters.maxPrice && s.price > filters.maxPrice * 1000) return false;
      if (filters.minScore && s.hero_score < filters.minScore) return false;
      if (filters.search && !s.name.toLowerCase().includes(filters.search.toLowerCase())) return false;
      return true;
    });

    // M1 map lookup
    const m1Map = {};
    (pipelineData.m1_pricing.items || []).forEach(p => { m1Map[p.item_id] = p; });

    filtered.forEach(sku => {
      const tr = document.createElement("tr");
      const isSelected = selectedSkuIds.has(sku.item_id);
      const m1 = m1Map[sku.item_id] || { scenario: "hold", discount_pct: 0 };

      let scenarioBadge = `<span class="badge tag-hold">GIỮ GIÁ</span>`;
      if (m1.scenario === "mild") scenarioBadge = `<span class="badge tag-mild">GIẢM -${m1.discount_pct}%</span>`;
      if (m1.scenario === "flash") scenarioBadge = `<span class="badge tag-flash">FLASH -${m1.discount_pct}%</span>`;

      tr.innerHTML = `
        <td style="width: 40px; text-align: center;">
          <input type="checkbox" ${isSelected ? "checked" : ""} data-id="${sku.item_id}" class="sku-checkbox">
        </td>
        <td style="width: 50px; font-weight: 700; color: var(--muted);">#${sku.rank}</td>
        <td>
          <div style="font-weight: 600; color: var(--text);">${sku.name}</div>
          <div style="font-size: 0.6875rem; color: var(--muted); margin-top: 2px;">
            <span class="badge" style="background: var(--brand-soft); color: var(--brand);">${sku.line}</span>
            <span style="margin-left: 6px;">Đã bán: ${AREA303.num(sku.raw_values.monthly_sold)}</span>
          </div>
        </td>
        <td style="font-weight: 700; white-space: nowrap;">${AREA303.vnd(sku.price)}</td>
        <td>${scenarioBadge}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="width: 60px; height: 6px; background: #e2e8f0; border-radius: 99px; overflow: hidden;">
              <div style="width: ${Math.round(sku.hero_score * 100)}%; height: 100%; background: var(--brand-accent);"></div>
            </div>
            <span style="font-weight: 700; font-size: 0.75rem;">${sku.hero_score.toFixed(2)}</span>
          </div>
        </td>
      `;
      skuTableBody.appendChild(tr);
    });

    // Checkbox events
    document.querySelectorAll(".sku-checkbox").forEach(cb => {
      cb.addEventListener("change", (e) => {
        const id = e.target.getAttribute("data-id");
        if (e.target.checked) selectedSkuIds.add(id);
        else selectedSkuIds.delete(id);
        if (statSelectedCount) statSelectedCount.textContent = selectedSkuIds.size;
      });
    });
  }

  function renderCombos() {
    if (!combosContainer || !pipelineData) return;
    combosContainer.innerHTML = "";
    const combos = pipelineData.m4_combos || [];

    if (combos.length === 0) {
      combosContainer.innerHTML = `<div style="color: var(--muted); font-size: 0.8125rem;">Chưa phát hiện combo tối ưu nào.</div>`;
      return;
    }

    combos.forEach(c => {
      const isSelected = selectedComboIds.has(c.combo_id);
      const card = document.createElement("div");
      card.className = "card";
      card.style.border = isSelected ? "2px solid var(--purple)" : "1px solid var(--line)";
      card.style.background = isSelected ? "rgba(124, 58, 237, 0.02)" : "#ffffff";
      card.style.display = "flex";
      card.style.flexDirection = "column";
      card.style.justifyContent = "space-between";

      card.innerHTML = `
        <div>
          <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
            <span class="badge tag-bundle">${c.type_label}</span>
            <label style="display: flex; align-items: center; gap: 4px; font-size: 0.75rem; font-weight: 600; cursor: pointer;">
              <input type="checkbox" ${isSelected ? "checked" : ""} data-cid="${c.combo_id}" class="combo-checkbox"> Ghép live
            </label>
          </div>
          <div style="font-weight: 700; font-size: 0.875rem; margin-bottom: 6px;">${c.combo_name}</div>
          <p style="font-size: 0.75rem; color: var(--muted); line-height: 1.4; margin-bottom: 10px;">${c.reason}</p>
        </div>
        <div style="display: flex; justify-content: space-between; align-items: center; padding-top: 8px; border-top: 1px solid var(--line);">
          <div>
            <span style="font-size: 0.6875rem; color: var(--muted); text-decoration: line-through;">${AREA303.vnd(c.original_total_price)}</span>
            <span style="font-size: 1rem; font-weight: 800; color: var(--purple); margin-left: 4px;">${AREA303.vnd(c.bundle_price)}</span>
          </div>
          <span class="badge" style="background: var(--ok-bg); color: var(--ok);">Tiết kiệm ${AREA303.vnd(c.savings)}</span>
        </div>
      `;
      combosContainer.appendChild(card);
    });

    document.querySelectorAll(".combo-checkbox").forEach(cb => {
      cb.addEventListener("change", (e) => {
        const cid = e.target.getAttribute("data-cid");
        if (e.target.checked) selectedComboIds.add(cid);
        else selectedComboIds.delete(cid);
        renderCombos();
      });
    });
  }

  function renderVouchers() {
    if (!vouchersContainer || !pipelineData) return;
    vouchersContainer.innerHTML = "";
    const vPlan = pipelineData.m5_voucher || {};
    const allocations = (vPlan.sku_allocations || []).filter(a => a.is_selected);

    if (allocations.length === 0) {
      vouchersContainer.innerHTML = `<div style="color: var(--muted); font-size: 0.8125rem;">Ngân sách chưa phân bổ voucher cho SKU nào.</div>`;
      return;
    }

    allocations.slice(0, 6).forEach(a => {
      const vEl = document.createElement("div");
      vEl.style.display = "flex";
      vEl.style.justifyContent = "space-between";
      vEl.style.alignItems = "center";
      vEl.style.padding = "8px 12px";
      vEl.style.background = "#f8fafc";
      vEl.style.borderRadius = "8px";
      vEl.style.border = "1px solid var(--line)";

      vEl.innerHTML = `
        <div style="min-width: 0; flex: 1; padding-right: 8px;">
          <div style="font-weight: 600; font-size: 0.75rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${a.name}</div>
          <div style="font-size: 0.6875rem; color: var(--muted);">Đơn tối thiểu: ${AREA303.vnd(a.min_spend)}</div>
        </div>
        <div style="text-align: right; flex-shrink: 0;">
          <div style="font-weight: 800; font-size: 0.875rem; color: var(--brand-accent);">-${AREA303.vnd(a.voucher_amount)}</div>
          <div style="font-size: 0.6875rem; color: var(--ok); font-weight: 600;">Dự kiến: ${a.expected_sales} đơn</div>
        </div>
      `;
      vouchersContainer.appendChild(vEl);
    });
  }

  // Filter Listeners
  const filterLine = document.getElementById("filter-line");
  const filterGift = document.getElementById("filter-gift");
  const filterMaxPrice = document.getElementById("filter-price");
  const filterSearch = document.getElementById("filter-search");
  const btnAutoPick = document.getElementById("btn-autopick");
  const btnSavePlaybook = document.getElementById("btn-save-playbook");

  if (filterLine) filterLine.addEventListener("change", (e) => { filters.line = e.target.value; renderSkusTable(); });
  if (filterGift) filterGift.addEventListener("change", (e) => { filters.gift = e.target.value; renderSkusTable(); });
  if (filterMaxPrice) filterMaxPrice.addEventListener("input", (e) => { filters.maxPrice = Number(e.target.value) || null; renderSkusTable(); });
  if (filterSearch) filterSearch.addEventListener("input", (e) => { filters.search = e.target.value; renderSkusTable(); });

  if (btnAutoPick) {
    btnAutoPick.addEventListener("click", () => {
      selectedSkuIds.clear();
      allSkus.slice(0, 10).forEach(s => selectedSkuIds.add(s.item_id));
      renderSkusTable();
      if (statSelectedCount) statSelectedCount.textContent = selectedSkuIds.size;
      AREA303.toast("Đã tự động chọn Top 10 SKU có Hero Score cao nhất!", "success");
    });
  }

  // Save Playbook & Go On-air
  if (btnSavePlaybook) {
    btnSavePlaybook.addEventListener("click", async () => {
      if (selectedSkuIds.size === 0) {
        AREA303.toast("Vui lòng chọn ít nhất 1 SKU cho phiên live!", "warn");
        return;
      }

      const selectedSkus = allSkus.filter(s => selectedSkuIds.has(s.item_id));
      const selectedCombos = (pipelineData.m4_combos || []).filter(c => selectedComboIds.has(c.combo_id));

      const playbookPayload = {
        shop_id: shopId,
        slot: pipelineData.m3_timeslot?.recommended_slot || "20:00 – 22:00",
        items: selectedSkus,
        combos: selectedCombos,
        vouchers: pipelineData.m5_voucher?.sku_allocations || [],
        summary: pipelineData.summary,
      };

      try {
        const resp = await fetch("/api/sessions/save-draft", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(playbookPayload),
        });
        const res = await resp.json();
        if (res.status === "ok") {
          AREA303.toast("Đã lưu Playbook thành công! Chuyển sang On-air...", "success");
          setTimeout(() => {
            window.location.href = `/onair?shop_id=${shopId}`;
          }, 600);
        } else {
          AREA303.toast("Lỗi lưu draft: " + res.message, "error");
        }
      } catch (err) {
        AREA303.toast("Lỗi kết nối", "error");
      }
    });
  }

  // Initial load
  loadPipeline();
});
