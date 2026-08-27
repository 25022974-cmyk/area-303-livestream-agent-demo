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

from typing import Any, Dict, Optional

from ..models.pipeline import run_pipeline
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
    ) -> Dict[str, Any]:
        """Runs the complete AI decision engine for a specified shop."""
        data_pool, snapshots, observations = shop_service.load_shop_data(shop_id)
        config = shop_service.load_shop_config(shop_id)
        learning_state = shop_service.load_learning_state(shop_id)

        # Apply runtime overrides if provided
        if budget_voucher_month is not None:
            config["budget_voucher_month"] = float(budget_voucher_month)
        if alpha is not None:
            config["alpha"] = float(alpha)
        if beta is not None:
            config["beta"] = float(beta)
        if use_dp_knapsack is not None:
            config["use_dp_knapsack"] = bool(use_dp_knapsack)

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

        return result


pipeline_service = PipelineService()
