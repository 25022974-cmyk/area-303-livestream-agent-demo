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

import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ──────────────────────────────────────────────────────────────────────
# Ensure httpx/urllib can verify TLS even on runtimes/installs whose own
# trust store is missing (Vercel @vercel/python on AWS Lambda, and some
# minimal Windows Pythons). Both httpx (used by the `vercel.blob` SDK
# backing BlobPath) and urllib respect SSL_CERT_FILE / SSL_CA_FILE /
# REQUESTS_CA_BUNDLE when trust_env is on. Pointing them at certifi's
# Mozilla bundle, if available, gives a complete root + intermediate set
# and fixes "[SSL: CERTIFICATE_VERIFY_FAILED] unable to get local issuer
# certificate" on Blob calls. Set BEFORE importing src.app so any storage
# / http client picks it up.
# ──────────────────────────────────────────────────────────────────────
for _ca_env in ("SSL_CERT_FILE", "SSL_CA_FILE", "REQUESTS_CA_BUNDLE"):
    if not os.environ.get(_ca_env):
        try:
            import certifi  # type: ignore
            os.environ[_ca_env] = certifi.where()
            break
        except Exception:
            pass

from src.app import create_app  # noqa: E402

# WSGI app served by Vercel for every matched route.
app = create_app()
