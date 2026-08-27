/* ============================================================
   AREA_303 — Pre-live Planner Logic
   Includes interactive SKU filters, HeroScore ranking,
   smart combo bundling, voucher knapsack, and livestream time picker.
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const shopId = window.__SHOP_ID__ || "213989179";

  // State
  let pipelineData = null;
  let allSkus = [];
  let selectedSkuIds = new Set();
  let selectedComboIds = new Set();
  let m5RerunTimer = null; // timer debounce re-run M5 mỗi khi tick đổi
  let budgetRerunTimer = null; // timer debounce re-run M5 mỗi khi ngân sách đổi
  let DEFAULT_BUDGET = 500000000; // mặc định khi ô ngân sách để trống
  let filters = {
    line: "",
    gift: "",
    maxPrice: null,
    minScore: 0,
    search: "",
  };

  // Timeslot State
  let selectedDate = new Date().toISOString().split("T")[0];
  let selectedStartTime = "20:00";
  let selectedEndTime = "22:00";

  // Elements
  const loadingEl = document.getElementById("loading-state");
  const mainContentEl = document.getElementById("main-content");
  const skuTableBody = document.getElementById("sku-table-body");
  const combosContainer = document.getElementById("combos-container");
  const vouchersContainer = document.getElementById("vouchers-container");

  // Timeslot Elements
  const liveDateInput = document.getElementById("live-date");
  const liveStartTimeInput = document.getElementById("live-start-time");
  const liveEndTimeInput = document.getElementById("live-end-time");
  const liveDurationBadge = document.getElementById("live-duration-badge");
  const timeslotReasonEl = document.getElementById("timeslot-reason");
  const peakHourLabel = document.getElementById("peak-hour-label");
  const heatmapBarsContainer = document.getElementById("heatmap-bars");
  const presetAiRecBtn = document.getElementById("preset-ai-rec");

  // KPI Elements
  const statSkus = document.getElementById("stat-skus");
  const statLift = document.getElementById("stat-lift");
  const statBudgetUsed = document.getElementById("stat-budget-used");
  const statSelectedCount = document.getElementById("selected-sku-count");

  // Budget Input (SECTION 4)
  const budgetInput = document.getElementById("budget-input");
  const budgetHint = document.getElementById("budget-hint");

  // Đọc ngân sách hiện tại từ ô nhập; để trống/invalid → dùng DEFAULT_BUDGET (500M).
  function currentBudget() {
    if (budgetInput) {
      const v = Number(budgetInput.value);
      if (Number.isFinite(v) && v > 0) return v;
    }
    return DEFAULT_BUDGET;
  }

  // Initialize Date Input
  if (liveDateInput) {
    liveDateInput.value = selectedDate;
    liveDateInput.min = selectedDate;
    liveDateInput.addEventListener("change", (e) => {
      selectedDate = e.target.value;
    });
  }

  // Fetch pipeline recommendation
  async function loadPipeline(customBudget = null) {
    if (loadingEl) loadingEl.style.display = "flex";
    if (mainContentEl) mainContentEl.style.display = "none";

    try {
      // Ngân sách: ưu tiên tham số truyền vào, rồi tới ô nhập, rồi mặc định 500M.
      const budgetVal = customBudget !== null ? customBudget : currentBudget();
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

        // Auto-select top 8 SKUs initially (hành vi gốc — tick tự do, không khoá).
        selectedSkuIds.clear();
        allSkus.slice(0, 8).forEach(s => selectedSkuIds.add(s.item_id));

        // Auto-select top 2 combos
        selectedComboIds.clear();
        (pipelineData.m4_combos || []).slice(0, 2).forEach(c => selectedComboIds.add(c.combo_id));

        // Set initial timeslot from AI Recommendation
        const m3 = pipelineData.m3_timeslot || {};
        if (m3.start_hour !== undefined && m3.end_hour !== undefined) {
          selectedStartTime = `${m3.start_hour.toString().padStart(2, "0")}:00`;
          selectedEndTime = `${m3.end_hour.toString().padStart(2, "0")}:00`;
          if (liveStartTimeInput) liveStartTimeInput.value = selectedStartTime;
          if (liveEndTimeInput) liveEndTimeInput.value = selectedEndTime;
          if (presetAiRecBtn) {
            presetAiRecBtn.textContent = `⭐ AI Gợi Ý (${selectedStartTime}–${selectedEndTime})`;
            presetAiRecBtn.setAttribute("data-start", selectedStartTime);
            presetAiRecBtn.setAttribute("data-end", selectedEndTime);
          }
        }

        renderUI();
        // Sau khi load full pipeline lần đầu, re-run M5 cho đúng 8 SKU đã auto-tick
        // (voucher container ban đầu hiển thị cho tập đã tick, không phải toàn bộ data_pool).
        scheduleM5Rerun();
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

  // Re-run M5 cho đúng tập SKU đã tick. Debounce 300ms để gộp nhiều tick liên tiếp.
  function scheduleM5Rerun() {
    clearTimeout(m5RerunTimer);
    m5RerunTimer = setTimeout(runM5ForSelected, 300);
  }

  async function runM5ForSelected() {
    if (!pipelineData) return;
    const ids = Array.from(selectedSkuIds);
    if (ids.length === 0) {
      // Chưa tick SKU nào: voucher rỗng, KPI 0. Không gửi request.
      pipelineData.m5_voucher = pipelineData.m5_voucher || {};
      pipelineData.m5_voucher.sku_allocations = [];
      pipelineData.m5_voucher.n_selected_skus = 0;
      pipelineData.m5_voucher.total_estimated_sales = 0;
      delete pipelineData.m5_voucher.error;
      pipelineData.summary = pipelineData.summary || {};
      pipelineData.summary.selected_skus = 0;
      renderVouchers();
      renderKPIs();
      return;
    }
    try {
      const resp = await fetch("/api/pipeline/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shopId,
          budget_voucher_month: currentBudget(),
          item_ids: ids,
          must_select_all: true,
        }),
      });
      const res = await resp.json();
      if (res.status === "ok") {
        const rec = res.recommendation;
        // CHỈ cập nhật m5_voucher + summary; KHÔNG re-render bảng SKU (tránh mất tick).
        pipelineData.m5_voucher = rec.m5_voucher;
        pipelineData.summary = rec.summary;
        renderVouchers();
        renderKPIs();
        if (rec.m5_voucher && rec.m5_voucher.error) {
          AREA303.toast("M5: " + rec.m5_voucher.error, "warn");
        }
      } else {
        AREA303.toast("Lỗi re-run M5: " + (res.message || ""), "error");
      }
    } catch (err) {
      console.error(err);
      AREA303.toast("Lỗi kết nối khi re-run M5", "error");
    }
  }

  function renderUI() {
    renderKPIs();
    renderTimeslotSection();
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

  /* ---------- Timeslot Rendering & Interactions ---------- */

  function parseMinutes(timeStr) {
    const parts = (timeStr || "00:00").split(":");
    return (parseInt(parts[0], 10) || 0) * 60 + (parseInt(parts[1], 10) || 0);
  }

  function updateDuration() {
    const startMins = parseMinutes(selectedStartTime);
    let endMins = parseMinutes(selectedEndTime);
    if (endMins <= startMins) {
      endMins += 24 * 60; // next day crossing
    }
    const diff = endMins - startMins;
    const hrs = Math.floor(diff / 60);
    const mins = diff % 60;

    if (liveDurationBadge) {
      liveDurationBadge.textContent = `Thời lượng: ${hrs}h ${mins.toString().padStart(2, "0")}m`;
    }
  }

  function renderTimeslotSection() {
    const ts = pipelineData?.m3_timeslot || {};
    if (timeslotReasonEl) timeslotReasonEl.textContent = ts.reason || "Khung giờ vàng dựa trên tín hiệu livestream ngành.";
    if (peakHourLabel && ts.evidence?.peak_hour !== undefined) {
      peakHourLabel.textContent = `Đỉnh cao điểm: ${ts.evidence.peak_hour}:00`;
    }

    updateDuration();
    renderHeatmap();
  }

  function renderHeatmap() {
    if (!heatmapBarsContainer || !pipelineData?.m3_timeslot?.evidence) return;
    heatmapBarsContainer.innerHTML = "";

    const dist = pipelineData.m3_timeslot.evidence.hour_distribution || [];
    const maxVal = Math.max(...dist, 1);

    const startH = parseInt(selectedStartTime.split(":")[0], 10);
    const endH = parseInt(selectedEndTime.split(":")[0], 10);

    for (let h = 0; h < 24; h++) {
      const count = dist[h] || 0;
      const heightPct = Math.max(12, Math.round((count / maxVal) * 100));

      const isSelected = (endH > startH) ? (h >= startH && h < endH) : (h >= startH || h < endH);

      const bar = document.createElement("div");
      bar.style.flex = "1";
      bar.style.height = `${heightPct}%`;
      bar.style.borderRadius = "2px 2px 0 0";
      bar.style.cursor = "pointer";
      bar.style.transition = "all 0.15s ease";
      bar.title = `${h}:00 - ${h + 1}:00 (${count} voucher ngành)`;

      if (isSelected) {
        bar.style.background = "var(--brand-accent)";
        bar.style.boxShadow = "0 0 4px rgba(2, 132, 199, 0.4)";
      } else {
        bar.style.background = count > 0 ? "#cbd5e1" : "#e2e8f0";
      }

      bar.addEventListener("mouseenter", () => {
        if (!isSelected) bar.style.background = "#94a3b8";
      });
      bar.addEventListener("mouseleave", () => {
        if (!isSelected) bar.style.background = count > 0 ? "#cbd5e1" : "#e2e8f0";
      });

      bar.addEventListener("click", () => {
        // Set 2-hour window starting from clicked hour
        const newStartH = h;
        const newEndH = (h + 2) % 24;
        selectedStartTime = `${newStartH.toString().padStart(2, "0")}:00`;
        selectedEndTime = `${newEndH.toString().padStart(2, "0")}:00`;
        if (liveStartTimeInput) liveStartTimeInput.value = selectedStartTime;
        if (liveEndTimeInput) liveEndTimeInput.value = selectedEndTime;

        document.querySelectorAll(".slot-preset-btn").forEach(b => b.classList.remove("active"));
        updateDuration();
        renderHeatmap();
      });

      heatmapBarsContainer.appendChild(bar);
    }
  }

  // Preset Buttons Event Handlers
  document.querySelectorAll(".slot-preset-btn").forEach(btn => {
    btn.addEventListener("click", (e) => {
      document.querySelectorAll(".slot-preset-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");

      selectedStartTime = btn.getAttribute("data-start");
      selectedEndTime = btn.getAttribute("data-end");
      if (liveStartTimeInput) liveStartTimeInput.value = selectedStartTime;
      if (liveEndTimeInput) liveEndTimeInput.value = selectedEndTime;

      updateDuration();
      renderHeatmap();
    });
  });

  // Time Inputs Handlers
  if (liveStartTimeInput) {
    liveStartTimeInput.addEventListener("change", (e) => {
      selectedStartTime = e.target.value;
      document.querySelectorAll(".slot-preset-btn").forEach(b => b.classList.remove("active"));
      updateDuration();
      renderHeatmap();
    });
  }

  if (liveEndTimeInput) {
    liveEndTimeInput.addEventListener("change", (e) => {
      selectedEndTime = e.target.value;
      document.querySelectorAll(".slot-preset-btn").forEach(b => b.classList.remove("active"));
      updateDuration();
      renderHeatmap();
    });
  }

  /* ---------- SKUs Table Rendering ---------- */

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

    document.querySelectorAll(".sku-checkbox").forEach(cb => {
      cb.addEventListener("change", (e) => {
        const id = e.target.getAttribute("data-id");
        if (e.target.checked) selectedSkuIds.add(id);
        else selectedSkuIds.delete(id);
        if (statSelectedCount) statSelectedCount.textContent = selectedSkuIds.size;
        // Re-run M5 cho đúng tập đã tick (debounce)
        scheduleM5Rerun();
      });
    });
  }

  /* ---------- Combos & Vouchers Rendering ---------- */

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

  // Budget Input: gõ → debounce 600ms → re-run M5 (cho tập SKU đã tick).
  // Việc đổi ngân sách chỉ ảnh hưởng M5 nên tái dùng runM5ForSelected (không load lại cả pipeline).
  if (budgetInput) {
    budgetInput.addEventListener("input", () => {
      const v = Number(budgetInput.value);
      if (budgetHint) {
        if (Number.isFinite(v) && v > 0) budgetHint.textContent = `M5 sẽ chạy lại với ${AREA303.vnd(v)} (sau ~0.6 giây)`;
        else budgetHint.textContent = "Để trống = dùng ngân sách mặc định 500M ₫";
      }
      clearTimeout(budgetRerunTimer);
      budgetRerunTimer = setTimeout(runM5ForSelected, 600);
    });
  }

  if (btnAutoPick) {
    btnAutoPick.addEventListener("click", () => {
      selectedSkuIds.clear();
      allSkus.slice(0, 10).forEach(s => selectedSkuIds.add(s.item_id));
      renderSkusTable();
      if (statSelectedCount) statSelectedCount.textContent = selectedSkuIds.size;
      AREA303.toast("Đã tự động chọn Top 10 SKU có Hero Score cao nhất!", "success");
      // Re-run M5 cho tập Top 10 mới
      scheduleM5Rerun();
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

      const startMins = parseMinutes(selectedStartTime);
      let endMins = parseMinutes(selectedEndTime);
      if (endMins <= startMins) endMins += 24 * 60;
      const durationMins = endMins - startMins;

      const playbookPayload = {
        shop_id: shopId,
        live_date: selectedDate,
        start_time: selectedStartTime,
        end_time: selectedEndTime,
        slot: `${selectedStartTime} – ${selectedEndTime}`,
        duration_mins: durationMins,
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
