"""Loader AREA_303 — parse CSV sản phẩm Shopee thành (data_pool, snapshots).

Tổng quát hóa từ `bibica_playbook.load_products` + `_load_raw_products`:
- Không hard-code shop_id hay đường dẫn. Nhận đường dẫn file hoặc bytes/in-memory.
- Validate cột bắt buộc (schema 40 cột Shopee).
- Dedup theo item_id (giữ row có monthly_sold_value lớn nhất) cho `data_pool`.
- Giữ `snapshots` = toàn bộ rows để build_observations cross-time cho M1.
- Gán `line` (line_or_catid) generic:
    * 1 catid duy nhất  -> synthetic line từ keyword tên (Zoo/Quasure/Gooka/Sumika/Other)
    * nhiều catid      -> line = str(catid) thật
- Trả (data_pool, snapshots). Mỗi row dict có đủ field cho 5 module.

Stdlib thuần (csv, io, re, collections).
"""
import csv
import io
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple, Union

from ._helpers import to_float

# Cột bắt buộc trong products.csv (schema 40 cột Shopee VN).
REQUIRED_COLUMNS = [
    "shop_id", "item_id", "product_name", "price", "price_original",
    "discount_percent", "monthly_sold_value", "rating_count", "rating",
    "ctime", "voucher_discount", "voucher_min_spend", "voucher_start_time",
    "voucher_end_time", "catid", "date",
]


class LoaderError(Exception):
    """Lỗi khi load/validate CSV."""

    def __init__(self, message: str, missing_columns: List[str] = None):
        super().__init__(message)
        self.missing_columns = missing_columns or []


PROMOTIONAL_CATEGORIES = [
    r"sản\s*phẩm\s*mới",
    r"san\s*pham\s*moi",
    r"tất\s*cả\s*sản\s*phẩm",
    r"tat\s*ca\s*san\s*pham",
    r"top\s*bán\s*chạy",
    r"sản\s*phẩm\s*bán\s*chạy",
    r"bán\s*chạy",
    r"best\s*seller",
    r"siêu\s*sale",
    r"mua\s*1\s*tặng\s*1",
    r"ưu\s*đãi",
    r"deal",
    r"giảm\s*giá",
    r"thùng\s*bánh",
    r"bánh\s*kẹo\s*sỉ",
    r"sỉ",
    r"cuồng\s*nhiệt",
    r"độc\s*quyền\s*online",
    r"box\s*độc\s*quyền",
    r"combo\s*mix",
    r"combo\s*tết",
    r"kinh\s*đô\s*tết",
]

_PROMO_REGEX = re.compile(r"|".join(PROMOTIONAL_CATEGORIES), re.IGNORECASE)

_GIFT_REGEX = re.compile(
    r"(\bquà\s*tặng\s*không\s*bán\b|\bhàng\s*tặng\s*không\s*bán\b|\bhàng\s*tặng\b|\[\s*quà\s*tặng|\[\s*gift\s*\]|\bquà\s*tặng\s*\||\bquà\s*tặng\s*-)",
    re.IGNORECASE,
)


def is_promotional_category(cat_name: Optional[str]) -> bool:
    """Kiểm tra xem danh mục có phải là danh mục quảng bá / khuyến mãi chung hay không."""
    if not cat_name or str(cat_name).strip() in ("", "None", "nan", "Khác", "Other"):
        return True
    return bool(_PROMO_REGEX.search(str(cat_name)))


def is_gift_product(product_name: Optional[str]) -> bool:
    """Kiểm tra xem tên sản phẩm có phải là hàng quà tặng kèm không."""
    if not product_name:
        return False
    name = str(product_name).strip()
    if _GIFT_REGEX.search(name):
        return True
    lower = name.lower()
    if lower.startswith("quà tặng") or lower.startswith("[quà tặng") or lower.startswith("(quà tặng") or lower.startswith("[gift"):
        return True
    if "quà tặng không bán" in lower or "quà tặng kèm" in lower or "hàng tặng" in lower:
        return True
    return False


def _synthetic_line(name: str) -> str:
    """Gán synthetic line từ keyword trong tên sản phẩm (lowercase)."""
    nm = (name or "").lower()
    if is_gift_product(nm):
        return "Quà Tặng"
    if "quasure" in nm or "sugar free" in nm or "không đường" in nm:
        return "Quasure Sugar Free"
    if "gooka" in nm or "nougat" in nm:
        return "Gooka Nougat Filling"
    if any(w in nm for w in ["zoo", "cho bé", "trẻ em", "kem tuyết", "sâu kỳ thú"]):
        return "Kẹo Cho Bé"
    if any(w in nm for w in ["ăn sáng", "sandwich", "bông lan olive", "bánh tươi olive", "bánh mì", "castella"]):
        return "Bánh Ăn Sáng"
    if any(w in nm for w in ["dinh dưỡng", "ăn kiêng", "tiểu đường", "ngũ cốc"]):
        return "Bánh Dinh Dưỡng"
    if any(w in nm for w in ["sumika", "cheery", "welly", "migita", "tứ quý", "michoco", "kẹo dẻo", "kẹo mút", "kẹo cứng", "kẹo ngậm", "kẹo mềm", "kẹo thạch", "kẹo"]):
        return "Kẹo Ăn Vặt"
    if any(w in nm for w in ["hura", "goody", "jamy", "cookies", "bánh quy", "bánh cracker", "bánh bông lan", "bánh"]):
        return "Bánh Ăn Vặt"
    return "Khác"


def load_category_mapping(shop_id: Optional[str] = None, base_dir: Optional[str] = None) -> Dict[str, str]:
    """Đọc category_list.csv và product_categories.csv để tạo ánh xạ item_id -> display_name."""
    import os
    candidate_roots = []
    if base_dir:
        candidate_roots.append(base_dir)
    mod_dir = os.path.dirname(os.path.abspath(__file__))
    candidate_roots.extend([
        os.path.join(mod_dir, "..", "..", "Data", "country_code=vn"),
        os.path.join(mod_dir, "..", "Data", "country_code=vn"),
        os.path.join(os.getcwd(), "mockups", "Data", "country_code=vn"),
        os.path.join(os.getcwd(), "Data", "country_code=vn"),
        os.path.join(os.getcwd(), "data"),
    ])

    root_found = None
    for r in candidate_roots:
        if os.path.isdir(os.path.join(r, "dataset=category_list")) or os.path.isdir(os.path.join(r, "dataset=product_categories")):
            root_found = r
            break

    if not root_found:
        return {}

    # Đọc category_list.csv
    cat_names: Dict[str, str] = {}
    cat_list_dir = os.path.join(root_found, "dataset=category_list")
    shop_subdirs = [f"shop_id={shop_id}"] if shop_id else (os.listdir(cat_list_dir) if os.path.exists(cat_list_dir) else [])
    for sdir in shop_subdirs:
        p = os.path.join(cat_list_dir, sdir, "category_list.csv")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        cid = row.get("shop_category_id")
                        name = row.get("display_name")
                        if cid and name:
                            cat_names[str(cid).strip()] = name.strip()
            except Exception:
                pass

    # Đọc product_categories.csv -> thu thập tất cả categories cho từng item_id
    item_all_cats: Dict[str, List[str]] = {}
    prod_cat_dir = os.path.join(root_found, "dataset=product_categories")
    p_shop_subdirs = [f"shop_id={shop_id}"] if shop_id else (os.listdir(prod_cat_dir) if os.path.exists(prod_cat_dir) else [])
    for sdir in p_shop_subdirs:
        p = os.path.join(prod_cat_dir, sdir, "product_categories.csv")
        if os.path.isfile(p):
            try:
                with open(p, encoding="utf-8-sig") as f:
                    for row in csv.DictReader(f):
                        iid = row.get("item_id")
                        cid = row.get("category_id") or row.get("category_slug")
                        if iid and cid:
                            iid_str = str(iid).strip()
                            cid_str = str(cid).strip()
                            cname = cat_names.get(cid_str, cid_str)
                            if cname:
                                item_all_cats.setdefault(iid_str, []).append(cname)
            except Exception:
                pass

    # Ưu tiên chọn danh mục cụ thể (không phải khuyến mãi / quảng bá chung)
    item_to_cat: Dict[str, str] = {}
    for iid_str, cats in item_all_cats.items():
        specific_cats = [c for c in cats if not is_promotional_category(c)]
        if specific_cats:
            item_to_cat[iid_str] = specific_cats[0]
        elif cats:
            item_to_cat[iid_str] = cats[0]

    return item_to_cat


def _parse_source(source: Union[str, bytes, io.StringIO, io.BytesIO]) -> io.StringIO:
    """Chuyển nhiều loại input về StringIO chứa text CSV."""
    if isinstance(source, str):
        if "\n" in source or "," in source:
            return io.StringIO(source)
        with open(source, encoding="utf-8-sig") as f:
            return io.StringIO(f.read())
    if isinstance(source, bytes):
        return io.StringIO(source.decode("utf-8-sig"))
    if isinstance(source, io.BytesIO):
        return io.StringIO(source.read().decode("utf-8-sig"))
    return source


def assign_line_or_catid(rows: List[Dict[str, Any]], category_mapping: Optional[Dict[str, str]] = None) -> str:
    """Mutate rows: thêm field 'line'."""
    if not rows:
        return "none"

    if category_mapping is None:
        shop_id = rows[0].get("shop_id")
        category_mapping = load_category_mapping(str(shop_id) if shop_id else None)

    for r in rows:
        pname = r.get("product_name", "")
        if is_gift_product(pname):
            r["line"] = "Quà Tặng"
            continue
        iid = str(r.get("item_id", "")).strip()
        if category_mapping and iid in category_mapping:
            cat = category_mapping[iid]
            if cat and not is_promotional_category(cat) and cat not in ("Khác", "Other"):
                r["line"] = cat
                continue
        # Fallback
        line = _synthetic_line(pname)
        r["line"] = line if line != "Khác" else ("Bánh Ăn Vặt" if "bánh" in str(pname).lower() else ("Kẹo Ăn Vặt" if "kẹo" in str(pname).lower() else "Bánh Ăn Vặt"))

    return "dataset_categories"


def load_csv(source: Union[str, bytes, io.StringIO, io.BytesIO], category_mapping: Optional[Dict[str, str]] = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Load products.csv -> (data_pool, snapshots).

    source: đường dẫn str | bytes CSV | StringIO/BytesIO.
    data_pool: 1 SKU/item_id (dedup, giữ row monthly_sold_value lớn nhất).
    snapshots: toàn bộ rows (per ngày) để build_observations cho M1.
    Raise LoaderError nếu thiếu cột bắt buộc.
    """
    sio = _parse_source(source)
    reader = csv.DictReader(sio)
    if reader.fieldnames is None:
        raise LoaderError("CSV rỗng hoặc không đọc được header.")
    missing = [c for c in REQUIRED_COLUMNS if c not in reader.fieldnames]
    if missing:
        raise LoaderError(f"CSV thiếu cột bắt buộc: {missing}", missing_columns=missing)

    snapshots: List[Dict[str, Any]] = []
    for r in reader:
        iid = r.get("item_id")
        if not iid or iid in ("", "None"):
            continue
        snapshots.append(r)

    if not snapshots:
        raise LoaderError("CSV không có row nào hợp lệ (thiếu item_id).")

    # Gán line (danh mục từ product_categories & category_list / synthetic / real_catid) — mutate snapshots.
    assign_line_or_catid(snapshots, category_mapping=category_mapping)

    # Dedup theo item_id: giữ row có monthly_sold_value lớn nhất.
    best: Dict[str, Dict[str, Any]] = {}
    for r in snapshots:
        iid = r["item_id"]
        ms = to_float(r.get("monthly_sold_value"))
        if iid not in best or ms > to_float(best[iid].get("monthly_sold_value")):
            best[iid] = r
    data_pool = list(best.values())
    return data_pool, snapshots

