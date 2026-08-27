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

"""UI web page routes rendering Jinja2 templates."""

from flask import Blueprint, render_template, request

from ..config import DEFAULT_SHOP_ID
from ..services.shop_service import shop_service

ui_bp = Blueprint("ui", __name__)


def _get_context(current_stage: str) -> dict:
    """Helper to assemble shared Jinja2 template context."""
    shop_id = request.args.get("shop_id", DEFAULT_SHOP_ID)
    try:
        shop_id = shop_service.validate_shop_id(shop_id)
    except Exception:
        shop_id = DEFAULT_SHOP_ID

    shops = shop_service.list_available_shops()
    active_shop = next((s for s in shops if s["shop_id"] == shop_id), None)
    if not active_shop:
        active_shop = shop_service.get_shop_meta(shop_id)

    return {
        "shops": shops,
        "active_shop": active_shop,
        "shop_id": shop_id,
        "current_stage": current_stage,
    }


@ui_bp.route("/")
def index():
    """Landing page and shop selector."""
    ctx = _get_context("index")
    return render_template("index.html", **ctx)


@ui_bp.route("/prelive")
def prelive():
    """Pre-live Planner stage."""
    ctx = _get_context("prelive")
    return render_template("prelive.html", **ctx)


@ui_bp.route("/onair")
def onair():
    """On-air Assistant stage."""
    ctx = _get_context("onair")
    return render_template("onair.html", **ctx)


@ui_bp.route("/postlive")
def postlive():
    """Post-live Review stage."""
    ctx = _get_context("postlive")
    return render_template("postlive.html", **ctx)
