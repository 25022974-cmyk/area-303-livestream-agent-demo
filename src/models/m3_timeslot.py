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

"""Module 3 — Optimal Livestream Time Window Optimization."""

from collections import Counter
from typing import Any, Dict, List, Optional

from ._helpers import ts_to_dt

KINH_DO_KEYWORD = "kinh do"
DEFAULT_WINDOW_SPAN = 2


def _extract_hour(epoch: Any) -> Optional[int]:
    """Extracts UTC/local hour from timestamp."""
    dt = ts_to_dt(epoch)
    return dt.hour if dt is not None else None


def optimize_timeslot(snapshots: List[Dict[str, Any]], shop_id: str = "") -> Dict[str, Any]:
    """
    Determines recommended livestream start & end hour using competitor live vouchers
    and 24-hour voucher activation overlap.
    """
    kinh_do_windows = set()
    all_hours: List[int] = []

    for r in snapshots:
        sh = _extract_hour(r.get("voucher_start_time"))
        eh = _extract_hour(r.get("voucher_end_time"))

        if sh is not None:
            all_hours.append(sh)

        shop_name = str(r.get("shop_name") or "").lower()
        if KINH_DO_KEYWORD in shop_name and sh is not None:
            if eh is None or eh <= sh:
                eh = (sh + DEFAULT_WINDOW_SPAN) % 24
            kinh_do_windows.add((sh, eh))

    # 24-hour histogram
    hour_counts = Counter(all_hours)
    hour_distribution = [hour_counts.get(h, 0) for h in range(24)]

    if kinh_do_windows:
        # Sort by duration or occurrence
        best_win = sorted(kinh_do_windows)[0]
        start_hour = best_win[0]
        end_hour = best_win[1]
        reason = f"Trùng khớp khung giờ Live Deal của Kinh Đô ({start_hour}:00–{end_hour}:00) và mật độ voucher ngành cao nhất."
    elif all_hours:
        # Pick peak hour from histogram
        peak_hour = max(range(24), key=lambda h: hour_counts.get(h, 0))
        start_hour = peak_hour
        end_hour = (peak_hour + DEFAULT_WINDOW_SPAN) % 24
        reason = f"Đỉnh kích hoạt voucher ngành lúc {start_hour}:00 ({hour_counts[peak_hour]} voucher)."
    else:
        # Default prime-time e-commerce window (20:00 - 22:00)
        start_hour = 20
        end_hour = 22
        reason = "Khung giờ vàng livestream thương mại điện tử mặc định (20:00–22:00)."

    return {
        "start_hour": start_hour,
        "end_hour": end_hour,
        "recommended_slot": f"{start_hour:02d}:00 – {end_hour:02d}:00",
        "reason": reason,
        "confidence": "medium" if kinh_do_windows else "low",
        "evidence": {
            "kinh_do_windows": [list(w) for w in sorted(kinh_do_windows)],
            "hour_distribution": hour_distribution,
            "peak_hour": max(range(24), key=lambda h: hour_counts.get(h, 0)) if all_hours else 20,
        },
    }
