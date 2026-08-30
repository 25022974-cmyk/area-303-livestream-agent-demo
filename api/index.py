# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; even without the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Vercel serverless entry point.

Vercel's @vercel/python runtime imports this module and calls its `app`
attribute as the WSGI handler. We re-export the Flask factory `create_app()`
so the same application object powers every route (UI + API + static),
without touching the original `src/run.py` used for local development.

sys.path is adjusted defensively because Vercel may run the function with a
cwd that does not include the project root, which would break
``from src.app import create_app``.
"""

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.app import create_app  # noqa: E402

# WSGI app served by Vercel for every matched route.
app = create_app()
