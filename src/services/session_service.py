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

"""Session service managing live drafts, active run-of-show playbooks, order tracking, and feedback."""

import datetime
import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..models.learner import update_learning_state
from .shop_service import shop_service


class SessionService:
    """Service managing session lifecycle states (Pre-live draft -> On-air -> Post-live review)."""

    def save_draft_playbook(self, shop_id: str, playbook_data: Dict[str, Any]) -> Path:
        """Saves active live draft playbook from Pre-live planner."""
        shop_d = shop_service.get_shop_dir(shop_id)
        path = shop_d / "draft_playbook.json"
        playbook_data["updated_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        path.write_text(json.dumps(playbook_data, ensure_ascii=False, indent=2), encoding="utf-8")

        # Also save archive snapshot
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
        archive_path = shop_d / "playbooks" / f"playbook_{ts}.json"
        archive_path.write_text(json.dumps(playbook_data, ensure_ascii=False, indent=2), encoding="utf-8")

        return path

    def get_draft_playbook(self, shop_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves currently active draft playbook for On-air assistant."""
        shop_d = shop_service.get_shop_dir(shop_id)
        path = shop_d / "draft_playbook.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return None

    def log_onair_order(self, shop_id: str, order_item: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Appends a new order to the live on-air order tracker log."""
        shop_d = shop_service.get_shop_dir(shop_id)
        path = shop_d / "orders.json"
        orders: List[Dict[str, Any]] = []
        if path.exists():
            try:
                orders = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                orders = []

        order_record = {
            "order_id": f"ORD_{datetime.datetime.now(datetime.timezone.utc).strftime('%H%M%S%f')[:10]}",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "item_id": order_item.get("item_id"),
            "product_name": order_item.get("product_name"),
            "price": float(order_item.get("price", 0.0)),
            "quantity": int(order_item.get("quantity", 1)),
            "combo_id": order_item.get("combo_id"),
            "voucher_applied": order_item.get("voucher_applied", False),
        }
        orders.append(order_record)
        path.write_text(json.dumps(orders, ensure_ascii=False, indent=2), encoding="utf-8")
        return orders

    def get_onair_orders(self, shop_id: str) -> List[Dict[str, Any]]:
        """Retrieves logged on-air orders."""
        shop_d = shop_service.get_shop_dir(shop_id)
        path = shop_d / "orders.json"
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def clear_onair_orders(self, shop_id: str) -> None:
        """Clears logged orders for a new session."""
        shop_d = shop_service.get_shop_dir(shop_id)
        path = shop_d / "orders.json"
        if path.exists():
            path.unlink()

    # ------------------------------------------------------------------
    # Past-session log aggregation (for AI timeslot suggestion)
    # ------------------------------------------------------------------

    @staticmethod
    def _safe_number(v: Any, default: float = 0.0) -> float:
        try:
            f = float(v)
            return default if f != f else f  # NaN check
        except (TypeError, ValueError):
            return default

    def _load_json_file(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def load_past_sessions(self, shop_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Reads archived playbooks and joins each with its matching post-live review.

        Playbooks and reviews are linked by live date (playbook.live_date ↔
        review.date), NOT by file timestamp — a draft is saved in pre-live while
        the review is submitted long after the stream ends, so their file
        timestamps never coincide. When multiple playbooks share a date, the
        newest (latest updated_at) wins. Returns newest-first.
        """
        shop_d = shop_service.get_shop_dir(shop_id)
        pb_dir = shop_d / "playbooks"
        rv_dir = shop_d / "reviews"

        # Load + index reviews by date
        reviews_by_date: Dict[str, Dict[str, Any]] = {}
        if rv_dir.exists():
            for p in sorted(rv_dir.glob("review_*.json")):
                rv = self._load_json_file(p) or {}
                d = str(rv.get("date") or "")
                if d:
                    # Newest review per date wins (later file = later mtime-ish)
                    reviews_by_date[d] = rv

        # Load playbooks, keep newest per live_date
        playbooks_by_date: Dict[str, Dict[str, Any]] = {}
        if pb_dir.exists():
            for p in sorted(pb_dir.glob("playbook_*.json"), reverse=True):
                pb = self._load_json_file(p) or {}
                d = str(pb.get("live_date") or "") or str((pb.get("summary") or {}).get("selected_date") or "")
                # Fallback for older playbooks that pre-date the live_date field:
                # derive a date from the file-name timestamp "playbook_YYYYMMDDHHMMSS.json".
                if not d:
                    stem = p.stem  # e.g. playbook_20260827183418
                    ts = stem.split("_", 1)[-1]
                    if len(ts) >= 8 and ts[:8].isdigit():
                        d = f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}"
                if not d:
                    continue
                if d in playbooks_by_date:
                    # Keep the newest by updated_at, then by file-name timestamp
                    old = playbooks_by_date[d]
                    if str(pb.get("updated_at") or "") <= str(old.get("updated_at") or ""):
                        continue
                playbooks_by_date[d] = pb

        sessions: List[Dict[str, Any]] = []
        for d, pb in playbooks_by_date.items():
            rv = reviews_by_date.get(d)
            sessions.append(self._compose_past_session(d, pb, rv))

        # Sort newest-first by date (tie-break by slot string)
        sessions.sort(key=lambda s: (s.get("date") or "", s.get("slot") or ""), reverse=True)
        if limit is not None:
            sessions = sessions[:max(0, int(limit))]
        return sessions

    def _compose_past_session(self, date: str, pb: Dict[str, Any],
                              rv: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Builds one compact past-session record from a playbook (+ optional review)."""
        start_t = str(pb.get("start_time") or "")
        end_t = str(pb.get("end_time") or "")
        slot = str(pb.get("slot") or ((f"{start_t} – {end_t}") if start_t and end_t else ""))
        items = pb.get("items") or []
        combos = pb.get("combos") or []
        summary = pb.get("summary") or {}

        compact_items = [
            {
                "item_id": it.get("item_id"),
                "name": it.get("name"),
                "price": it.get("price"),
            }
            for it in items if isinstance(it, dict)
        ][:30]
        compact_combos = [
            {
                "combo_id": c.get("combo_id"),
                "combo_name": c.get("combo_name"),
                "bundle_price": c.get("bundle_price"),
            }
            for c in combos if isinstance(c, dict)
        ][:10]

        record: Dict[str, Any] = {
            "date": date,
            "start_time": start_t,
            "end_time": end_t,
            "slot": slot,
            "duration_mins": pb.get("duration_mins"),
            "recommended_timeslot": summary.get("recommended_timeslot"),
            "n_sku": len(compact_items),
            "n_combo": len(compact_combos),
            "items": compact_items,
            "combos": compact_combos,
        }

        # Review (actual performance) is optional — only present after post-live submit
        actual = rv.get("actual") or [] if rv else []
        if actual:
            total_actual = sum(self._safe_number(a.get("actual_sales")) for a in actual if isinstance(a, dict))
            total_est = sum(self._safe_number(a.get("estimated_sales")) for a in actual if isinstance(a, dict))
            redeem_count = sum(1 for a in actual if isinstance(a, dict) and a.get("voucher_redeemed"))
            combo_sold_count = sum(1 for a in actual if isinstance(a, dict) and a.get("combo_sold"))
            # Lightweight MAPE proxy (mean abs % error), no learner needed
            mape_list = []
            for a in actual:
                if not isinstance(a, dict):
                    continue
                est = self._safe_number(a.get("estimated_sales"))
                act = self._safe_number(a.get("actual_sales"))
                if est > 0:
                    mape_list.append(abs(est - act) / est)
            mape_proxy = round(sum(mape_list) / len(mape_list), 3) if mape_list else None

            record.update({
                "has_review": True,
                "actual_total_sales": int(round(total_actual)),
                "estimated_total_sales": int(round(total_est)),
                "mape_proxy": mape_proxy,
                "redeem_count": redeem_count,
                "combo_sold_count": combo_sold_count,
                "per_sku": [
                    {
                        "item_id": a.get("item_id"),
                        "name": a.get("name") or a.get("product_name"),
                        "actual_sales": a.get("actual_sales"),
                        "estimated_sales": a.get("estimated_sales"),
                        "discount_used_pct": a.get("discount_used_pct"),
                        "voucher_redeemed": bool(a.get("voucher_redeemed")),
                        "combo_sold": bool(a.get("combo_sold")),
                    }
                    for a in actual if isinstance(a, dict)
                ][:30],
            })
        else:
            record["has_review"] = False
        return record

    def build_timeslot_ai_context(self, shop_id: str, max_sessions: int = 12) -> Dict[str, Any]:
        """Builds a compact, token-friendly context summarising past sessions
        for the AI timeslot suggestion. Aggregates per-slot performance so the
        model sees which windows historically convert best.
        """
        sid = shop_service.validate_shop_id(shop_id)
        sessions = self.load_past_sessions(sid, limit=max_sessions)

        # Aggregate by slot (start_time–end_time). Only sessions with a review count.
        per_slot: Dict[str, Dict[str, Any]] = {}
        for s in sessions:
            if not s.get("has_review"):
                continue
            key = s.get("slot") or ""
            if not key:
                continue
            agg = per_slot.setdefault(key, {
                "slot": key, "n_phien": 0,
                "tong_doanh_thuc": 0.0, "tong_est": 0.0,
                "tong_redeem": 0, "tong_combo": 0, "mape_sum": 0.0, "mape_n": 0,
            })
            agg["n_phien"] += 1
            agg["tong_doanh_thuc"] += float(s.get("actual_total_sales") or 0.0)
            agg["tong_est"] += float(s.get("estimated_total_sales") or 0.0)
            agg["tong_redeem"] += int(s.get("redeem_count") or 0)
            agg["tong_combo"] += int(s.get("combo_sold_count") or 0)
            if s.get("mape_proxy") is not None:
                agg["mape_sum"] += float(s["mape_proxy"])
                agg["mape_n"] += 1

        slot_summary = []
        for agg in per_slot.values():
            n = max(agg["n_phien"], 1)
            slot_summary.append({
                "slot": agg["slot"],
                "n_phien": agg["n_phien"],
                "trung_binh_doanh_thuc": round(agg["tong_doanh_thuc"] / n, 1),
                "trung_binh_redeem": round(agg["tong_redeem"] / n, 2),
                "trung_binh_combo": round(agg["tong_combo"] / n, 2),
                "mape": round(agg["mape_sum"] / agg["mape_n"], 3) if agg["mape_n"] else None,
            })
        # Sort by avg actual sales descending (best-performing first)
        slot_summary.sort(key=lambda r: r.get("trung_binh_doanh_thuc") or 0.0, reverse=True)

        # Learner trend (history) — short, newest-first
        learning_state = shop_service.load_learning_state(sid)
        hist = (learning_state.get("history") or [])[-(max_sessions or 0):] if max_sessions else (learning_state.get("history") or [])
        trend = [
            {
                "date": h.get("date"),
                "alpha": h.get("alpha"),
                "beta": h.get("beta"),
                "session_mape": h.get("session_mape"),
                "redeem_rate": h.get("redeem_rate"),
            }
            for h in hist if isinstance(h, dict)
        ][::-1]

        # Compact per-session detail (drop items/combos/per_sku to save tokens)
        chi_tiet = [
            {k: v for k, v in s.items() if k not in ("items", "combos", "per_sku")}
            for s in sessions
        ]

        return {
            "shop_id": sid,
            "n_sessions": len(sessions),
            "n_sessions_co_review": sum(1 for s in sessions if s.get("has_review")),
            "tong_hop_theo_khung_gio": slot_summary,
            "xu_huong_hoc": trend,
            "chi_tiet_phien": chi_tiet,
        }

    def submit_postlive_feedback(self, shop_id: str, feedback_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Processes actual live performance, updates learning state, and saves post-live review."""
        current_state = shop_service.load_learning_state(shop_id)
        new_state = update_learning_state(current_state, feedback_payload)
        shop_service.save_learning_state(shop_id, new_state)

        # Save post-live review record
        shop_d = shop_service.get_shop_dir(shop_id)
        review_dir = shop_d / "reviews"
        review_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d%H%M%S")
        review_path = review_dir / f"review_{ts}.json"
        review_path.write_text(json.dumps(feedback_payload, ensure_ascii=False, indent=2), encoding="utf-8")

        return new_state


session_service = SessionService()
