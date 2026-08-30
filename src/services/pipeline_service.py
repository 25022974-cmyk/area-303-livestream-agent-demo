# Copyright (C) 2026 Nguyen The Viet, Vu Thi Mai Anh, Do Huu An Phu, Phan Thuy Tram
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Pipeline execution service executing M1-M5 models for shop sessions."""

from typing import Any, Dict, List, Optional

from ..models.pipeline import run_pipeline
from .ai_service import is_ai_configured, suggest_timeslot
from .session_service import session_service
from .shop_service import shop_service


class PipelineService:
    """Service providing end-to-end execution of the livestream decision engine."""

    def run_for_shop(
        self,
        shop_id: str,
        budget_voucher_month: Optional[float] = None,
        alpha: Optional[float] = None,
        beta: Optional[float] = None,
        use_dp_knapsack: Optional[bool] = None,
        must_select_all: Optional[bool] = None,
        item_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Runs the complete AI decision engine for a specified shop.

        Khi `item_ids` không None, data_pool được lọc chỉ giữ các SKU có item_id
        trong tập này trước khi chạy pipeline. Đây là cách UI truyền tập SKU đã tick
        làm đầu vào cho M5 (phân voucher cho đúng tập đã chọn).
        """
        data_pool, snapshots, observations = shop_service.load_shop_data(shop_id)
        config = shop_service.load_shop_config(shop_id)
        learning_state = shop_service.load_learning_state(shop_id)

        # Lọc data_pool theo danh sách SKU đã tick (nếu được cung cấp)
        if item_ids is not None:
            ids_set = {str(i) for i in item_ids}
            data_pool = [r for r in data_pool if str(r.get("item_id")) in ids_set]

        # Apply runtime overrides if provided
        if budget_voucher_month is not None:
            config["budget_voucher_month"] = float(budget_voucher_month)
        if alpha is not None:
            config["alpha"] = float(alpha)
        if beta is not None:
            config["beta"] = float(beta)
        if use_dp_knapsack is not None:
            config["use_dp_knapsack"] = bool(use_dp_knapsack)
        if must_select_all is not None:
            config["must_select_all"] = bool(must_select_all)

        # Merge industry snapshots from all shops for market-level FE elasticity & timeslots
        industry_snapshots = shop_service.load_all_industry_snapshots()
        if not industry_snapshots:
            industry_snapshots = snapshots

        result = run_pipeline(
            data_pool=data_pool,
            observations=observations,
            shop_config=config,
            learning_state=learning_state,
            snapshots=industry_snapshots,
        )

        # Augment M3 timeslot with an AI suggestion built from past-session logs.
        # This is best-effort: it never overrides the heuristic start/end hours
        # (which drive the time inputs + heatmap) — it only adds advice text.
        try:
            ts_block = result.get("m3_timeslot") if isinstance(result, dict) else None
            if isinstance(ts_block, dict):
                past_ctx = session_service.build_timeslot_ai_context(shop_id, max_sessions=12)
                n_sessions = int(past_ctx.get("n_sessions", 0) or 0)
                ai_configured = is_ai_configured()
                # Only ask the AI when there is real history to reason from.
                # Without logs, an AI answer would be a hallucinated guess.
                ai_advice = None
                if n_sessions > 0 and ai_configured:
                    industry_evidence = (ts_block.get("evidence") or {}) if isinstance(ts_block.get("evidence"), dict) else None
                    ai_advice = suggest_timeslot(
                        shop_id=shop_id,
                        past_context=past_ctx,
                        industry_signal=industry_evidence,
                    )
                ts_block["ai_advice"] = ai_advice
                ts_block["ai_advice_source"] = {
                    "n_sessions": n_sessions,
                    "n_sessions_co_review": int(past_ctx.get("n_sessions_co_review", 0) or 0),
                    "available": n_sessions > 0,
                    "ai_configured": ai_configured,
                }
        except Exception:
            # AI timeslot advice must never break the pipeline.
            pass

        return result


pipeline_service = PipelineService()
