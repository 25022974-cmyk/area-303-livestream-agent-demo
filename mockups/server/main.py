"""FastAPI app AREA_303 — mount routes, serve UI.

Chạy:
    cd D:/UET/competition/AREA_303
    uvicorn server.main:app --reload --app-dir .

Prototype auth: shop_id là path param số, KHÔNG có password — KHÔNG production-secure.
Model bộ não nằm ở `model_bibica/modules/` (stdlib thuần); server chỉ là lớp HTTP/WS + file IO.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import STATIC_DIR
from .routes import shops as shops_routes
from .routes import stream as stream_routes
from .routes import ui as ui_routes

app = FastAPI(
    title="AREA_303 — AI Livestream Strategist Server",
    description=(
        "Multi-tenant SaaS wrapper cho pipeline AREA_303. Shop upload CSV sản phẩm Shopee "
        "→ server chạy 5 module (giá/hero/giờ/combo/voucher) → đẩy đề xuất về qua WebSocket.\n\n"
        "⚠️ Prototype auth: shop_id là path param số, KHÔNG có password. "
        "KHÔNG production-secure — thay bằng auth thật trước khi triển khai."
    ),
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(shops_routes.router)
app.include_router(stream_routes.router)
app.include_router(ui_routes.router)

# Serve static assets (css/js/data.js) — mount trên app thay vì router con.
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health", tags=["meta"])
async def health():
    return {"status": "ok"}
