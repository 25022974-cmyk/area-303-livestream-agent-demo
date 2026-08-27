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

"""REST API endpoints for executing the AI decision engine pipeline."""

from flask import Blueprint, jsonify, request

from ..services.pipeline_service import pipeline_service
from ..services.shop_service import shop_service

api_pipeline_bp = Blueprint("api_pipeline", __name__, url_prefix="/api/pipeline")


@api_pipeline_bp.route("/run", methods=["POST"])
def run_pipeline_endpoint():
    """Runs the 5-module AI decision engine for a shop."""
    body = request.get_json() or {}
    shop_id = str(body.get("shop_id", "")).strip()

    if not shop_id:
        return jsonify({"status": "error", "message": "Missing required field: 'shop_id'"}), 400

    try:
        sid = shop_service.validate_shop_id(shop_id)
        budget = body.get("budget_voucher_month")
        alpha = body.get("alpha")
        beta = body.get("beta")
        use_dp = body.get("use_dp_knapsack")

        result = pipeline_service.run_for_shop(
            shop_id=sid,
            budget_voucher_month=float(budget) if budget is not None else None,
            alpha=float(alpha) if alpha is not None else None,
            beta=float(beta) if beta is not None else None,
            use_dp_knapsack=bool(use_dp) if use_dp is not None else None,
        )

        return jsonify({"status": "ok", "recommendation": result})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500
