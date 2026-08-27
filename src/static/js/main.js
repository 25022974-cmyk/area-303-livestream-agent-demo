/* ============================================================
   AREA_303 — Global JavaScript Utilities
   ============================================================ */

window.AREA303 = (function () {
  "use strict";

  function formatVND(amount) {
    const num = Number(amount || 0);
    if (Math.abs(num) >= 1e6) {
      return (num / 1e6).toFixed(2).replace(/\.00$/, "") + "M ₫";
    }
    if (Math.abs(num) >= 1e3) {
      return Math.round(num / 1000).toLocaleString("vi-VN") + "k ₫";
    }
    return Math.round(num).toLocaleString("vi-VN") + " ₫";
  }

  function formatNum(val) {
    return Math.round(Number(val || 0)).toLocaleString("vi-VN");
  }

  function formatPct(val) {
    return Number(val || 0).toFixed(1).replace(/\.0$/, "") + "%";
  }

  function showToast(message, type = "info") {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      document.body.appendChild(container);
    }

    const toast = document.createElement("div");
    toast.className = "toast";
    if (type === "success") toast.style.background = "#16a34a";
    if (type === "error") toast.style.background = "#dc2626";
    if (type === "warn") toast.style.background = "#d97706";

    toast.textContent = message;
    container.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3000);
  }

  function switchShop(shopId) {
    if (!shopId) return;
    const url = new URL(window.location.href);
    url.searchParams.set("shop_id", shopId);
    window.location.href = url.toString();
  }

  return {
    vnd: formatVND,
    num: formatNum,
    pct: formatPct,
    toast: showToast,
    switchShop: switchShop,
  };
})();
