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

"""Flask Application Factory for AREA_303 AI Livestream Strategist."""

import datetime
from flask import Flask

from .config import STATIC_DIR, TEMPLATES_DIR
from .models._helpers import format_vnd
from .routes import api_dashboard_bp, api_debug_bp, api_pipeline_bp, api_sessions_bp, api_shops_bp, ui_bp


def create_app() -> Flask:
    """Creates and configures the Flask application instance."""
    app = Flask(
        __name__,
        static_folder=str(STATIC_DIR),
        template_folder=str(TEMPLATES_DIR),
    )

    # Secret key for sessions
    app.config["SECRET_KEY"] = "area303-livestream-agent-secret-key-2026"

    # Register Jinja2 template filters
    @app.template_filter("vnd")
    def jinja_vnd(val):
        return format_vnd(val)

    @app.template_filter("num")
    def jinja_num(val):
        try:
            return f"{int(round(float(val or 0))):,}"
        except Exception:
            return "0"

    @app.template_filter("pct")
    def jinja_pct(val):
        try:
            return f"{float(val or 0):.1f}%"
        except Exception:
            return "0.0%"

    @app.template_filter("datetime_fmt")
    def jinja_datetime(val):
        try:
            if isinstance(val, str):
                dt = datetime.datetime.fromisoformat(val)
            elif isinstance(val, (int, float)):
                dt = datetime.datetime.fromtimestamp(val, tz=datetime.timezone.utc)
            else:
                dt = val
            return dt.strftime("%d/%m/%Y %H:%M")
        except Exception:
            return str(val)

    # Register Blueprints
    app.register_blueprint(ui_bp)
    app.register_blueprint(api_shops_bp)
    app.register_blueprint(api_pipeline_bp)
    app.register_blueprint(api_sessions_bp)
    app.register_blueprint(api_dashboard_bp)
    app.register_blueprint(api_debug_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=5000, debug=True)
