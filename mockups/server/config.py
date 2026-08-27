"""Cấu hình server AREA_303 (paths, defaults)."""
import os
from pathlib import Path

# AREA_303 root = cha của `server/` (server/ nằm trong root).
ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / "model_bibica"
SERVER_DIR = Path(__file__).resolve().parent
SHOPS_DIR = SERVER_DIR / "shops"          # per-shop state (volume mount trong Docker)
STATIC_DIR = SERVER_DIR / "static"

MAX_UPLOAD_BYTES = 5 * 1024 * 1024        # 5 MB giới hạn CSV upload

# Defaults cho shop mới (trùng với bibica_playbook.py constants).
DEFAULT_BUDGET_VOUCHER_MONTH = 500_000_000.0
DEFAULT_ALPHA = 0.5
DEFAULT_BETA = 0.2
DEFAULT_USE_DP_KNAPSACK = True

SHOP_ID_PATTERN = r"^\d+$"                # chỉ số, anti path traversal

# Cho phép import `model_bibica.modules.*` từ server.
import sys
if str(MODEL_DIR) not in sys.path:
    sys.path.insert(0, str(MODEL_DIR))
