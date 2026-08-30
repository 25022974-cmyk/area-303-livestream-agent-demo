# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""High-level AI features built on top of the LLM proxy client.

Two entry points:
    * suggest_next_slot  — in-live suggestion for the upcoming slot, called after a
      slot ends (the app's "Slot tiep" action). Watches the slot's order log and the
      online-learner weight trend.
    * review_post_live   — post-live text report / decision, called right after the
      learner loop updates alpha/beta/MAPE from submitted feedback.

Both functions are total: they never raise. They return ``None`` when the proxy is
not configured or when the call fails, so callers can degrade gracefully.
"""

import json
from typing import Any, Dict, List, Optional

from .ai_client import AIClientError, chat, is_ai_configured


# ---------------------------------------------------------------------------
# Helpers: server-side mirror of onair.js buildRunOfShow (compact, no DOM).
# ---------------------------------------------------------------------------

def _summarize_run_of_show(draft: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Rebuilds the run-of-show plan server-side, mirroring onair.js buildRunOfShow.

    Returns a compact list of slots: [{role, roleLabel, name, price, item_id,
    combo_id, durationMins, hook, action}]. Used to describe the finished slot and
    the upcoming one to the AI.
    """
    slots: List[Dict[str, Any]] = []
    items = draft.get("items") or []
    combos = draft.get("combos") or []

    def _slot(role, label, *, item=None, combo=None, duration=10,
              hook="", action=""):
        if item is not None:
            return {
                "role": role, "roleLabel": label,
                "name": item.get("name"),
                "price": item.get("price"),
                "item_id": item.get("item_id"),
                "combo_id": None,
                "durationMins": duration, "hook": hook, "action": action,
            }
        # combo
        return {
            "role": role, "roleLabel": label,
            "name": combo.get("combo_name"),
            "price": combo.get("bundle_price"),
            "item_id": combo.get("hero_item_id"),
            "combo_id": combo.get("combo_id"),
            "durationMins": duration, "hook": hook, "action": action,
        }

    if items:
        slots.append(_slot(
            "opening_hero", "Mo Man . Hero 1", item=items[0], duration=15,
            hook=f"Chao mung khach xem livestream! Deal doc quyen cuc hot: {items[0].get('name')}.",
            action="Tung voucher khai man",
        ))
    if len(items) > 1:
        slots.append(_slot(
            "flash_deal", "Flash Sale", item=items[1], duration=10,
            hook=f"Flash sale chop nhoang! Chi con 50 suat giam soc cho {items[1].get('name')}.",
            action="Bat dong ho dem nguoc flash sale",
        ))
    if combos:
        slots.append(_slot(
            "combo", "Combo Dot Pha", combo=combos[0], duration=15,
            hook=f"Mua combo sieu hoi: {combos[0].get('combo_name')}.",
            action="Tang kem qua cho don dat trong khung gio nay",
        ))
    for i, it in enumerate(items):
        if i < 2:
            continue
        slots.append(_slot(
            f"standard_deal", f"Deal #{i + 1}", item=it, duration=10,
            hook=f"San pham tiep theo: {it.get('name')}.",
            action="Nhac nho ap ma voucher giam gia",
        ))
    if items:
        slots.append(_slot(
            "closing", "Chot Phien Live", item=items[0], duration=10,
            hook="Con 10 phut cuoi cua phien live! Diem lai top 3 san pham ban chay nhat.",
            action="Xa voucher chot phien",
        ))
    return slots


def _filter_slot_orders(slot: Optional[Dict[str, Any]],
                        orders: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Returns only orders belonging to given slot (matched by item_id / name)."""
    if not slot or not orders:
        return []
    item_id = slot.get("item_id")
    name = slot.get("name")
    matched: List[Dict[str, Any]] = []
    for o in orders:
        o_item = o.get("item_id")
        o_name = o.get("product_name")
        if item_id and o_item and str(o_item) == str(item_id):
            matched.append(o)
        elif name and o_name and str(name) == str(o_name):
            matched.append(o)
    return matched


def _learning_state_brief(state: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    state = state or {}
    params = state.get("params") or {}
    metrics = state.get("metrics") or {}
    return {
        "alpha": params.get("alpha"),
        "beta": params.get("beta"),
        "rolling_mape": metrics.get("rolling_mape"),
        "rolling_redeem_rate": metrics.get("rolling_redeem_rate"),
        "n_sessions": metrics.get("n_sessions"),
        "history": state.get("history") or [],
    }


# ---------------------------------------------------------------------------
# In-live suggestion
# ---------------------------------------------------------------------------

def suggest_next_slot(*, shop_id: str, draft: Dict[str, Any],
                      current_slot_index: int, slot_orders: List[Dict[str, Any]],
                      learning_state: Optional[Dict[str, Any]]) -> Optional[str]:
    """Text suggestion for the next slot, watching the finished slot's order log.

    ``current_slot_index`` is the index of the slot that just finished (after the
    UI advanced to the next one). Returns None if AI not configured / call fails.
    """
    if not is_ai_configured():
        return None

    plan = _summarize_run_of_show(draft)
    idx = int(current_slot_index or 0)
    finished = plan[idx] if 0 <= idx < len(plan) else {}
    upcoming = plan[idx + 1] if 0 <= (idx + 1) < len(plan) else {}
    # Prefer slot-scoped orders if the caller pre-filtered them; otherwise filter now.
    if slot_orders and finished:
        scoped = _filter_slot_orders(finished, slot_orders)
        slot_orders = scoped or slot_orders

    gmv = sum(
        float(o.get("price", 0.0) or 0.0) * int(o.get("quantity", 1) or 1)
        for o in slot_orders
    )

    ctx = {
        "shop_id": shop_id,
        "slot_vua_ket_thuc": finished,
        "log_don_slot": {
            "so_don": len(slot_orders),
            "gmv": gmv,
            "san_pham": [o.get("product_name") for o in slot_orders],
        },
        "slot_ke_tiep_theo_kich_ban": upcoming,
        "learning_state": _learning_state_brief(learning_state),
    }

    system = (
        "Bạn là trợ lý livestream bán kẹo/thực phẩm (AREA_303) với cách nói chuyên nghiệp  "
        "nhưng thiên hướng buisiness .Khi một phiên live vừa kết thúc, dựa vào xu hướng "
        "trong mô hình học máy (alpha/beta/MAPE), hãy đưa ra gợi ý NHANH, ngắn gọn để "
        "đọc on-air cho phiên livestream tiếp theo: sản phẩm/voucher/combo nên tung, kèm "
        "kịch bản chốt deal 1-2 câu. Tối đa ~900 ký tự, tiếng Việt có dấu, không viết "
        "markdown nặng (không dùng dấu #)."
    )
    user = (
        "Phiên live vừa kết thúc 1 slot. Theo dõi log va xu hướng trọng số rồi "
        "đưa ra nhận xét cho sản phẩm vừa rồi và gợi ý cho slot kế tiếp. Dữ liệu JSON:\n"
        + json.dumps(ctx, ensure_ascii=False)
    )

    try:
        return chat(
            [{"role": "user", "content": user}],
            system=system,
            temperature=0.6,
        )
    except AIClientError:
        return None


# ---------------------------------------------------------------------------
# Post-live review / decision
# ---------------------------------------------------------------------------

def review_post_live(*, shop_id: str, feedback_payload: Dict[str, Any],
                     new_state: Dict[str, Any],
                     prev_state: Optional[Dict[str, Any]]) -> Optional[str]:
    """Text report / decision after the learner loop updates weights.

    Returns None if AI not configured / call fails. ``new_state`` already contains
    the just-updated alpha/beta/MAPE/history; ``prev_state`` is the state before.
    """
    if not is_ai_configured():
        return None

    def _trend(state):
        hist = (state or {}).get("history") or []
        return [
            {
                "date": h.get("date"),
                "alpha": h.get("alpha"),
                "beta": h.get("beta"),
                "session_mape": h.get("session_mape"),
                "mean_bias": h.get("mean_bias"),
                "redeem_rate": h.get("redeem_rate"),
            }
            for h in hist
        ]

    actual = feedback_payload.get("actual") or []

    ctx = {
        "shop_id": shop_id,
        "tong_quan": {
            "so_sku": len(actual),
            "thuc_te_vs_du_doan": [
                {
                    "item_id": a.get("item_id"),
                    "estimated_sales": a.get("estimated_sales"),
                    "actual_sales": a.get("actual_sales"),
                    "discount_used_pct": a.get("discount_used_pct"),
                    "voucher_redeemed": a.get("voucher_redeemed"),
                    "combo_sold": a.get("combo_sold"),
                }
                for a in actual
            ],
        },
        "trong_so_truoc_sau": {
            "alpha_truoc": (prev_state or {}).get("params", {}).get("alpha"),
            "alpha_sau": new_state.get("params", {}).get("alpha"),
            "beta_truoc": (prev_state or {}).get("params", {}).get("beta"),
            "beta_sau": new_state.get("params", {}).get("beta"),
            "mape_truoc": (prev_state or {}).get("metrics", {}).get("rolling_mape"),
            "mape_sau": new_state.get("metrics", {}).get("rolling_mape"),
            "redeem_rate_sau": new_state.get("metrics", {}).get("rolling_redeem_rate"),
        },
        "xu_huong_history": _trend(new_state),
    }

    system = (
        "Ban la chuyen gia phan tich hieu qua livestream ban keo/thuc pham (AREA_303). "
        "Doc du lieu hieu qua phien live va xu huong trong so hoc may (alpha = do nhay "
        "giam gia, beta = rao can voucher, MAPE = sai so du bao). Dua ra 'Quyet dinh' "
        "tong quan ve phien va 'De xuat cho phien sau' cu the (dieu chinh giam gia, "
        "voucher, combo, lua chon hero SKU). Viet tieng Viet, dang van ban, ngan gon "
        "(~400-700 tu), khong viet markdown nang (khong dung dau #)."
    )
    user = (
        "Day la bao cao sau phien live. Phan tich sai so, xu huong trong so, ty le "
        "redeem, roi dua ra quyet dinh va de xuat cho phien sau. Du lieu JSON:\n"
        + json.dumps(ctx, ensure_ascii=False)
    )

    try:
        return chat(
            [{"role": "user", "content": user}],
            system=system,
            temperature=0.5,
        )
    except AIClientError:
        return None


# ---------------------------------------------------------------------------
# Pre-live timeslot suggestion (from past-session logs)
# ---------------------------------------------------------------------------

def suggest_timeslot(*, shop_id: str, past_context: Dict[str, Any],
                     industry_signal: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Text suggestion for the optimal livestream window for an upcoming session.

    Reads the shop's past-session logs (playbooks + reviews + learning trend),
    aggregated by time slot, and reasons about which window historically
    converted best. Returns None if AI not configured / call fails.
    """
    if not is_ai_configured():
        return None

    ctx = dict(past_context or {})
    if industry_signal:
        ctx["tin_hieu_nganh"] = {
            "peak_hour": industry_signal.get("peak_hour"),
            "kinh_do_windows": industry_signal.get("kinh_do_windows"),
        }

    system = (
        "Ban la chuyen gia toi uu khung gio livestream ban keo/thuc pham (AREA_303). "
        "Ban duoc cho doc toan bo log hieu qua thuc te cua cac phien live da chay cua "
        "shop (doanh so thuc, ti le redeem voucher, combo ban ra, MAPE moi khung gio). "
        "Dua vao do, hay de xuat MOT khung gio cu the (start–end) cho phien live moi kem "
        "ly do ngan 2-4 cau: chi ro khung gio tung ra don tot nhat va khung gio nen "
        "tranh. Neu tin hieu nganh (peak voucher) khac voi lich su cua shop, hay can "
        "nhac ca hai. Tieng Viet co dau, ~600 ky tu, khong viet markdown nang "
        "(khong dung dau #)."
    )
    user = (
        "Day la tong hop log cac phien live da chay cua shop. Phan tich khung gio nao "
        "ra don tot nhat dua tren doanh thuc/redeem/combo/MAPE, roi de xuat khung gio "
        "cho phien moi. Du lieu JSON:\n"
        + json.dumps(ctx, ensure_ascii=False)
    )

    try:
        return chat(
            [{"role": "user", "content": user}],
            system=system,
            temperature=0.4,
        )
    except AIClientError:
        return None
