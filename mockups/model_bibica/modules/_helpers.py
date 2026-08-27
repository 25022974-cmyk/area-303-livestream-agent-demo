"""Helpers dùng chung cho các module AREA_303 (stdlib thuần).

Port từ `bibica_playbook.py` (to_float, ts_to_dt, norm, fmt_money) để các module
mới (loader, m2..m5, pipeline) tái dùng mà không phụ thuộc file legacy hard-code Bibica.
"""
import datetime


def to_float(v, default=0.0):
    """Ép kiểu an toàn về float. None/""/"None" -> default. "0"/"0.0" -> 0.0."""
    if v is None or v == "" or v == "None":
        return default
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def ts_to_dt(s):
    """Epoch giây (str/int/float) -> datetime UTC, hoặc None nếu không hợp lệ."""
    try:
        if not s or s in ("", "None", "0", "0.0"):
            return None
        return datetime.datetime.fromtimestamp(float(s), tz=datetime.timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def norm(values):
    """Min-max normalize list -> [0,1]. List rỗng -> []. max==min -> 0.5 cho mọi phần tử."""
    if not values:
        return []
    mx = max(values)
    mn = min(values)
    if mx == mn:
        return [0.5 for _ in values]
    return [(v - mn) / (mx - mn) for v in values]


def fmt_money(v):
    """Định dạng số tiền VND: 1234567 -> '1,234,567'."""
    try:
        return f"{int(round(v)):,}"
    except (TypeError, ValueError):
        return str(v)
