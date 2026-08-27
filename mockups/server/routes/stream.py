"""WebSocket endpoint AREA_303 — chạy pipeline nền, đẩy events realtime."""
import asyncio
import json
import re

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..services import shop_state
from ..services.pipeline_runner import run_streaming
from ..services.session_manager import sessions

router = APIRouter(prefix="/shops", tags=["stream"])

_SHOP_ID_RE = re.compile(r"^\d+$")


@router.websocket("/{shop_id}/stream/{session_id}")
async def stream(ws: WebSocket, shop_id: str, session_id: str) -> None:
    """
    Mở WS để chạy pipeline. Server đẩy events:
      loading, module1..module5, (learner Phase D), done | error
    Sau "done": payload là recommendation dict đầy đủ; server lưu JSON vào shops/{shop_id}/recommendations/.
    """
    await ws.accept()
    if not shop_id or not _SHOP_ID_RE.match(shop_id):
        await ws.send_json({"event": "error", "error": "shop_id phải là chuỗi số."})
        await ws.close()
        return

    session = sessions.get(session_id)
    if not session or session.shop_id != shop_id:
        await ws.send_json({"event": "error", "error": "session không hợp lệ hoặc không thuộc shop này."})
        await ws.close()
        return

    queue, task = await run_streaming(session)

    try:
        while True:
            event_name, payload = await queue.get()
            if event_name == "done":
                # Lưu recommendation (server chịu trách nhiệm file IO, không phải model).
                if isinstance(payload, dict):
                    try:
                        shop_state.save_recommendation(shop_id, payload)
                    except Exception as exc:  # noqa: BLE001
                        await ws.send_json({"event": "error", "error": f"save recommendation failed: {exc}"})
                await ws.send_json({"event": "done", "payload": payload})
                break
            if event_name == "error":
                await ws.send_json({"event": "error", "error": payload})
                break
            await ws.send_json({"event": event_name, "payload": payload})

        await task  # đảm bảo task sạch
        # Giữ WS mở thêm cho Phase D feedback (server nhận text frame; Phase A chỉ ping).
        while True:
            try:
                await ws.receive_text()  # ignore Phase A
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        if not task.done():
            task.cancel()
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
        sessions.remove(session_id)
