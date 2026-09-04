/* ============================================================
   AREA_303 — Generated Data Management Dashboard Controller
   ============================================================ */

document.addEventListener("DOMContentLoaded", () => {
  const shopId = window.__SHOP_ID__ || "213989179";

  // Elements - KPIs
  const kpiTotalFiles = document.getElementById("kpi-total-files");
  const kpiTotalBytes = document.getElementById("kpi-total-bytes");
  const kpiDraftStatus = document.getElementById("kpi-draft-status");
  const kpiDraftSub = document.getElementById("kpi-draft-sub");
  const kpiOrdersCount = document.getElementById("kpi-orders-count");
  const kpiOrdersGmv = document.getElementById("kpi-orders-gmv");
  const kpiLearnerWeights = document.getElementById("kpi-learner-weights");
  const kpiLearnerSessions = document.getElementById("kpi-learner-sessions");

  // Tab Badges
  const tabPlaybookBadge = document.getElementById("tab-playbook-badge");
  const tabOrdersBadge = document.getElementById("tab-orders-badge");
  const tabReviewsBadge = document.getElementById("tab-reviews-badge");
  const archivedCountBadge = document.getElementById("archived-count-badge");

  // Tables
  const playbooksTableBody = document.getElementById("playbooks-table-body");
  const ordersTableBody = document.getElementById("orders-table-body");
  const learnerHistoryBody = document.getElementById("learner-history-body");
  const reviewsTableBody = document.getElementById("reviews-table-body");

  // Draft Elements
  const draftSlotText = document.getElementById("draft-slot-text");
  const draftMetaText = document.getElementById("draft-meta-text");
  const draftActions = document.getElementById("draft-actions");

  // Learner Inputs
  const inputLearnerAlpha = document.getElementById("input-learner-alpha");
  const inputLearnerBeta = document.getElementById("input-learner-beta");
  const btnSaveLearnerParams = document.getElementById("btn-save-learner-params");
  const btnResetLearner = document.getElementById("btn-reset-learner");

  // Orders Actions
  const btnExportOrdersJson = document.getElementById("btn-export-orders-json");
  const btnClearAllOrders = document.getElementById("btn-clear-all-orders");

  // Purge & Refresh
  const btnPurgeShop = document.getElementById("btn-purge-shop");
  const btnRefresh = document.getElementById("btn-refresh-dashboard");

  // Modals
  const modalJson = document.getElementById("modal-json-viewer");
  const modalJsonTitle = document.getElementById("modal-json-title");
  const modalJsonContent = document.getElementById("modal-json-content");
  const btnCopyModalJson = document.getElementById("btn-copy-modal-json");

  const modalEditOrder = document.getElementById("modal-edit-order");
  const editOrderId = document.getElementById("edit-order-id");
  const editOrderIdDisplay = document.getElementById("edit-order-id-display");
  const editOrderName = document.getElementById("edit-order-name");
  const editOrderPrice = document.getElementById("edit-order-price");
  const editOrderQty = document.getElementById("edit-order-qty");
  const btnSaveEditOrder = document.getElementById("btn-save-edit-order");

  const modalConfirm = document.getElementById("modal-confirm");
  const confirmTitle = document.getElementById("confirm-title");
  const confirmMessage = document.getElementById("confirm-message");
  const btnConfirmOk = document.getElementById("btn-confirm-ok");
  let onConfirmCallback = null;

  // Cached state
  let currentOrders = [];

  function formatBytes(bytes) {
    const num = Number(bytes || 0);
    if (num < 1024) return num + " B";
    if (num < 1024 * 1024) return (num / 1024).toFixed(1) + " KB";
    return (num / (1024 * 1024)).toFixed(2) + " MB";
  }

  /* ---------- Modal Helpers ---------- */
  function openModal(modal) {
    if (modal) modal.style.display = "flex";
  }

  function closeModal(modal) {
    if (modal) modal.style.display = "none";
  }

  document.querySelectorAll(".modal-close-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      closeModal(modalJson);
      closeModal(modalEditOrder);
      closeModal(modalConfirm);
    });
  });

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeModal(modalJson);
      closeModal(modalEditOrder);
      closeModal(modalConfirm);
    }
  });

  function showConfirm(title, message, onOk) {
    if (confirmTitle) confirmTitle.textContent = title;
    if (confirmMessage) confirmMessage.textContent = message;
    onConfirmCallback = onOk;
    openModal(modalConfirm);
  }

  if (btnConfirmOk) {
    btnConfirmOk.addEventListener("click", async () => {
      closeModal(modalConfirm);
      if (onConfirmCallback) {
        await onConfirmCallback();
        onConfirmCallback = null;
      }
    });
  }

  if (btnCopyModalJson && modalJsonContent) {
    btnCopyModalJson.addEventListener("click", () => {
      navigator.clipboard.writeText(modalJsonContent.textContent || "")
        .then(() => AREA303.toast("📋 Đã sao chép nội dung JSON!", "success"))
        .catch(() => AREA303.toast("Lỗi sao chép vào clipboard", "warn"));
    });
  }

  /* ---------- Tab Navigation ---------- */
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const targetId = btn.getAttribute("data-tab");
      document.querySelectorAll(".tab-btn").forEach(b => {
        b.classList.remove("active");
        b.classList.add("btn-secondary");
      });
      btn.classList.add("active");
      btn.classList.remove("btn-secondary");

      document.querySelectorAll(".tab-content").forEach(panel => {
        panel.style.display = (panel.id === targetId) ? "block" : "none";
      });
    });
  });

  /* ---------- Data Loaders ---------- */
  async function loadSummary() {
    try {
      const res = await fetch(`/api/dashboard/${shopId}/summary`).then(r => r.json());
      if (res.status === "ok") {
        const s = res.summary;
        if (kpiTotalFiles) kpiTotalFiles.textContent = `${s.total_files} tệp tin`;
        if (kpiTotalBytes) kpiTotalBytes.textContent = formatBytes(s.total_bytes);

        // Draft
        if (s.draft_playbook && s.draft_playbook.exists) {
          if (kpiDraftStatus) kpiDraftStatus.textContent = "Sẵn sàng";
          if (kpiDraftSub) kpiDraftSub.textContent = `${s.draft_playbook.items_count} SKU · ${s.draft_playbook.slot || "Chưa chọn slot"}`;
        } else {
          if (kpiDraftStatus) kpiDraftStatus.textContent = "Chưa có";
          if (kpiDraftSub) kpiDraftSub.textContent = "Lập draft tại Pre-live";
        }

        // Orders
        const ord = s.orders || {};
        if (kpiOrdersCount) kpiOrdersCount.textContent = `${ord.count} đơn`;
        if (kpiOrdersGmv) kpiOrdersGmv.textContent = AREA303.vnd(ord.gmv);

        // Learner
        const lrn = s.learning_state || {};
        if (kpiLearnerWeights) kpiLearnerWeights.textContent = `α=${lrn.alpha || 0.5}, β=${lrn.beta || 0.2}`;
        if (kpiLearnerSessions) kpiLearnerSessions.textContent = `${lrn.n_sessions || 0} phiên đã học`;

        // Tab Badges
        const pbTotal = (s.draft_playbook?.exists ? 1 : 0) + (s.archived_playbooks_count || 0);
        if (tabPlaybookBadge) tabPlaybookBadge.textContent = pbTotal;
        if (tabOrdersBadge) tabOrdersBadge.textContent = ord.count || 0;
        if (tabReviewsBadge) tabReviewsBadge.textContent = s.archived_reviews_count || 0;
        if (archivedCountBadge) archivedCountBadge.textContent = `${s.archived_playbooks_count || 0} bản ghi`;
      }
    } catch (err) {
      console.error(err);
      AREA303.toast("Lỗi tải thông tin tổng quan dashboard", "error");
    }
  }

  async function loadDraftPlaybook() {
    try {
      const res = await fetch(`/api/sessions/draft/${shopId}`).then(r => r.json());
      if (res.status === "ok" && res.draft) {
        const d = res.draft;
        const itemsCount = (d.items || []).length;
        const combosCount = (d.combos || []).length;
        const vouchersCount = (d.vouchers || []).length;
        const dt = d.updated_at ? new Date(d.updated_at).toLocaleString("vi-VN") : "Gần đây";

        if (draftSlotText) draftSlotText.textContent = `Khung giờ: ${d.slot || "20:00 – 22:00"}`;
        if (draftMetaText) draftMetaText.textContent = `Cập nhật: ${dt} · ${itemsCount} SKU · ${combosCount} combo · ${vouchersCount} voucher`;

        if (draftActions) {
          draftActions.innerHTML = `
            <button class="btn btn-secondary btn-sm" id="btn-view-draft">🔍 Xem JSON</button>
            <a href="/prelive?shop_id=${shopId}" class="btn btn-secondary btn-sm">✏️ Chỉnh Sửa</a>
            <button class="btn btn-danger btn-sm" id="btn-delete-draft">🗑 Xóa</button>
          `;
          document.getElementById("btn-view-draft").addEventListener("click", () => {
            showJsonModal("Playbook Bản Nháp Hiện Hành (draft_playbook.json)", d);
          });
          document.getElementById("btn-delete-draft").addEventListener("click", () => {
            showConfirm("Xóa Bản Nháp Hiện Hành", "Bạn có chắc muốn xóa draft_playbook.json không?", async () => {
              const delRes = await fetch(`/api/dashboard/${shopId}/draft`, { method: "DELETE" }).then(r => r.json());
              if (delRes.status === "ok") {
                AREA303.toast("Đã xóa draft playbook!", "success");
                refreshAll();
              } else {
                AREA303.toast("Lỗi xóa draft: " + delRes.message, "error");
              }
            });
          });
        }
      } else {
        if (draftSlotText) draftSlotText.textContent = "Chưa có bản nháp nào đang hoạt động";
        if (draftMetaText) draftMetaText.textContent = "Vào Pre-live Planner để tạo bản nháp mới.";
        if (draftActions) {
          draftActions.innerHTML = `<a href="/prelive?shop_id=${shopId}" class="btn btn-primary btn-sm">+ Lập Bản Nháp Mới</a>`;
        }
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function loadArchivedPlaybooks() {
    if (!playbooksTableBody) return;
    try {
      const res = await fetch(`/api/dashboard/${shopId}/playbooks`).then(r => r.json());
      if (res.status === "ok") {
        const list = res.archived || [];
        if (list.length === 0) {
          playbooksTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--muted); padding: 1.5rem;">Chưa có bản lưu trữ playbook nào trong playbooks/</td></tr>`;
          return;
        }

        playbooksTableBody.innerHTML = "";
        list.forEach(p => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td style="font-weight: 700; font-family: monospace; font-size: 0.8125rem;">${p.filename}</td>
            <td style="font-weight: 600;">${p.slot || "-"}</td>
            <td style="text-align: center;"><span class="badge" style="background: var(--brand-soft); color: var(--brand); font-weight: 700;">${p.items_count}</span></td>
            <td style="text-align: center;"><span class="badge" style="background: var(--purple-bg); color: var(--purple); font-weight: 700;">${p.combos_count}</span></td>
            <td style="text-align: right; color: var(--muted); font-size: 0.75rem;">${formatBytes(p.size_bytes)}</td>
            <td style="text-align: right;">
              <button class="btn btn-secondary btn-sm btn-view-pb" data-fn="${p.filename}" style="padding: 2px 6px; font-size: 0.75rem;">Xem</button>
              <button class="btn btn-secondary btn-sm btn-restore-pb" data-fn="${p.filename}" style="padding: 2px 6px; font-size: 0.75rem; color: var(--brand-accent);">↺ Khôi Phục</button>
              <button class="btn btn-danger btn-sm btn-delete-pb" data-fn="${p.filename}" style="padding: 2px 6px; font-size: 0.75rem;">Xóa</button>
            </td>
          `;
          playbooksTableBody.appendChild(tr);
        });

        // Wire buttons
        playbooksTableBody.querySelectorAll(".btn-view-pb").forEach(btn => {
          btn.addEventListener("click", async () => {
            const fn = btn.getAttribute("data-fn");
            const d = await fetch(`/api/dashboard/${shopId}/playbooks/${fn}`).then(r => r.json());
            if (d.status === "ok") showJsonModal(`Playbook: ${fn}`, d.data);
          });
        });

        playbooksTableBody.querySelectorAll(".btn-restore-pb").forEach(btn => {
          btn.addEventListener("click", () => {
            const fn = btn.getAttribute("data-fn");
            showConfirm("Khôi Phục Playbook", `Khôi phục '${fn}' thành bản nháp hiện hành?`, async () => {
              const r = await fetch(`/api/dashboard/${shopId}/playbooks/${fn}/restore`, { method: "POST" }).then(res => res.json());
              if (r.status === "ok") {
                AREA303.toast("✨ Đã khôi phục playbook thành công!", "success");
                refreshAll();
              } else {
                AREA303.toast("Lỗi khôi phục: " + r.message, "error");
              }
            });
          });
        });

        playbooksTableBody.querySelectorAll(".btn-delete-pb").forEach(btn => {
          btn.addEventListener("click", () => {
            const fn = btn.getAttribute("data-fn");
            showConfirm("Xóa Bản Lưu Trữ", `Xác nhận xóa tệp '${fn}' khỏi hệ thống?`, async () => {
              const r = await fetch(`/api/dashboard/${shopId}/playbooks/${fn}`, { method: "DELETE" }).then(res => res.json());
              if (r.status === "ok") {
                AREA303.toast("Đã xóa bản lưu trữ!", "success");
                refreshAll();
              } else {
                AREA303.toast("Lỗi xóa: " + r.message, "error");
              }
            });
          });
        });
      }
    } catch (err) {
      console.error(err);
    }
  }

  async function loadOrders() {
    if (!ordersTableBody) return;
    try {
      const res = await fetch(`/api/dashboard/${shopId}/orders`).then(r => r.json());
      if (res.status === "ok") {
        currentOrders = res.orders || [];
        if (currentOrders.length === 0) {
          ordersTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--muted); padding: 1.5rem;">Chưa có đơn hàng nào trong orders.json</td></tr>`;
          return;
        }

        ordersTableBody.innerHTML = "";
        currentOrders.forEach(o => {
          const tr = document.createElement("tr");
          const total = (o.price || 0) * (o.quantity || 1);
          tr.innerHTML = `
            <td style="font-weight: 600; font-size: 0.75rem; color: var(--muted);">${o.order_id || "-"}</td>
            <td style="font-weight: 700;">${o.product_name || "Sản phẩm"}</td>
            <td style="text-align: right; font-weight: 600;">${AREA303.vnd(o.price)}</td>
            <td style="text-align: center;"><span class="badge" style="background: var(--brand-soft); color: var(--brand); font-weight: 700;">${o.quantity || 1}</span></td>
            <td style="text-align: right; font-weight: 800; color: var(--ok);">${AREA303.vnd(total)}</td>
            <td style="text-align: right;">
              <button class="btn btn-secondary btn-sm btn-edit-order" data-id="${o.order_id}" style="padding: 2px 6px; font-size: 0.75rem;">Sửa</button>
              <button class="btn btn-danger btn-sm btn-del-order" data-id="${o.order_id}" style="padding: 2px 6px; font-size: 0.75rem;">Xóa</button>
            </td>
          `;
          ordersTableBody.appendChild(tr);
        });

        // Wire edit buttons
        ordersTableBody.querySelectorAll(".btn-edit-order").forEach(btn => {
          btn.addEventListener("click", () => {
            const oid = btn.getAttribute("data-id");
            const order = currentOrders.find(x => String(x.order_id) === String(oid));
            if (order) {
              if (editOrderId) editOrderId.value = order.order_id;
              if (editOrderIdDisplay) editOrderIdDisplay.textContent = order.order_id;
              if (editOrderName) editOrderName.value = order.product_name || "";
              if (editOrderPrice) editOrderPrice.value = order.price || 0;
              if (editOrderQty) editOrderQty.value = order.quantity || 1;
              openModal(modalEditOrder);
            }
          });
        });

        // Wire delete buttons
        ordersTableBody.querySelectorAll(".btn-del-order").forEach(btn => {
          btn.addEventListener("click", () => {
            const oid = btn.getAttribute("data-id");
            showConfirm("Xóa Đơn Hàng", `Bạn có chắc muốn xóa đơn hàng '${oid}' không?`, async () => {
              const r = await fetch(`/api/dashboard/${shopId}/orders/${oid}`, { method: "DELETE" }).then(res => res.json());
              if (r.status === "ok") {
                AREA303.toast("Đã xóa đơn hàng!", "success");
                refreshAll();
              } else {
                AREA303.toast("Lỗi xóa đơn: " + r.message, "error");
              }
            });
          });
        });
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Save Edit Order
  if (btnSaveEditOrder) {
    btnSaveEditOrder.addEventListener("click", async () => {
      const oid = editOrderId?.value;
      if (!oid) return;
      const payload = {
        product_name: editOrderName?.value,
        price: Number(editOrderPrice?.value) || 0,
        quantity: Number(editOrderQty?.value) || 1,
      };

      try {
        const res = await fetch(`/api/dashboard/${shopId}/orders/${oid}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }).then(r => r.json());

        if (res.status === "ok") {
          closeModal(modalEditOrder);
          AREA303.toast("Đã cập nhật đơn hàng thành công!", "success");
          refreshAll();
        } else {
          AREA303.toast("Lỗi sửa đơn: " + res.message, "error");
        }
      } catch (err) {
        AREA303.toast("Lỗi kết nối", "error");
      }
    });
  }

  // Export Orders JSON
  if (btnExportOrdersJson) {
    btnExportOrdersJson.addEventListener("click", () => {
      const blob = new Blob([JSON.stringify(currentOrders, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `orders_${shopId}_${new Date().toISOString().split("T")[0]}.json`;
      a.click();
      URL.revokeObjectURL(url);
      AREA303.toast("Đã xuất tệp đơn hàng JSON!", "success");
    });
  }

  // Clear All Orders
  if (btnClearAllOrders) {
    btnClearAllOrders.addEventListener("click", () => {
      showConfirm("Xóa Toàn Bộ Đơn Hàng", "Hành động này sẽ xóa sạch nhật ký đơn hàng On-air (orders.json). Tiếp tục?", async () => {
        const res = await fetch(`/api/dashboard/${shopId}/orders`, { method: "DELETE" }).then(r => r.json());
        if (res.status === "ok") {
          AREA303.toast("Đã xóa sạch đơn hàng!", "success");
          refreshAll();
        } else {
          AREA303.toast("Lỗi xóa đơn: " + res.message, "error");
        }
      });
    });
  }

  async function loadLearner() {
    try {
      const res = await fetch(`/api/dashboard/${shopId}/learning-state`).then(r => r.json());
      if (res.status === "ok") {
        const state = res.learning_state || {};
        const params = state.params || {};
        if (inputLearnerAlpha) inputLearnerAlpha.value = params.alpha !== undefined ? params.alpha : 0.5;
        if (inputLearnerBeta) inputLearnerBeta.value = params.beta !== undefined ? params.beta : 0.2;

        const hist = state.history || [];
        if (learnerHistoryBody) {
          if (hist.length === 0) {
            learnerHistoryBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--muted); padding: 1rem;">Chưa có lịch sử học phiên nào.</td></tr>`;
          } else {
            learnerHistoryBody.innerHTML = "";
            hist.slice().reverse().forEach(h => {
              const tr = document.createElement("tr");
              tr.innerHTML = `
                <td style="font-weight: 700; font-family: monospace; font-size: 0.8125rem;">${(h.session_id || "").substring(0, 16)}...</td>
                <td>${h.date || "Vừa xong"}</td>
                <td style="text-align: right; font-weight: 700; color: var(--ok);">${((h.session_mape || 0) * 100).toFixed(1)}%</td>
                <td style="text-align: center; font-weight: 700; color: var(--brand-accent);">${h.alpha}</td>
                <td style="text-align: center; font-weight: 700; color: var(--purple);">${h.beta}</td>
              `;
              learnerHistoryBody.appendChild(tr);
            });
          }
        }
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Save Learner Parameters
  if (btnSaveLearnerParams) {
    btnSaveLearnerParams.addEventListener("click", async () => {
      const alpha = Number(inputLearnerAlpha?.value);
      const beta = Number(inputLearnerBeta?.value);
      try {
        const res = await fetch(`/api/dashboard/${shopId}/learning-state`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ alpha, beta }),
        }).then(r => r.json());

        if (res.status === "ok") {
          AREA303.toast("✨ Đã lưu cập nhật trọng số Alpha & Beta!", "success");
          refreshAll();
        } else {
          AREA303.toast("Lỗi cập nhật trọng số: " + res.message, "error");
        }
      } catch (err) {
        AREA303.toast("Lỗi kết nối", "error");
      }
    });
  }

  // Reset Learner State
  if (btnResetLearner) {
    btnResetLearner.addEventListener("click", () => {
      showConfirm("Đặt Lại Học Máy", "Đặt lại toàn bộ tham số về mặc định ban đầu (Alpha=0.5, Beta=0.2)?", async () => {
        const res = await fetch(`/api/dashboard/${shopId}/learning-state/reset`, { method: "POST" }).then(r => r.json());
        if (res.status === "ok") {
          AREA303.toast("Đã đặt lại trạng thái học máy về mặc định!", "success");
          refreshAll();
        } else {
          AREA303.toast("Lỗi reset: " + res.message, "error");
        }
      });
    });
  }

  async function loadReviews() {
    if (!reviewsTableBody) return;
    try {
      const res = await fetch(`/api/dashboard/${shopId}/reviews`).then(r => r.json());
      if (res.status === "ok") {
        const list = res.reviews || [];
        if (list.length === 0) {
          reviewsTableBody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--muted); padding: 1.5rem;">Chưa có tệp đánh giá post-live nào trong reviews/</td></tr>`;
          return;
        }

        reviewsTableBody.innerHTML = "";
        list.forEach(r => {
          const tr = document.createElement("tr");
          tr.innerHTML = `
            <td style="font-weight: 700; font-family: monospace; font-size: 0.8125rem;">${r.filename}</td>
            <td style="font-weight: 600;">${r.session_id || "-"}</td>
            <td>${r.date || "-"}</td>
            <td style="text-align: center;"><span class="badge" style="background: var(--brand-soft); color: var(--brand); font-weight: 700;">${r.sku_count}</span></td>
            <td style="text-align: right; color: var(--muted); font-size: 0.75rem;">${formatBytes(r.size_bytes)}</td>
            <td style="text-align: right;">
              <button class="btn btn-secondary btn-sm btn-view-rv" data-fn="${r.filename}" style="padding: 2px 6px; font-size: 0.75rem;">Xem</button>
              <button class="btn btn-danger btn-sm btn-del-rv" data-fn="${r.filename}" style="padding: 2px 6px; font-size: 0.75rem;">Xóa</button>
            </td>
          `;
          reviewsTableBody.appendChild(tr);
        });

        // Wire view/delete
        reviewsTableBody.querySelectorAll(".btn-view-rv").forEach(btn => {
          btn.addEventListener("click", async () => {
            const fn = btn.getAttribute("data-fn");
            const d = await fetch(`/api/dashboard/${shopId}/reviews/${fn}`).then(res => res.json());
            if (d.status === "ok") showJsonModal(`Báo Cáo Review: ${fn}`, d.data);
          });
        });

        reviewsTableBody.querySelectorAll(".btn-del-rv").forEach(btn => {
          btn.addEventListener("click", () => {
            const fn = btn.getAttribute("data-fn");
            showConfirm("Xóa Báo Cáo", `Bạn có chắc muốn xóa tệp '${fn}' khỏi hệ thống không?`, async () => {
              const res = await fetch(`/api/dashboard/${shopId}/reviews/${fn}`, { method: "DELETE" }).then(r => r.json());
              if (res.status === "ok") {
                AREA303.toast("Đã xóa tệp báo cáo!", "success");
                refreshAll();
              } else {
                AREA303.toast("Lỗi xóa review: " + res.message, "error");
              }
            });
          });
        });
      }
    } catch (err) {
      console.error(err);
    }
  }

  // Purge Shop Generated Data
  if (btnPurgeShop) {
    btnPurgeShop.addEventListener("click", () => {
      showConfirm(
        "Xác Nhận Xóa Dữ Liệu Tạm",
        `CẢNH BÁO: Thao tác này sẽ xóa draft_playbook, orders.json, tất cả playbooks, reviews và reset learner cho shop ID ${shopId}. Bạn có chắc chắn muốn tiếp tục?`,
        async () => {
          try {
            const res = await fetch(`/api/dashboard/${shopId}/purge`, { method: "POST" }).then(r => r.json());
            if (res.status === "ok") {
              AREA303.toast("🧹 Đã dọn dẹp sạch toàn bộ dữ liệu phát sinh của shop!", "success");
              refreshAll();
            } else {
              AREA303.toast("Lỗi dọn dẹp: " + res.message, "error");
            }
          } catch (err) {
            AREA303.toast("Lỗi kết nối máy chủ", "error");
          }
        }
      );
    });
  }

  function showJsonModal(title, dataObj) {
    if (modalJsonTitle) modalJsonTitle.textContent = title;
    if (modalJsonContent) modalJsonContent.textContent = JSON.stringify(dataObj, null, 2);
    openModal(modalJson);
  }

  function refreshAll() {
    loadSummary();
    loadDraftPlaybook();
    loadArchivedPlaybooks();
    loadOrders();
    loadLearner();
    loadReviews();
  }

  if (btnRefresh) {
    btnRefresh.addEventListener("click", () => {
      refreshAll();
      AREA303.toast("Đã làm mới dữ liệu!", "info");
    });
  }

  // Initial load
  refreshAll();
});
