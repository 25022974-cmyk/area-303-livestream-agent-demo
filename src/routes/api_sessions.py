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

"""REST API endpoints for draft playbooks, live order tracking, and post-live feedback."""

from flask import Blueprint, jsonify, request

from ..services.session_service import session_service
from ..services.shop_service import shop_service

api_sessions_bp = Blueprint("api_sessions", __name__, url_prefix="/api/sessions")


@api_sessions_bp.route("/save-draft", methods=["POST"])
def save_draft():
    """Saves configured draft playbook for On-air execution."""
    body = request.get_json() or {}
    shop_id = str(body.get("shop_id", "")).strip()

    if not shop_id:
        return jsonify({"status": "error", "message": "Missing required field: 'shop_id'"}), 400

    try:
        sid = shop_service.validate_shop_id(shop_id)
        saved_path = session_service.save_draft_playbook(sid, body)
        return jsonify({"status": "ok", "message": "Draft playbook saved successfully.", "path": str(saved_path)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_sessions_bp.route("/draft/<shop_id>", methods=["GET"])
def get_draft(shop_id: str):
    """Retrieves current draft playbook."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        draft = session_service.get_draft_playbook(sid)
        if not draft:
            return jsonify({"status": "empty", "draft": None, "message": "No active draft found."})
        return jsonify({"status": "ok", "draft": draft})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_sessions_bp.route("/log-order", methods=["POST"])
def log_order():
    """Logs an order placed during On-air livestream."""
    body = request.get_json() or {}
    shop_id = str(body.get("shop_id", "")).strip()
    order_item = body.get("order", {})

    if not shop_id:
        return jsonify({"status": "error", "message": "Missing shop_id"}), 400

    try:
        sid = shop_service.validate_shop_id(shop_id)
        orders = session_service.log_onair_order(sid, order_item)
        return jsonify({"status": "ok", "orders": orders, "count": len(orders)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@api_sessions_bp.route("/orders/<shop_id>", methods=["GET"])
def get_orders(shop_id: str):
    """Retrieves all logged orders for current on-air session."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        orders = session_service.get_onair_orders(sid)
        return jsonify({"status": "ok", "orders": orders, "count": len(orders)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_sessions_bp.route("/clear-orders", methods=["POST"])
def clear_orders():
    """Clears logged orders."""
    body = request.get_json() or {}
    shop_id = str(body.get("shop_id", "")).strip()
    try:
        sid = shop_service.validate_shop_id(shop_id)
        session_service.clear_onair_orders(sid)
        return jsonify({"status": "ok", "message": "Orders cleared."})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_sessions_bp.route("/feedback", methods=["POST"])
def post_feedback():
    """Submits actual sales results and updates online learner parameters."""
    body = request.get_json() or {}
    shop_id = str(body.get("shop_id", "")).strip()

    if not shop_id:
        return jsonify({"status": "error", "message": "Missing shop_id"}), 400

    try:
        sid = shop_service.validate_shop_id(shop_id)
        new_state = session_service.submit_postlive_feedback(sid, body)
        return jsonify({"status": "ok", "learning_state": new_state})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
