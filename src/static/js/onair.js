/* ============================================================
   AREA_303 — On-air Assistant Logic
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const shopId = window.__SHOP_ID__ || "213989179";

  // State
  let draftPlaybook = null;
  let showSlots = [];
  let currentSlotIdx = 0;
  let isLive = false;
  let elapsedSeconds = 0;
  let timerInterval = null;
  let ordersList = [];

  // Elements
  const emptyStateEl = document.getElementById("onair-empty-state");
  const activeShowEl = document.getElementById("onair-active-show");
  const timelineContainer = document.getElementById("timeline-slots");
  const activeSkuCard = document.getElementById("active-sku-card");
  const ordersTableBody = document.getElementById("orders-table-body");
  const ordersCountEl = document.getElementById("orders-count");
  const ordersGmvEl = document.getElementById("orders-gmv");
  const liveTimerEl = document.getElementById("live-timer");
  const btnToggleLive = document.getElementById("btn-toggle-live");
  const btnNextSlot = document.getElementById("btn-next-slot");
  const btnPrevSlot = document.getElementById("btn-prev-slot");
  const btnLogOrder = document.getElementById("btn-log-order");
  const btnFinishShow = document.getElementById("btn-finish-show");

  async function loadDraft() {
    try {
      const resp = await fetch(`/api/sessions/draft/${shopId}`);
      const res = await resp.json();

      if (res.status === "ok" && res.draft && res.draft.items && res.draft.items.length > 0) {
        draftPlaybook = res.draft;
        buildRunOfShow(draftPlaybook);
        if (emptyStateEl) emptyStateEl.style.display = "none";
        if (activeShowEl) activeShowEl.style.display = "grid";
        loadExistingOrders();
        renderRunOfShow();
        renderCurrentSlot();
      } else {
        if (emptyStateEl) emptyStateEl.style.display = "block";
        if (activeShowEl) activeShowEl.style.display = "none";
      }
    } catch (err) {
      console.error(err);
      AREA303.toast("Lỗi tải playbook phiên live", "error");
    }
  }

  function buildRunOfShow(draft) {
    showSlots = [];
    const items = draft.items || [];
    const combos = draft.combos || [];

    // Slot 1: Opening Hero
    if (items.length > 0) {
      showSlots.push({
        role: "opening_hero",
        roleLabel: "Mở Màn · Hero 1",
        item: items[0],
        durationMins: 15,
        hook: `Chào mừng khách xem livestream! Mở màn hôm nay với deal độc quyền cực hot: ${items[0].name}. Giảm ngay trong 15 phút đầu!`,
        action: "Tung voucher khai màn phiên live",
      });
    }

    // Slot 2: Flash Deal
    if (items.length > 1) {
      showSlots.push({
        role: "flash_deal",
        roleLabel: "Flash Sale Giới Hạn",
        item: items[1],
        durationMins: 10,
        hook: `Flash sale chớp nhoáng! Chỉ còn 50 suất giảm sốc cho ${items[1].name}. Bấm mua ngay kẻo hết!`,
        action: "Bật đồng hồ đếm ngược 10 phút flash sale",
      });
    }

    // Slot 3: Combo Bundle
    if (combos.length > 0) {
      const c = combos[0];
      showSlots.push({
        role: "combo",
        roleLabel: "Combo Đột Phá",
        combo: c,
        durationMins: 15,
        hook: `Mua combo siêu hời: ${c.combo_name}. Mua 1 được 2, tiết kiệm ngay ${AREA303.vnd(c.savings)}!`,
        action: "Tặng kèm quà cho đơn đặt trong khung giờ này",
      });
    }

    // Remaining items
    for (let i = 2; i < items.length; i++) {
      showSlots.push({
        role: "standard_deal",
        roleLabel: `Deal #${i + 1}`,
        item: items[i],
        durationMins: 10,
        hook: `Sản phẩm tiếp theo: ${items[i].name}. Đã bán hơn ${AREA303.num(items[i].raw_values?.monthly_sold || 0)} lượt trên sàn!`,
        action: "Nhắc nhở áp mã voucher giảm giá",
      });
    }

    // Closing Slot
    showSlots.push({
      role: "closing",
      roleLabel: "Chốt Phiên Live",
      item: items[0] || null,
      durationMins: 10,
      hook: "Còn 10 phút cuối cùng của phiên live! Điểm lại top 3 sản phẩm bán chạy nhất hôm nay. Đừng bỏ lỡ mã giảm giá cuối cùng!",
      action: "Xả voucher chốt phiên",
    });
  }

  function renderRunOfShow() {
    if (!timelineContainer) return;
    timelineContainer.innerHTML = "";

    showSlots.forEach((slot, idx) => {
      const el = document.createElement("div");
      el.className = "timeline-item";
      if (idx === currentSlotIdx) el.classList.add("active");
      if (idx < currentSlotIdx) el.classList.add("done");

      let title = slot.item ? slot.item.name : (slot.combo ? slot.combo.combo_name : "Kết thúc phiên");
      let price = slot.item ? AREA303.vnd(slot.item.price) : (slot.combo ? AREA303.vnd(slot.combo.bundle_price) : "");

      el.innerHTML = `
        <div class="timeline-num">${idx + 1}</div>
        <div style="flex: 1; min-width: 0;">
          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span class="badge" style="background: var(--brand-soft); color: var(--brand); font-size: 0.6875rem;">${slot.roleLabel}</span>
            <span style="font-size: 0.6875rem; color: var(--muted);">${slot.durationMins} phút</span>
          </div>
          <div style="font-weight: 600; font-size: 0.8125rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; margin-top: 4px;">${title}</div>
          <div style="font-weight: 800; font-size: 0.875rem; color: var(--brand-accent);">${price}</div>
        </div>
      `;

      el.addEventListener("click", () => {
        currentSlotIdx = idx;
        renderRunOfShow();
        renderCurrentSlot();
      });

      timelineContainer.appendChild(el);
    });
  }

  function renderCurrentSlot() {
    if (!activeSkuCard || !showSlots[currentSlotIdx]) return;
    const slot = showSlots[currentSlotIdx];
    const isCombo = !!slot.combo;
    const targetObj = isCombo ? slot.combo : slot.item;

    let title = isCombo ? targetObj.combo_name : (targetObj ? targetObj.name : "Chốt phiên");
    let price = isCombo ? AREA303.vnd(targetObj.bundle_price) : (targetObj ? AREA303.vnd(targetObj.price) : "-");
    let origPrice = isCombo ? AREA303.vnd(targetObj.original_total_price) : (targetObj ? AREA303.vnd(targetObj.price_original) : "-");

    activeSkuCard.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 12px;">
        <div>
          <span class="badge" style="background: var(--brand); color: #ffffff;">${slot.roleLabel}</span>
          <span class="badge" style="background: var(--ok-bg); color: var(--ok); margin-left: 6px;">Thời lượng: ${slot.durationMins} phút</span>
        </div>
        <div style="text-align: right;">
          <div style="font-size: 0.75rem; color: var(--muted); text-decoration: line-through;">${origPrice}</div>
          <div style="font-size: 1.5rem; font-weight: 800; color: var(--danger);">${price}</div>
        </div>
      </div>

      <h2 style="font-size: 1.125rem; font-weight: 800; color: var(--text); margin-bottom: 12px; line-height: 1.3;">${title}</h2>

      <div style="background: #f8fafc; border: 1px solid var(--line); border-radius: 8px; padding: 12px; margin-bottom: 14px;">
        <div style="font-size: 0.75rem; font-weight: 700; color: var(--brand-accent); text-transform: uppercase; margin-bottom: 4px;">📢 AI Talk Track & Kịch Bản Chốt Deal:</div>
        <p style="font-size: 0.875rem; font-weight: 500; color: var(--text); line-height: 1.5;">"${slot.hook}"</p>
      </div>

      <div style="background: #fef2f2; border: 1px solid var(--danger-border); border-radius: 8px; padding: 10px 12px; display: flex; align-items: center; justify-content: space-between;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="live-dot"></span>
          <span style="font-size: 0.8125rem; font-weight: 700; color: var(--danger);">Hành động đề xuất:</span>
          <span style="font-size: 0.8125rem; color: var(--text);">${slot.action}</span>
        </div>
        <button id="btn-trigger-action" class="btn btn-sm btn-danger">Kích Hoạt Deal</button>
      </div>
    `;

    const btnAct = document.getElementById("btn-trigger-action");
    if (btnAct) {
      btnAct.addEventListener("click", () => {
        AREA303.toast("⚡ Đã kích hoạt Flash Deal / Voucher lên màn hình livestream!", "success");
      });
    }
  }

  async function loadExistingOrders() {
    try {
      const resp = await fetch(`/api/sessions/orders/${shopId}`);
      const res = await resp.json();
      if (res.status === "ok") {
        ordersList = res.orders || [];
        renderOrders();
      }
    } catch (err) {
      console.error(err);
    }
  }

  function renderOrders() {
    if (!ordersTableBody) return;
    ordersTableBody.innerHTML = "";

    let totalGmv = 0;
    ordersList.forEach((ord, idx) => {
      totalGmv += (ord.price * (ord.quantity || 1));
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 600; color: var(--muted); font-size: 0.75rem;">${ord.order_id}</td>
        <td style="font-weight: 600;">${ord.product_name || "Sản phẩm Live"}</td>
        <td style="font-weight: 700; text-align: right;">${AREA303.vnd(ord.price)}</td>
      `;
      ordersTableBody.prepend(tr);
    });

    if (ordersCountEl) ordersCountEl.textContent = ordersList.length;
    if (ordersGmvEl) ordersGmvEl.textContent = AREA303.vnd(totalGmv);
  }

  async function logLiveOrder() {
    const slot = showSlots[currentSlotIdx];
    if (!slot) return;
    const isCombo = !!slot.combo;
    const targetObj = isCombo ? slot.combo : slot.item;

    const orderPayload = {
      item_id: isCombo ? targetObj.hero_item_id : (targetObj ? targetObj.item_id : "unknown"),
      product_name: isCombo ? targetObj.combo_name : (targetObj ? targetObj.name : "Sản phẩm Live"),
      price: isCombo ? targetObj.bundle_price : (targetObj ? targetObj.price : 0),
      quantity: 1,
      voucher_applied: true,
    };

    try {
      const resp = await fetch("/api/sessions/log-order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          shop_id: shopId,
          order: orderPayload,
        }),
      });
      const res = await resp.json();
      if (res.status === "ok") {
        ordersList = res.orders || [];
        renderOrders();
        AREA303.toast("🛒 Đã ghi nhận 1 đơn hàng mới!", "success");
      }
    } catch (err) {
      AREA303.toast("Lỗi ghi nhận đơn hàng", "error");
    }
  }

  // Live Timer Controls
  if (btnToggleLive) {
    btnToggleLive.addEventListener("click", () => {
      isLive = !isLive;
      if (isLive) {
        btnToggleLive.textContent = "⏸ Tạm Dừng Live";
        btnToggleLive.className = "btn btn-secondary";
        timerInterval = setInterval(() => {
          elapsedSeconds++;
          const mins = Math.floor(elapsedSeconds / 60);
          const secs = elapsedSeconds % 60;
          if (liveTimerEl) liveTimerEl.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }, 1000);
        AREA303.toast("🔴 Phiên livestream đang ON-AIR!", "success");
      } else {
        btnToggleLive.textContent = "▶ Bắt Đầu Live";
        btnToggleLive.className = "btn btn-primary";
        clearInterval(timerInterval);
      }
    });
  }

  if (btnNextSlot) {
    btnNextSlot.addEventListener("click", () => {
      if (currentSlotIdx < showSlots.length - 1) {
        currentSlotIdx++;
        renderRunOfShow();
        renderCurrentSlot();
      }
    });
  }

  if (btnPrevSlot) {
    btnPrevSlot.addEventListener("click", () => {
      if (currentSlotIdx > 0) {
        currentSlotIdx--;
        renderRunOfShow();
        renderCurrentSlot();
      }
    });
  }

  if (btnLogOrder) {
    btnLogOrder.addEventListener("click", logLiveOrder);
  }

  if (btnFinishShow) {
    btnFinishShow.addEventListener("click", () => {
      clearInterval(timerInterval);
      AREA303.toast("Đã kết thúc phiên live! Chuyển sang Post-live Review...", "success");
      setTimeout(() => {
        window.location.href = `/postlive?shop_id=${shopId}`;
      }, 600);
    });
  }

  // Initial load
  loadDraft();
});
