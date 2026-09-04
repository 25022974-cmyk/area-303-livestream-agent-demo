# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or (at
# your option) any later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <https://www.gnu.org/licenses/>.

"""Diagnostic endpoint to inspect the runtime storage backend and SSL setup.

Exposed at ``/api/_debug/storage``. Returns environment + SSL context facts,
whether ``BLOB_READ_WRITE_TOKEN``/``BLOB_STORE_URL`` are set (without
revealing their values), which backend is active, and the result of a probe
LIST call to the Blob endpoint. This lets us diagnose "certificate verify
failed" errors without disabling TLS verification blindly. Remove or gate
this route before shipping if the demo goes public beyond trusted viewers.
"""

import os
import ssl

from flask import Blueprint

from ..services.shop_service import shop_service
from ..services.storage import get_storage_backend
from ..services.storage import vercel_blob as vb

api_debug_bp = Blueprint("api_debug", __name__, url_prefix="/api/_debug")


def _mask(v: str) -> str:
    if not v:
        return "<unset>"
    if len(v) <= 8:
        return "<set>"
    return f"<set, len={len(v)}, head={v[:2]}...>"


@api_debug_bp.route("/storage", methods=["GET"])
def storage_info():
    info = {
        "env": {
            "VERCEL": os.environ.get("VERCEL", ""),
            "LAMBDA_TASK_ROOT": os.environ.get("LAMBDA_TASK_ROOT", ""),
            "BLOB_READ_WRITE_TOKEN": _mask(os.environ.get("BLOB_READ_WRITE_TOKEN", "")),
            "BLOB_STORE_URL": os.environ.get("BLOB_STORE_URL", ""),
            "AREA303_STORAGE_BACKEND": os.environ.get("AREA303_STORAGE_BACKEND", ""),
        },
        "backend": {
            "active": shop_service.backend.name,
            "factory_selects": get_storage_backend().name,
        },
        "blob_base": vb._BLOB_BASE,
        "ssl_context": {
            "verify_mode": vb._SSL_CONTEXT.verify_mode,  # 0=CERT_NONE, 2=CERT_REQUIRED
            "check_hostname": vb._SSL_CONTEXT.check_hostname,
            "ca_certs_count": len(vb._SSL_CONTEXT.get_ca_certs()),
        },
        "python_ssl": {
            "OPENSSL_VERSION": ssl.OPENSSL_VERSION,
            "DEFAULT_CIPHERS": ssl._DEFAULT_CIPHERS if hasattr(ssl, "_DEFAULT_CIPHERS") else None,
        },
    }

    # Probe the Blob LIST endpoint to capture the real error.
    probe = {"ok": None, "error": None, "status": None, "body_excerpt": None}
    if os.environ.get("BLOB_READ_WRITE_TOKEN"):
        try:
            blobs = vb.VercelBlobBackend()._list_prefix("area303/")
            probe["ok"] = True
            probe["blob_count"] = len(blobs)
        except Exception as e:
            probe["ok"] = False
            probe["error"] = f"{type(e).__name__}: {e}"
            # If it's an HTTPError, surface the code
            eh = getattr(e, "headers", None)
            if hasattr(e, "code"):
                probe["status"] = e.code
            try:
                probe["body_excerpt"] = e.read().decode("utf-8", "replace")[:300] if hasattr(e, "read") else None
            except Exception:
                pass

    return {"status": "ok", "info": info, "blob_probe": probe}
