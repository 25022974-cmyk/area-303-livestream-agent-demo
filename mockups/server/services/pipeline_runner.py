"""Pipeline runner — chạy model pipeline nền, đẩy events vào asyncio.Queue.

`pipeline.run_pipeline` là BLOCKING (stdlib thuần, không asyncio). Để không block
event loop FastAPI, chạy qua `loop.run_in_executor` threadpool. Callback `progress_cb`
được gọi từ sync thread -> dùng `asyncio.run_coroutine_threadsafe(queue.put(...), loop)`
đẩy event an toàn cross-thread vào queue của event loop.
"""
import asyncio
from typing import Any, Tuple

from modules import pipeline as model_pipeline

from .session_manager import Session


async def run_streaming(session: Session) -> Tuple[asyncio.Queue, "asyncio.Task[Any]"]:
    """Trả (queue events, background task). Caller drain queue -> gửi WS.

    Queue chứa tuples (event_name, payload). Cuối stream luôn ("done", recommendation_dict)
    hoặc ("error", error_message).
    """
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()

    def progress_cb(event_name: str, payload: Any) -> None:
        # Gọi từ sync thread (run_in_executor) -> schedule put vào loop.
        asyncio.run_coroutine_threadsafe(queue.put((event_name, payload)), loop)

    async def runner() -> None:
        def _run_blocking() -> dict:
            return model_pipeline.run_pipeline(
                session.data_pool, session.observations,
                shop_config=session.shop_config,
                learner_state=None,  # Phase D: truyền learning_state
                progress_cb=progress_cb,
            )

        try:
            result = await loop.run_in_executor(None, _run_blocking)
            await queue.put(("done", result))
        except Exception as exc:  # noqa: BLE001
            await queue.put(("error", str(exc)))

    task = asyncio.create_task(runner())
    return queue, task
