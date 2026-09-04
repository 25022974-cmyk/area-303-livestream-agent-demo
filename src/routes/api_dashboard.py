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

"""REST API endpoints for generated livestream data dashboard and actions."""

from flask import Blueprint, jsonify, request

from ..services.dashboard_service import dashboard_service
from ..services.shop_service import shop_service

api_dashboard_bp = Blueprint("api_dashboard", __name__, url_prefix="/api/dashboard")


@api_dashboard_bp.route("/<shop_id>/summary", methods=["GET"])
def get_summary(shop_id: str):
    """Returns overview summary of all generated files for a shop."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        summary = dashboard_service.get_shop_data_summary(sid)
        return jsonify({"status": "ok", "summary": summary})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# --- Playbooks ---

@api_dashboard_bp.route("/<shop_id>/playbooks", methods=["GET"])
def list_playbooks(shop_id: str):
    """Lists active draft and archived playbooks."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        archived = dashboard_service.list_archived_playbooks(sid)
        return jsonify({"status": "ok", "archived": archived})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/playbooks/<filename>", methods=["GET"])
def get_playbook(shop_id: str, filename: str):
    """Retrieves full JSON of an archived playbook."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        data = dashboard_service.get_playbook_detail(sid, filename)
        return jsonify({"status": "ok", "filename": filename, "data": data})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/playbooks/<filename>/restore", methods=["POST"])
def restore_playbook(shop_id: str, filename: str):
    """Restores an archived playbook as the current draft."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        restored = dashboard_service.restore_playbook(sid, filename)
        return jsonify({"status": "ok", "message": f"Playbook '{filename}' restored as active draft.", "draft": restored})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/playbooks/<filename>", methods=["DELETE"])
def delete_playbook(shop_id: str, filename: str):
    """Deletes an archived playbook snapshot."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        deleted = dashboard_service.delete_archived_playbook(sid, filename)
        if deleted:
            return jsonify({"status": "ok", "message": f"Archived playbook '{filename}' deleted."})
        return jsonify({"status": "error", "message": f"Playbook '{filename}' not found."}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/draft", methods=["DELETE"])
def delete_draft(shop_id: str):
    """Deletes the active draft playbook."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        deleted = dashboard_service.delete_draft_playbook(sid)
        if deleted:
            return jsonify({"status": "ok", "message": "Active draft playbook deleted."})
        return jsonify({"status": "error", "message": "No active draft found."}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# --- Orders ---

@api_dashboard_bp.route("/<shop_id>/orders", methods=["GET"])
def get_orders(shop_id: str):
    """Retrieves all orders in orders.json."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        orders = dashboard_service.get_orders(sid)
        return jsonify({"status": "ok", "orders": orders, "count": len(orders)})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/orders/<order_id>", methods=["PUT"])
def update_order(shop_id: str, order_id: str):
    """Updates an order in orders.json."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        body = request.get_json() or {}
        orders = dashboard_service.update_order(sid, order_id, body)
        return jsonify({"status": "ok", "message": f"Order '{order_id}' updated.", "orders": orders})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/orders/<order_id>", methods=["DELETE"])
def delete_order(shop_id: str, order_id: str):
    """Deletes an order from orders.json."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        orders = dashboard_service.delete_order(sid, order_id)
        return jsonify({"status": "ok", "message": f"Order '{order_id}' deleted.", "orders": orders})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/orders", methods=["DELETE"])
def clear_orders(shop_id: str):
    """Clears all orders."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        dashboard_service.clear_orders(sid)
        return jsonify({"status": "ok", "message": "All orders cleared."})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# --- Learner State ---

@api_dashboard_bp.route("/<shop_id>/learning-state", methods=["GET"])
def get_learning_state(shop_id: str):
    """Returns learning state."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        state = dashboard_service.get_learner_state(sid)
        return jsonify({"status": "ok", "learning_state": state})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/learning-state", methods=["PUT"])
def update_learning_params(shop_id: str):
    """Updates alpha and beta hyperparameters."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        body = request.get_json() or {}
        if "alpha" not in body or "beta" not in body:
            return jsonify({"status": "error", "message": "Missing 'alpha' or 'beta' fields."}), 400

        alpha = float(body["alpha"])
        beta = float(body["beta"])
        new_state = dashboard_service.update_learner_params(sid, alpha, beta)
        return jsonify({"status": "ok", "message": "Learner parameters updated.", "learning_state": new_state})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/learning-state/reset", methods=["POST"])
def reset_learning_state(shop_id: str):
    """Resets learning state to default initial state."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        fresh_state = dashboard_service.reset_learner_state(sid)
        return jsonify({"status": "ok", "message": "Learner state reset to defaults.", "learning_state": fresh_state})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# --- Reviews ---

@api_dashboard_bp.route("/<shop_id>/reviews", methods=["GET"])
def list_reviews(shop_id: str):
    """Lists archived reviews."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        archived = dashboard_service.list_archived_reviews(sid)
        return jsonify({"status": "ok", "reviews": archived})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/reviews/<filename>", methods=["GET"])
def get_review(shop_id: str, filename: str):
    """Retrieves full JSON of an archived review."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        data = dashboard_service.get_review_detail(sid, filename)
        return jsonify({"status": "ok", "filename": filename, "data": data})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


@api_dashboard_bp.route("/<shop_id>/reviews/<filename>", methods=["DELETE"])
def delete_review(shop_id: str, filename: str):
    """Deletes an archived review snapshot."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        deleted = dashboard_service.delete_archived_review(sid, filename)
        if deleted:
            return jsonify({"status": "ok", "message": f"Archived review '{filename}' deleted."})
        return jsonify({"status": "error", "message": f"Review '{filename}' not found."}), 404
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400


# --- Purge ---

@api_dashboard_bp.route("/<shop_id>/purge", methods=["POST"])
def purge_data(shop_id: str):
    """Safely clears test session data for a shop."""
    try:
        sid = shop_service.validate_shop_id(shop_id)
        res = dashboard_service.purge_all_generated(sid)
        return jsonify(res)
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
