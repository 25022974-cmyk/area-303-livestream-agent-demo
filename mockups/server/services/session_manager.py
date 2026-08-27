"""Session registry in-memoryfür AREA_303 server.

Map session_id -> parsed (data_pool, snapshots, observations, shop_config).
Tồn tại trong RAM cho lần chạy hiện tại; WS connect lookup qua session_id.
"""
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class Session:
    session_id: str
    shop_id: str
    shop_config: Dict[str, Any]
    data_pool: List[Dict[str, Any]]
    snapshots: List[Dict[str, Any]]
    observations: List[Dict[str, Any]]
    csv_path: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


class SessionManager:
    def __init__(self) -> None:
        self._sessions: Dict[str, Session] = {}

    def create(self, shop_id: str, shop_config: Dict[str, Any],
               data_pool: List[Dict[str, Any]], snapshots: List[Dict[str, Any]],
               observations: List[Dict[str, Any]], csv_path: Optional[str] = None,
               warnings: Optional[List[str]] = None) -> Session:
        session_id = str(uuid.uuid4())
        s = Session(
            session_id=session_id, shop_id=shop_id, shop_config=shop_config,
            data_pool=data_pool, snapshots=snapshots, observations=observations,
            csv_path=csv_path, warnings=warnings or [],
        )
        self._sessions[session_id] = s
        return s

    def get(self, session_id: str) -> Optional[Session]:
        return self._sessions.get(session_id)

    def remove(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)


# Singleton trong runtime.
sessions = SessionManager()
