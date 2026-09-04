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

"""Pluggable storage backend for per-shop writable state.

On a normal local run we write to the filesystem (``data/shops/<id>/...``). On
Vercel serverless the filesystem is ephemeral (``/tmp`` is wiped on cold start /
redeploy), so we swap in a Blob-backed implementation that talks to Vercel Blob
over HTTP. ``ShopService`` is agnostic of the concrete backend; only the env at
boot decides which adapter is in use (see ``get_storage_backend``).
"""

from __future__ import annotations

from .base import StorageBackend, get_storage_backend  # noqa: F401
