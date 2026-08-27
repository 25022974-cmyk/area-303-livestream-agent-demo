"""Module 3 — Chọn khung giờ live.

Contract theo DELIVERABLE_SPEC.md §B/Module 3.

Gợi ý giờ dựa trên:
  1. Cửa sổ voucher của shop "Kinh Đô" (shop có label LIVE thật — Kinh Do Official Store).
  2. Histogram voucher_start_time của nhiều shop (industry overlap).

`confidence` luôn "low" — suy luận gián tiếp (spec ghi rõ). Khi Bibica có log viewer
thật (Phase 2) mới thay proxy bằng ranking model.

Lưu ý: server upload 1 CSV/1 shop -> `snapshots` có thể chỉ 1 shop_id. Khi đó
industry_overlap_score = 0 và DÙ fallback histogram từ chính shop đó. Khi upload
nhiều shop (hoặc CLI gộp ngành) -> overlap thật.

Giờ UTC của epoch (~17:00 UTC = 00:00 VN). Giữ nguyên UTC hour cho deterministic;
dashboard/CLI có thể hiển thị tooltip chuyển sang VN giờ nếu muốn.

Stdlib thuần.
"""
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from ._helpers import to_float, ts_to_dt

KINH_DO_KEYWORD = "kinh do"   # match shop_name "Kinh Do Official Store"
WINDOW_SPAN_HOURS = 2         # nếu chỉ có start (không có end) -> cửa sổ 2 giờ


def _hour_from_epoch(epoch: Any) -> Optional[int]:
    dt = ts_to_dt(epoch)
    return dt.hour if dt is not None else None


def _kinh_do_windows(snapshots: List[Dict[str, Any]]) -> List[List[int]]:
    """Cửa sổ [start_hour, end_hour] của các shop có "kinh đô" trong tên + voucher.

    Trả list các [start, end] khác biệt (int 0-23).
    """
    windows = set()
    for r in snapshots:
        shop = (r.get("shop_name") or "").lower()
        if KINH_DO_KEYWORD not in shop:
            continue
        sh = _hour_from_epoch(r.get("voucher_start_time"))
        eh = _hour_from_epoch(r.get("voucher_end_time"))
        if sh is None:
            continue
        if eh is None or eh < sh:
            eh = (sh + WINDOW_SPAN_HOURS) % 24
        windows.add((sh, eh))
    return [list(w) for w in sorted(windows)]


def _all_voucher_hours(snapshots: List[Dict[str, Any]]) -> List[int]:
    hours = []
    for r in snapshots:
        h = _hour_from_epoch(r.get("voucher_start_time"))
        if h is not None:
            hours.append(h)
    return hours


def _shop_ids_with_voucher(snapshots: List[Dict[str, Any]]) -> List[str]:
    """Distinct shop_id có voucher_start_time hợp lệ."""
    ids = set()
    for r in snapshots:
        if _hour_from_epoch(r.get("voucher_start_time")) is not None:
            sid = r.get("shop_id")
            if sid is not None and str(sid).strip():
                ids.add(str(sid))
    return list(ids)


def _industry_overlap(snapshots: List[Dict[str, Any]],
                      start_hour: int, end_hour: int) -> float:
    """% shop_id có voucher overlap khung [start, end].

    Overlap: giao [shop_start, shop_end] với [start, end] != rỗng.
    """
    total_shops_with_voucher = set()
    overlapping = set()
    for r in snapshots:
        sh = _hour_from_epoch(r.get("voucher_start_time"))
        eh = _hour_from_epoch(r.get("voucher_end_time"))
        if sh is None:
            continue
        if eh is None or eh < sh:
            eh = (sh + WINDOW_SPAN_HOURS) % 24
        sid = r.get("shop_id")
        if sid is None or not str(sid).strip():
            continue
        sid = str(sid)
        total_shops_with_voucher.add(sid)
        # overlap [sh, eh] vs [start_hour, end_hour] — xử lý wrap đơn giản:
        # nếu cùng có start chung hoặc playlist. Nước đơn giản: sh trong [start,end]
        # hoặc start trong [sh, eh] (vòng tròn bỏ qua để ổn).
        if _hours_overlap(sh, eh, start_hour, end_hour):
            overlapping.add(sid)
    if not total_shops_with_voucher:
        return 0.0
    return round(len(overlapping) / len(total_shops_with_voucher), 3)


def _hours_overlap(a_s: int, a_e: int, b_s: int, b_e: int) -> bool:
    """Overlap đơn giản (không xử lý wrap-around phức tạp — voucher ban đêm cả
    ngày thì gần như luôn overlap). Trả True nếu [a_s,a_e] ∩ [b_s,b_e] != rỗng."""
    lo = max(a_s, b_s)
    # end lấy min; nếu a_e<b_a (wrap) thì end = max để dễ overlap
    hi = min(a_e, b_e) if a_e >= a_s and b_e >= b_s else max(a_e, b_e)
    return lo <= hi


def timeslot(snapshots: List[Dict[str, Any]],
             shop_id: Optional[str] = None) -> Dict[str, Any]:
    """Trả contract Module 3.

    shop_id chỉ dùng cho reason text (giải thích cho shop nào), không lọc data.
    """
    kd_windows = _kinh_do_windows(snapshots)
    hours = _all_voucher_hours(snapshots)

    if kd_windows:
        start_hour, end_hour = kd_windows[0]
        confidence_sub = "Kinh Do windows"
    elif hours:
        # Fallback histogram voucher_start của tất cả snapshots.
        start_hour = Counter(hours).most_common(1)[0][0]
        end_hour = (start_hour + WINDOW_SPAN_HOURS) % 24
        confidence_sub = "fallback histogram voucher_start (khong co Kinh Do trong data)"
        kd_windows = []
    else:
        return {
            "start_hour": None, "end_hour": None,
            "reason": "Khong co voucher_start_time hop le trong data.",
            "confidence": "low",
            "evidence": {"kinh_do_windows": [], "industry_overlap_score": 0.0},
        }

    overlap = _industry_overlap(snapshots, start_hour, end_hour)
    n_shops = len(_shop_ids_with_voucher(snapshots))
    reason = (
        f"{confidence_sub}: {start_hour}-{end_hour}h (UTC), "
        f"{overlap*100:.0f}% overlap giua {n_shops} shop co voucher. "
        "Confidence low - su luan gian tiep."
    )

    return {
        "start_hour": start_hour,
        "end_hour": end_hour,
        "reason": reason,
        "confidence": "low",
        "evidence": {
            "kinh_do_windows": kd_windows,
            "industry_overlap_score": overlap,
        },
    }


# =====================================================================
# SELF-TEST
# =====================================================================
if __name__ == "__main__":
    import datetime as _dt
    # mock 10 shop: Kinh Do voucher 20-22h + vài shop overlap + vài không.
    base = int(_dt.datetime(2026, 8, 1, 20, 0, tzinfo=_dt.timezone.utc).timestamp())  # 20h UTC
    base22 = int(_dt.datetime(2026, 8, 1, 22, 0, tzinfo=_dt.timezone.utc).timestamp())
    snaps = []
    for sid, name, overlap in [
        ("140360136", "Kinh Do Official Store", True),
        ("213989179", "Bibica Official Store", True),   # 20-22 overlap
        ("111", "Nestle", False),                        # 10-12h không overlap
    ]:
        if overlap:
            s, e = base, base22
        else:
            s = int(_dt.datetime(2026, 8, 1, 10, 0, tzinfo=_dt.timezone.utc).timestamp())
            e = int(_dt.datetime(2026, 8, 1, 12, 0, tzinfo=_dt.timezone.utc).timestamp())
        snaps.append({"shop_id": sid, "shop_name": name,
                      "voucher_start_time": str(s), "voucher_end_time": str(e)})
    out = timeslot(snaps, shop_id="213989179")
    print("[M3 test]")
    print(" ", out)
    assert out["start_hour"] == 20 and out["end_hour"] == 22, "Kinh Do window phải thắng"
    assert out["confidence"] == "low"
    assert out["evidence"]["industry_overlap_score"] == round(2 / 3, 3), "2/3 shop overlap"
    print("✓ m3_timeslot OK (Kinh Do 20-22h, overlap 2/3)")

    # Fallback: không có Kinh Do
    snaps2 = [{"shop_id": "1", "shop_name": "X", "voucher_start_time": str(base)}] * 5
    out2 = timeslot(snaps2)
    print(" ", out2)
    assert out2["start_hour"] == 20 and out2["evidence"]["kinh_do_windows"] == [], "fallback chạy"
    print("✓ fallback OK")
