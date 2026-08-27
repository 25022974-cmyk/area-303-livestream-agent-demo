"""REST endpoints cho shops AREA_303: upload CSV, feedback, state."""
import csv
import io
import json
import re
from typing import Any, List

from fastapi import APIRouter, Body, File, Form, HTTPException, Path, Query, UploadFile

from ..config import (
    DEFAULT_ALPHA, DEFAULT_BETA, DEFAULT_BUDGET_VOUCHER_MONTH,
    DEFAULT_USE_DP_KNAPSACK, MAX_UPLOAD_BYTES,
)
from ..schemas import (
    FeedbackRequest, LearningState, ShopConfigRequest, ShopStateResponse,
    UploadResponse,
)
from ..services import shop_state
from ..services.session_manager import sessions
from modules import loader as model_loader
from modules import m1_price

router = APIRouter(prefix="/shops", tags=["shops"])

_SHOP_ID_RE = re.compile(r"^\d+$")


def _validate_shop_id(shop_id: str) -> str:
    if not shop_id or not _SHOP_ID_RE.match(shop_id):
        raise HTTPException(status_code=400, detail="shop_id phải là chuỗi số.")
    return shop_id


def _shop_config_dict(shop_id: str, cfg: ShopConfigRequest | None) -> dict[str, Any]:
    c = cfg or ShopConfigRequest()
    return {
        "shop_id": shop_id,
        "shop_name": c.shop_name or "",
        "budget_voucher_month": c.budget_voucher_month,
        "alpha": c.alpha,
        "beta": c.beta,
        "use_dp_knapsack": c.use_dp_knapsack,
    }


@router.post("/{shop_id}/upload", response_model=UploadResponse)
async def upload(
    shop_id: str = Path(..., pattern=r"^\d+$"),
    file: UploadFile = File(...),
    shop_name: str | None = Form(None),
    budget_voucher_month: float = Form(DEFAULT_BUDGET_VOUCHER_MONTH),
    alpha: float = Form(DEFAULT_ALPHA),
    beta: float = Form(DEFAULT_BETA),
    use_dp_knapsack: bool = Form(DEFAULT_USE_DP_KNAPSACK),
) -> UploadResponse:
    """
    Upload CSV sản phẩm Shopee của shop. Parse + validate ngay, đăng ký session,
    trả session_id. Client mở WS `/shops/{shop_id}/stream/{session_id}` để chạy pipeline.

    Prototype auth: shop_id là path param số, không có password — KHÔNG production-secure.
    """
    _validate_shop_id(shop_id)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"File quá lớn (max {MAX_UPLOAD_BYTES} bytes).")
    if not raw:
        raise HTTPException(400, "File rỗng.")

    # Parse CSV qua loader (nhận bytes).
    try:
        data_pool, snapshots = model_loader.load_csv(raw)
    except model_loader.LoaderError as exc:
        raise HTTPException(400, detail={
            "message": str(exc), "missing_columns": exc.missing_columns,
        })

    # Gán line đã xong trong loader; build observations cho M1.
    observations = m1_price.build_observations(snapshots)

    # Lưu raw CSV + config cho reproduction.
    csv_path = shop_state.save_csv(shop_id, raw)
    shop_cfg = _shop_config_dict(shop_id, ShopConfigRequest(
        shop_name=shop_name, budget_voucher_month=budget_voucher_month,
        alpha=alpha, beta=beta, use_dp_knapsack=use_dp_knapsack,
    ))
    shop_cfg_for_save = dict(shop_cfg)
    shop_cfg_for_save["csv_path"] = str(csv_path)
    shop_state.save_config(shop_id, shop_cfg_for_save)

    # Distinct catids + kia gán line kiểu nào.
    catids = {r.get("catid") for r in snapshots if r.get("catid") not in (None, "", "None")}
    # Lấy kiểu line_assignment từ snapshots (loader đã mutate).
    line_assignment = "synthetic" if all(r.get("line") for r in snapshots) else "synthetic_none"
    # heuristic: nếu có nhiều catid khác nhau -> real_catid
    distinct_count = len(catids)
    if distinct_count > 1:
        line_assignment = "real_catid"

    warnings: List[str] = []
    if len(observations) < 5:
        warnings.append(f"Chỉ có {len(observations)} observation (cần >=5 cho elasticity thật) — sẽ dùng fallback β=-1 → ép hold.")
    if distinct_count <= 1:
        warnings.append("1 catid -> dòng synthetic line từ keyword tên (guessing).")

    sess = sessions.create(
        shop_id=shop_id, shop_config=shop_cfg,
        data_pool=data_pool, snapshots=snapshots, observations=observations,
        csv_path=str(csv_path), warnings=warnings,
    )

    return UploadResponse(
        shop_id=shop_id, session_id=sess.session_id,
        rows_received=len(snapshots), rows_deduped=len(data_pool),
        distinct_catids=distinct_count, line_assignment=line_assignment,
        warnings=warnings, missing_columns=[],
    )


@router.get("/{shop_id}/state", response_model=ShopStateResponse)
async def get_state(shop_id: str = Path(..., pattern=r"^\d+$")) -> ShopStateResponse:
    """Trả learning_state hiện tại + danh sách sessions đã chạy."""
    _validate_shop_id(shop_id)
    state = shop_state.load_learning_state(shop_id)
    return ShopStateResponse(
        shop_id=shop_id,
        learning_state=LearningState(**state) if state else None,
        sessions=shop_state.list_sessions(shop_id),
    )


@router.post("/{shop_id}/feedback", response_model=LearningState)
async def post_feedback(shop_id: str = Path(..., pattern=r"^\d+$"), body: FeedbackRequest = Body(...)) -> LearningState:
    """Phase D: submit actual sales -> learner update. Phase A: trả state rỗng/mặc định."""
    _validate_shop_id(shop_id)
    state = shop_state.load_learning_state(shop_id) or _default_learning_state()
    # TODO Phase D: learner.update(state, body)
    shop_state.save_learning_state(shop_id, state)
    return LearningState(**state)


def _default_learning_state() -> dict[str, Any]:
    return {
        "version": 1,
        "last_session_id": None,
        "params": {"alpha": DEFAULT_ALPHA, "beta": DEFAULT_BETA, "elasticity_beta_by_line": {}},
        "metrics": {"n_sessions": 0, "rolling_mape": None, "rolling_redeem_rate": None, "lift_vs_hold": None},
        "bounds": {"alpha": [0.1, 1.0], "beta": [0.0, 0.5], "discount_pct": [0, 36]},
    }
