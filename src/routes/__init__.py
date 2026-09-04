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

"""Route Blueprints for AREA_303 Livestream Strategist."""

from .api_pipeline import api_pipeline_bp
from .api_sessions import api_sessions_bp
from .api_shops import api_shops_bp
from .api_dashboard import api_dashboard_bp
from .api_debug import api_debug_bp
from .ui import ui_bp

__all__ = ["ui_bp", "api_shops_bp", "api_pipeline_bp", "api_sessions_bp", "api_dashboard_bp", "api_debug_bp"]
