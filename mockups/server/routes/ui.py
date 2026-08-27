"""Serve web UI — 3 trung tâm điều phối phiên live (Pre / On-air / Post).

    cd D:/UET/competition/AREA_303
    uvicorn server.main:app --reload --app-dir .

Pages:
    GET /         → index.html   (landing + progress)
    GET /prelive   → prelive.html
    GET /onair     → onair.html
    GET /postlive  → postlive.html
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..config import STATIC_DIR

router = APIRouter(tags=["ui"])

# Static assets (css/js/data.js) được mount trực tiếp trên app trong main.py.

_PAGES = {
    "index.html": "/",
    "prelive.html": "/prelive",
    "onair.html": "/onair",
    "postlive.html": "/postlive",
}


def _serve(filename: str):
    async def _h():
        path = STATIC_DIR / filename
        if not path.is_file():
            raise HTTPException(404, f"{filename} not found")
        return FileResponse(path)
    return _h


# Route chuẩn (không đuôi .html) + route có đuôi .html cho ai gõ / link tới.
for fname, route in _PAGES.items():
    handler = _serve(fname)
    router.add_api_route(route, handler, include_in_schema=False, methods=["GET"])
    router.add_api_route("/" + fname, handler, include_in_schema=False, methods=["GET"])
