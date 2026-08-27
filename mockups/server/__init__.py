"""Server AREA_303 — FastAPI multi-tenant SaaS wrapper cho pipeline AI Livestream Strategist.

Separation of concerns:
- `model_bibica/modules/` (stdlib thuần) — pipeline/decision logic, không import fastapi.
- `server/` (FastAPI + Pydantic) — HTTP/WS layer, file IO, session management.

Prototype auth: `shop_id` là path param số, KHÔNG có password — không production-secure.
"""
