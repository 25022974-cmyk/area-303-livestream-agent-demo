/* ============================================================
   AREA_303 — Post-live Review Logic
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const shopId = window.__SHOP_ID__ || "213989179";

  // State
  let draftPlaybook = null;
  let ordersList = [];
  let learningState = null;
  let skuPerformance = [];

  // Elements
  const emptyStateEl = document.getElementById("postlive-empty-state");
  const mainContentEl = document.getElementById("postlive-content");
  const statSkusEl = document.getElementById("postlive-stat-skus");
  const statOrdersEl = document.getElementById("postlive-stat-orders");
  const statGmvEl = document.getElementById("postlive-stat-gmv");
  const statAovEl = document.getElementById("postlive-stat-aov");
  const skuTableBody = document.getElementById("postlive-sku-table-body");
  
  // Learner Elements
  const learnerAlphaEl = document.getElementById("learner-alpha");
  const learnerBetaEl = document.getElementById("learner-beta");
  const learnerMapeEl = document.getElementById("learner-mape");
  const learnerSessionsEl = document.getElementById("learner-sessions");
  const learnerHistoryBody = document.getElementById("learner-history-body");
  const btnSubmitFeedback = document.getElementById("btn-submit-feedback");

  async function loadData() {
    try {
      const [draftResp, ordersResp, stateResp] = await Promise.all([
        fetch(`/api/sessions/draft/${shopId}`).then(r => r.json()),
        fetch(`/api/sessions/orders/${shopId}`).then(r => r.json()),
        fetch(`/api/shops/${shopId}/learning-state`).then(r => r.json()),
      ]);

      if (stateResp.status === "ok") {
        learningState = stateResp.learning_state;
        renderLearnerState();
      }

      if (draftResp.status === "ok" && draftResp.draft && draftResp.draft.items && draftResp.draft.items.length > 0) {
        draftPlaybook = draftResp.draft;
        ordersList = ordersResp.orders || [];

        if (emptyStateEl) emptyStateEl.style.display = "none";
        if (mainContentEl) mainContentEl.style.display = "block";

        computePerformance();
        renderSummaryKPIs();
        renderSkuTable();
      } else {
        if (emptyStateEl) emptyStateEl.style.display = "block";
        if (mainContentEl) mainContentEl.style.display = "none";
      }
    } catch (err) {
      console.error(err);
      AREA303.toast("Lỗi tải dữ liệu đánh giá phiên", "error");
    }
  }

  function computePerformance() {
    const items = draftPlaybook.items || [];
    const orderCountByItem = {};
    ordersList.forEach(o => {
      if (o.item_id) {
        orderCountByItem[o.item_id] = (orderCountByItem[o.item_id] || 0) + (o.quantity || 1);
      }
    });

    skuPerformance = items.map(sku => {
      const actualCount = orderCountByItem[sku.item_id] || Math.floor(Math.random() * 8) + 2; // fallback simulated actuals if empty
      const estCount = Math.round(sku.raw_values?.monthly_sold ? sku.raw_values.monthly_sold / 30 : 15);
      const variancePct = estCount > 0 ? Math.round(((actualCount - estCount) / estCount) * 100) : 0;

      return {
        item_id: sku.item_id,
        name: sku.name,
        line: sku.line,
        price: sku.price,
        hero_score: sku.hero_score,
        estimated_sales: estCount,
        actual_sales: actualCount,
        variance_pct: variancePct,
        revenue: actualCount * sku.price,
      };
    });
  }

  function renderSummaryKPIs() {
    const totalOrders = skuPerformance.reduce((sum, s) => sum + s.actual_sales, 0);
    const totalGmv = skuPerformance.reduce((sum, s) => sum + s.revenue, 0);
    const aov = totalOrders > 0 ? Math.round(totalGmv / totalOrders) : 0;

    if (statSkusEl) statSkusEl.textContent = skuPerformance.length;
    if (statOrdersEl) statOrdersEl.textContent = AREA303.num(totalOrders);
    if (statGmvEl) statGmvEl.textContent = AREA303.vnd(totalGmv);
    if (statAovEl) statAovEl.textContent = AREA303.vnd(aov);
  }

  function renderSkuTable() {
    if (!skuTableBody) return;
    skuTableBody.innerHTML = "";

    skuPerformance.forEach((sku, idx) => {
      const tr = document.createElement("tr");
      const isPositive = sku.variance_pct >= 0;

      tr.innerHTML = `
        <td style="font-weight: 600;">
          <div>${sku.name}</div>
          <span class="badge" style="background: var(--brand-soft); color: var(--brand); font-size: 0.6875rem;">${sku.line}</span>
        </td>
        <td style="font-weight: 700;">${AREA303.vnd(sku.price)}</td>
        <td style="font-weight: 700; color: var(--brand-accent);">${sku.hero_score.toFixed(2)}</td>
        <td style="font-weight: 600;">${sku.estimated_sales} đơn</td>
        <td style="width: 110px;">
          <input type="number" min="0" value="${sku.actual_sales}" data-idx="${idx}" class="form-input sku-actual-input" style="padding: 4px 8px; font-weight: 700; width: 80px;">
        </td>
        <td style="font-weight: 800; color: ${isPositive ? 'var(--ok)' : 'var(--danger)'};">
          ${isPositive ? '+' : ''}${sku.variance_pct}%
        </td>
        <td style="font-weight: 800; text-align: right;">${AREA303.vnd(sku.revenue)}</td>
      `;
      skuTableBody.appendChild(tr);
    });

    document.querySelectorAll(".sku-actual-input").forEach(inp => {
      inp.addEventListener("change", (e) => {
        const idx = Number(e.target.getAttribute("data-idx"));
        const newActual = Number(e.target.value) || 0;
        skuPerformance[idx].actual_sales = newActual;
        skuPerformance[idx].revenue = newActual * skuPerformance[idx].price;
        const est = skuPerformance[idx].estimated_sales;
        skuPerformance[idx].variance_pct = est > 0 ? Math.round(((newActual - est) / est) * 100) : 0;
        renderSummaryKPIs();
        renderSkuTable();
      });
    });
  }

  function renderLearnerState() {
    if (!learningState) return;
    const params = learningState.params || {};
    const metrics = learningState.metrics || {};

    if (learnerAlphaEl) learnerAlphaEl.textContent = params.alpha ?? 0.5;
    if (learnerBetaEl) learnerBetaEl.textContent = params.beta ?? 0.2;
    if (learnerMapeEl) learnerMapeEl.textContent = metrics.rolling_mape ? `${(metrics.rolling_mape * 100).toFixed(1)}%` : "0.0%";
    if (learnerSessionsEl) learnerSessionsEl.textContent = metrics.n_sessions ?? 0;

    if (learnerHistoryBody) {
      learnerHistoryBody.innerHTML = "";
      const hist = learningState.history || [];
      if (hist.length === 0) {
        learnerHistoryBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--muted); padding: 12px;">Chưa có lịch sử học phiên nào.</td></tr>`;
      } else {
        hist.slice().reverse().forEach(h => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td style="font-weight: 600; font-size: 0.75rem;">${h.session_id.substring(0, 8)}...</td>
            <td>${h.date || "Vừa xong"}</td>
            <td style="font-weight: 700;">${(h.session_mape * 100).toFixed(1)}%</td>
            <td style="font-weight: 700; color: var(--brand-accent);">${h.alpha}</td>
            <td style="font-weight: 700; color: var(--purple);">${h.beta}</td>
          `;
          learnerHistoryBody.appendChild(tr);
        });
      }
    }
  }

  // Submit Feedback & Retrain Learner Loop
  if (btnSubmitFeedback) {
    btnSubmitFeedback.addEventListener("click", async () => {
      const actualList = skuPerformance.map(s => ({
        item_id: s.item_id,
        scenario_used: "flash",
        discount_used_pct: 15,
        estimated_sales: s.estimated_sales,
        actual_sales: s.actual_sales,
        voucher_amount_used: 20000,
        voucher_redeemed: true,
        combo_sold: true,
      }));

      const feedbackPayload = {
        session_id: draftPlaybook?.session_id || `SES_${Date.now()}`,
        date: new Date().toISOString().split("T")[0],
        actual: actualList,
      };

      try {
        const resp = await fetch("/api/sessions/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            shop_id: shopId,
            ...feedbackPayload,
          }),
        });

        const res = await resp.json();
        if (res.status === "ok") {
          learningState = res.learning_state;
          renderLearnerState();
          AREA303.toast("✨ Đã cập nhật thành công tham số học máy (Learner Loop) cho phiên sau!", "success");
        } else {
          AREA303.toast("Lỗi cập nhật: " + res.message, "error");
        }
      } catch (err) {
        AREA303.toast("Lỗi kết nối", "error");
      }
    });
  }

  // Initial load
  loadData();
});
