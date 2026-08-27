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

"""REST API endpoints for shop operations, data upload, and configuration."""

from flask import Blueprint, jsonify, request

from ..config import MAX_UPLOAD_BYTES
from ..services.shop_service import shop_service

api_shops_bp = Blueprint("api_shops", __name__, url_prefix="/api/shops")


@api_shops_bp.route("", methods=["GET"])
def list_shops():
    """Lists all available shops."""
    shops = shop_service.list_available_shops()
    return jsonify({"status": "ok", "shops": shops})


@api_shops_bp.route("/<shop_id>", methods=["GET"])
def get_shop(shop_id: str):
    """Retrieves metadata, configuration, learning state, and products for a shop."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        meta = shop_service.get_shop_meta(sid)
        config = shop_service.load_shop_config(sid)
        learning_state = shop_service.load_learning_state(sid)
        data_pool, _, _ = shop_service.load_shop_data(sid)

        return jsonify({
            "status": "ok",
            "shop": meta,
            "config": config,
            "learning_state": learning_state,
            "product_count": len(data_pool),
            "products": data_pool,
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_shops_bp.route("/upload", methods=["POST"])
def upload_csv():
    """Uploads custom Shopee products CSV file."""
    if "file" not in request.files:
        return jsonify({"status": "error", "message": "No file uploaded."}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"status": "error", "message": "Empty filename."}), 400

    raw_bytes = file.read()
    if len(raw_bytes) > MAX_UPLOAD_BYTES:
        return jsonify({"status": "error", "message": f"File exceeds maximum limit of {MAX_UPLOAD_BYTES} bytes."}), 413

    shop_id = request.form.get("shop_id", "").strip()
    shop_name = request.form.get("shop_name", "").strip() or None

    if not shop_id:
        return jsonify({"status": "error", "message": "Missing shop_id form parameter."}), 400

    try:
        sid = shop_service.validate_shop_id(shop_id)
        saved_path = shop_service.save_uploaded_csv(sid, raw_bytes, shop_name=shop_name)
        data_pool, snapshots, observations = shop_service.load_shop_data(sid)

        return jsonify({
            "status": "ok",
            "message": f"Successfully uploaded {len(snapshots)} rows ({len(data_pool)} unique SKUs).",
            "shop_id": sid,
            "saved_path": str(saved_path),
            "skus_count": len(data_pool),
            "observations_count": len(observations),
        })
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_shops_bp.route("/<shop_id>/config", methods=["POST"])
def save_config(shop_id: str):
    """Updates shop configuration parameters."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        body = request.get_json() or {}
        cfg = shop_service.load_shop_config(sid)

        if "budget_voucher_month" in body:
            cfg["budget_voucher_month"] = float(body["budget_voucher_month"])
        if "alpha" in body:
            cfg["alpha"] = float(body["alpha"])
        if "beta" in body:
            cfg["beta"] = float(body["beta"])
        if "use_dp_knapsack" in body:
            cfg["use_dp_knapsack"] = bool(body["use_dp_knapsack"])
        if "shop_name" in body and body["shop_name"]:
            cfg["shop_name"] = str(body["shop_name"])

        shop_service.save_shop_config(sid, cfg)
        return jsonify({"status": "ok", "config": cfg})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_shops_bp.route("/<shop_id>/learning-state", methods=["GET"])
def get_learning_state(shop_id: str):
    """Returns online learning state for a shop."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        state = shop_service.load_learning_state(sid)
        return jsonify({"status": "ok", "learning_state": state})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
