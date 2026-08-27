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

"""Global configuration, paths, and default settings for AREA_303 Livestream Strategist."""

import os
from pathlib import Path

# Paths
SRC_DIR = Path(__file__).resolve().parent
ROOT_DIR = SRC_DIR.parent
DATA_DIR = ROOT_DIR / "mockups" / "Data" / "country_code=vn"
STORAGE_DIR = ROOT_DIR / "data" / "shops"
STATIC_DIR = SRC_DIR / "static"
TEMPLATES_DIR = SRC_DIR / "templates"

# Create storage directory if not present
STORAGE_DIR.mkdir(parents=True, exist_ok=True)


def _load_dotenv() -> None:
    """Loads simple KEY=VALUE pairs from a .env file into os.environ (stdlib only).

    Existing environment variables are NOT overwritten, so shell-set vars win.
    Runs once at import time so that AI_* values below read correctly. This is a
    minimal stdlib loader (no python-dotenv dependency).
    """
    env_path = ROOT_DIR / ".env"
    if not env_path.exists():
        return
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            if not key:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value
    except Exception:
        pass


_load_dotenv()

# Upload limits
MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB

# Model Hyperparameter Defaults
DEFAULT_SHOP_ID = "213989179"  # Bibica Official Store
DEFAULT_BUDGET_VOUCHER_MONTH = 500_000_000.0  # 500M VND
DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 0.2
DEFAULT_USE_DP_KNAPSACK = True

# Preloaded Benchmark Shop Catalog
PRELOADED_SHOPS = {
    "213989179": {
        "shop_id": "213989179",
        "shop_name": "Bibica Official Store",
        "username": "bibica_corporation",
        "is_default": True,
        "category": "Confectionery / Bánh kẹo",
        "badge": "Chính hãng",
        "brand_color": "#1e293b",
    },
    "140360136": {
        "shop_id": "140360136",
        "shop_name": "Kinh Do Official Store",
        "username": "kinhdo_official_store",
        "is_default": False,
        "category": "Confectionery / Bánh kẹo",
        "badge": "Mall",
        "brand_color": "#b91c1c",
    },
    "108166524": {
        "shop_id": "108166524",
        "shop_name": "Nestlé Chính hãng",
        "username": "nestlevnn",
        "is_default": False,
        "category": "Beverage & Food / Đồ uống",
        "badge": "Mall",
        "brand_color": "#0369a1",
    },
    "1145316676": {
        "shop_id": "1145316676",
        "shop_name": "Nestlé Health Science",
        "username": "nestlehealthscience",
        "is_default": False,
        "category": "Health & Nutrition / Dinh dưỡng",
        "badge": "Mall",
        "brand_color": "#047857",
    },
    "289646907": {
        "shop_id": "289646907",
        "shop_name": "Orion VN Official Store",
        "username": "orion_official_store",
        "is_default": False,
        "category": "Confectionery / Bánh kẹo",
        "badge": "Mall",
        "brand_color": "#c2410c",
    },
    "430972539": {
        "shop_id": "430972539",
        "shop_name": "Perfetti Van Melle Vietnam",
        "username": "perfetti_officialstore",
        "is_default": False,
        "category": "Confectionery / Kẹo Chupa Chups & Mentos",
        "badge": "Mall",
        "brand_color": "#7c3aed",
    },
    "1546895026": {
        "shop_id": "1546895026",
        "shop_name": "Mars Snacking VN",
        "username": "mars.wrigley.vn",
        "is_default": False,
        "category": "Chocolate & Gum / Kẹo & Socola",
        "badge": "Mall",
        "brand_color": "#9333ea",
    },
    "173513432": {
        "shop_id": "173513432",
        "shop_name": "Richy - Chi Nhánh Miền Bắc",
        "username": "richystore.mb",
        "is_default": False,
        "category": "Confectionery / Bánh gạo & Bánh mềm",
        "badge": "Chính hãng",
        "brand_color": "#d97706",
    },
    "438905996": {
        "shop_id": "438905996",
        "shop_name": "Richy - Chi nhánh Miền Nam",
        "username": "richystore.mn",
        "is_default": False,
        "category": "Confectionery / Bánh gạo & Bánh mềm",
        "badge": "Chính hãng",
        "brand_color": "#ea580c",
    },
    "464391416": {
        "shop_id": "464391416",
        "shop_name": "Bánh Kẹo Hải Hà - Chính hãng",
        "username": "haihaco_hcm",
        "is_default": False,
        "category": "Confectionery / Bánh kẹo truyền thống",
        "badge": "Chính hãng",
        "brand_color": "#e11d48",
    },
}

# ============================================================
# AI / LLM — GLM-5.2 via Anthropic-Messages proxy
# ============================================================
# Configuration read from environment variables
# (see src/config.py _load_dotenv).
#
# Proxy contract (Anthropic Messages API-compatible):
#   POST <AI_PROXY_BASE_URL><AI_API_PATH>
#   Headers: Authorization: Bearer <AI_API_KEY>,
#            anthropic-version: 2023-06-01, Content-Type: application/json
#   Body:    {"model": <AI_MODEL>, "max_tokens": <AI_MAX_TOKENS>,
#            "messages": [{"role": "user"|"assistant", "content": "..." }],
#            "system": "..." (optional)}
#   Response: data["content"][0]["text"]
AI_PROXY_BASE_URL = os.environ.get("AI_PROXY_BASE_URL", "").strip().rstrip("/")
AI_API_URL = os.environ.get("AI_API_URL", "").strip()             # Full URL override (optional)
AI_API_KEY = os.environ.get("AI_API_KEY", "").strip()
AI_MODEL = os.environ.get("AI_MODEL", "glm-5.2").strip() or "glm-5.2"
AI_API_PATH = os.environ.get("AI_API_PATH", "/v1/messages")        # Anthropic Messages path
AI_ANTHROPIC_VERSION = os.environ.get("AI_ANTHROPIC_VERSION", "2023-06-01")
try:
    AI_REQUEST_TIMEOUT = int(os.environ.get("AI_TIMEOUT", "30"))
except (TypeError, ValueError):
    AI_REQUEST_TIMEOUT = 30
try:
    AI_MAX_TOKENS = int(os.environ.get("AI_MAX_TOKENS", "1024"))
except (TypeError, ValueError):
    AI_MAX_TOKENS = 1024
