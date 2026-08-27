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

"""Helper utilities and mathematical routines for models."""

import datetime
from typing import Any, List, Optional


def to_float(v: Any, default: float = 0.0) -> float:
    """Safe conversion to float."""
    if v is None or v == "" or v in ("None", "nan", "null"):
        return default
    try:
        val = float(v)
        return default if val != val else val  # check NaN
    except (ValueError, TypeError):
        return default


def to_int(v: Any, default: int = 0) -> int:
    """Safe conversion to int."""
    if v is None or v == "" or v in ("None", "nan", "null"):
        return default
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return default


def ts_to_dt(s: Any) -> Optional[datetime.datetime]:
    """Convert epoch timestamp to datetime with UTC timezone."""
    try:
        if s is None or s in ("", "None", "0", "0.0", "nan"):
            return None
        return datetime.datetime.fromtimestamp(float(s), tz=datetime.timezone.utc)
    except Exception:
        return None


def norm(values: List[float]) -> List[float]:
    """Min-max normalize a list of floats to [0, 1]. Returns 0.5 if all values equal."""
    if not values:
        return []
    mx = max(values)
    mn = min(values)
    if mx == mn:
        return [0.5 for _ in values]
    diff = mx - mn
    return [(v - mn) / diff for v in values]


def clamp01(x: float) -> float:
    """Clamps float value to [0.0, 1.0]."""
    return max(0.0, min(1.0, float(x)))


def format_vnd(amount: float) -> str:
    """Formats numeric VND currency string."""
    try:
        amt = float(amount or 0.0)
        if abs(amt) >= 1_000_000:
            return f"{amt / 1_000_000:.2f}".rstrip("0").rstrip(".") + "M ₫"
        if abs(amt) >= 1_000:
            return f"{round(amt / 1000):,}k ₫"
        return f"{int(round(amt)):,} ₫"
    except Exception:
        return "0 ₫"
