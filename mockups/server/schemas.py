"""Pydantic models cho request/response của AREA_303 server."""
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class ShopConfigRequest(BaseModel):
    """Tuỳ chọn gửi kèm khi upload (budget/alpha/beta của shop)."""
    shop_name: Optional[str] = None
    budget_voucher_month: float = 500_000_000
    alpha: float = 0.5
    beta: float = 0.2
    use_dp_knapsack: bool = True


class ShopConfig(ShopConfigRequest):
    """Shop config đầy đủ (serve nội bộ, thêm shop_id)."""
    shop_id: str


class UploadResponse(BaseModel):
    shop_id: str
    session_id: str
    rows_received: int = Field(description="Tổng số row parse được (snapshots)")
    rows_deduped: int = Field(description="Số SKU duy nhất (data_pool)")
    distinct_catids: int
    line_assignment: str = Field(description="'synthetic' | 'real_catid' | 'synthetic_none'")
    warnings: list[str] = []
    missing_columns: list[str] = []


class WSEvent(BaseModel):
    event: Literal["loading", "module1", "module2", "module3", "module4",
                   "module5", "learner", "done", "error"]
    payload: Optional[dict[str, Any]] = None
    error: Optional[str] = None


class FeedbackItem(BaseModel):
    item_id: str
    scenario_used: Literal["hold", "mild", "flash"]
    discount_used_pct: float
    estimated_sales: float
    actual_sales: Optional[float] = None
    voucher_amount_used: float = 0.0
    voucher_redeemed: Optional[bool] = None
    combo_sold: Optional[bool] = None


class FeedbackRequest(BaseModel):
    session_id: str
    date: str
    actual: list[FeedbackItem]


class LearningState(BaseModel):
    version: int = 1
    last_session_id: Optional[str] = None
    params: dict[str, Any]
    metrics: dict[str, Any]
    bounds: dict[str, Any]


class ShopStateResponse(BaseModel):
    shop_id: str
    learning_state: Optional[LearningState] = None
    sessions: list[str] = []
