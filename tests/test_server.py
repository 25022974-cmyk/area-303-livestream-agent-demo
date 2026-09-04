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

"""Verification tests for AREA_303 Flask application and AI Decision Engine."""

import os
import sys
import unittest
from unittest import mock

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app import create_app


class TestArea303Server(unittest.TestCase):
    """Test suite for Flask routes and AI decision engine."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()
        # Default: AI disabled for the whole suite so existing tests never make
        # real network calls (even if a .env with proxy placeholders is present).
        # Patch on the route module (which imported the name) so the views see False.
        self._ai_patch = mock.patch(
            "src.routes.api_sessions.is_ai_configured", return_value=False
        )
        self._ai_patch.start()

    def tearDown(self):
        self._ai_patch.stop()

    def test_ui_routes(self):
        """Tests that all Jinja2 HTML page routes render successfully with 200 OK."""
        pages = ["/", "/prelive", "/onair", "/postlive"]
        for p in pages:
            res = self.client.get(f"{p}?shop_id=213989179")
            self.assertEqual(res.status_code, 200, f"Failed on page: {p}")
            self.assertIn(b"AREA_303", res.data)

    def test_api_list_shops(self):
        """Tests /api/shops endpoint lists available preloaded shops."""
        res = self.client.get("/api/shops")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertGreaterEqual(len(data["shops"]), 10)

    def test_api_get_shop(self):
        """Tests /api/shops/<shop_id> for Bibica."""
        res = self.client.get("/api/shops/213989179")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertGreater(data["product_count"], 0)

    def test_api_pipeline_run(self):
        """Tests running the 5-module decision engine via POST /api/pipeline/run."""
        payload = {
            "shop_id": "213989179",
            "budget_voucher_month": 500000000.0,
            "alpha": 0.5,
            "beta": 0.2,
        }
        res = self.client.post("/api/pipeline/run", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        rec = data["recommendation"]
        self.assertIn("m1_pricing", rec)
        self.assertIn("m2_heros", rec)
        self.assertIn("m3_timeslot", rec)
        self.assertIn("m4_combos", rec)
        self.assertIn("m5_voucher", rec)
        self.assertGreater(len(rec["m2_heros"]), 0)

    def test_session_lifecycle(self):
        """Tests saving draft playbook, logging live orders, and submitting feedback to learner loop."""
        shop_id = "213989179"

        # 1. Save draft playbook
        draft_payload = {
            "shop_id": shop_id,
            "slot": "20:00 – 22:00",
            "items": [{"item_id": "123", "name": "Bánh Zoo", "price": 50000}],
            "combos": [],
            "vouchers": [],
        }
        res_draft = self.client.post("/api/sessions/save-draft", json=draft_payload)
        self.assertEqual(res_draft.status_code, 200)

        # 2. Retrieve draft
        res_get_draft = self.client.get(f"/api/sessions/draft/{shop_id}")
        self.assertEqual(res_get_draft.status_code, 200)
        self.assertEqual(res_get_draft.get_json()["status"], "ok")

        # 3. Log live order
        order_payload = {
            "shop_id": shop_id,
            "order": {"item_id": "123", "product_name": "Bánh Zoo", "price": 50000, "quantity": 1},
        }
        res_order = self.client.post("/api/sessions/log-order", json=order_payload)
        self.assertEqual(res_order.status_code, 200)

        # 4. Get orders
        res_get_orders = self.client.get(f"/api/sessions/orders/{shop_id}")
        self.assertEqual(res_get_orders.status_code, 200)
        self.assertGreaterEqual(len(res_get_orders.get_json()["orders"]), 1)

        # 5. Submit feedback & update learner loop
        feedback_payload = {
            "shop_id": shop_id,
            "session_id": "test_session_01",
            "date": "2026-08-27",
            "actual": [
                {
                    "item_id": "123",
                    "estimated_sales": 20,
                    "actual_sales": 18,
                    "voucher_amount_used": 10000,
                    "voucher_redeemed": True,
                }
            ],
        }
        res_fb = self.client.post("/api/sessions/feedback", json=feedback_payload)
        self.assertEqual(res_fb.status_code, 200)
        fb_data = res_fb.get_json()
        self.assertEqual(fb_data["status"], "ok")
        self.assertGreater(fb_data["learning_state"]["metrics"]["n_sessions"], 0)

    def test_ai_next_slot_disabled_without_config(self):
        """When the LLM proxy is not configured, /api/sessions/ai-next-slot
        must return 200 with suggestion=None and NEVER make a network call.
        (setUp already disables AI; this just asserts the contract.)"""
        res = self.client.post(
            "/api/sessions/ai-next-slot",
            json={"shop_id": "213989179", "current_slot_index": 0},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertFalse(data["ai_configured"])
        self.assertIsNone(data["suggestion"])

    def test_feedback_returns_ai_report_null_without_config(self):
        """POST /api/sessions/feedback must still succeed and include ai_report
        (null) when the LLM proxy is not configured. (setUp already disables AI.)"""
        shop_id = "213989179"
        res = self.client.post(
            "/api/sessions/feedback",
            json={
                "shop_id": shop_id,
                "session_id": "test_session_ai",
                "date": "2026-08-28",
                "actual": [{
                    "item_id": "123",
                    "estimated_sales": 10,
                    "actual_sales": 9,
                    "voucher_amount_used": 0,
                    "voucher_redeemed": False,
                }],
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIsNone(data["ai_report"])
        self.assertFalse(data["ai_configured"])

    def test_dashboard_ui_route(self):
        """Tests that /dashboard page route renders with 200 OK."""
        res = self.client.get("/dashboard?shop_id=213989179")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"AREA_303", res.data)
        self.assertIn("Qu\u1ea3n L\u00fd D\u1eef Li\u1ec7u".encode("utf-8"), res.data)

    def test_api_dashboard_summary(self):
        """Tests GET /api/dashboard/<shop_id>/summary endpoint."""
        res = self.client.get("/api/dashboard/213989179/summary")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        summary = data["summary"]
        self.assertIn("total_files", summary)
        self.assertIn("total_bytes", summary)
        self.assertIn("draft_playbook", summary)
        self.assertIn("orders", summary)
        self.assertIn("learning_state", summary)

    def test_api_dashboard_orders_crud(self):
        """Tests order CRUD through /api/dashboard/<shop_id>/orders endpoints."""
        shop_id = "213989179"
        # 1. Log an order
        order_payload = {
            "shop_id": shop_id,
            "order": {"item_id": "test_sku_99", "product_name": "Bánh Test", "price": 45000, "quantity": 2},
        }
        res_log = self.client.post("/api/sessions/log-order", json=order_payload)
        self.assertEqual(res_log.status_code, 200)
        orders = res_log.get_json()["orders"]
        self.assertGreaterEqual(len(orders), 1)
        target_order = orders[-1]
        target_id = target_order["order_id"]

        # 2. Fetch orders via dashboard API
        res_get = self.client.get(f"/api/dashboard/{shop_id}/orders")
        self.assertEqual(res_get.status_code, 200)
        self.assertGreaterEqual(res_get.get_json()["count"], 1)

        # 3. Update order via dashboard API
        update_payload = {"product_name": "Bánh Test Updated", "price": 50000, "quantity": 3}
        res_put = self.client.put(f"/api/dashboard/{shop_id}/orders/{target_id}", json=update_payload)
        self.assertEqual(res_put.status_code, 200)
        updated_orders = res_put.get_json()["orders"]
        updated_item = next(o for o in updated_orders if o["order_id"] == target_id)
        self.assertEqual(updated_item["product_name"], "Bánh Test Updated")
        self.assertEqual(updated_item["price"], 50000)
        self.assertEqual(updated_item["quantity"], 3)

        # 4. Delete order via dashboard API
        res_del = self.client.delete(f"/api/dashboard/{shop_id}/orders/{target_id}")
        self.assertEqual(res_del.status_code, 200)
        remaining = res_del.get_json()["orders"]
        self.assertFalse(any(o["order_id"] == target_id for o in remaining))

    def test_api_dashboard_learner_actions(self):
        """Tests updating and resetting learner hyperparameters via dashboard API."""
        shop_id = "213989179"
        # 1. Update alpha and beta
        res_put = self.client.put(
            f"/api/dashboard/{shop_id}/learning-state",
            json={"alpha": 0.45, "beta": 0.15},
        )
        self.assertEqual(res_put.status_code, 200)
        st = res_put.get_json()["learning_state"]
        self.assertEqual(st["params"]["alpha"], 0.45)
        self.assertEqual(st["params"]["beta"], 0.15)

        # 2. Out of bounds test
        res_bad = self.client.put(
            f"/api/dashboard/{shop_id}/learning-state",
            json={"alpha": 99.0, "beta": 0.15},
        )
        self.assertEqual(res_bad.status_code, 400)

        # 3. Reset learner state
        res_reset = self.client.post(f"/api/dashboard/{shop_id}/learning-state/reset")
        self.assertEqual(res_reset.status_code, 200)
        reset_st = res_reset.get_json()["learning_state"]
        self.assertEqual(reset_st["params"]["alpha"], 0.5)
        self.assertEqual(reset_st["params"]["beta"], 0.2)

    def test_api_dashboard_playbooks_list(self):
        """Tests listing playbooks via dashboard API."""
        shop_id = "213989179"
        res = self.client.get(f"/api/dashboard/{shop_id}/playbooks")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["status"], "ok")
        self.assertIsInstance(data["archived"], list)


if __name__ == "__main__":
    unittest.main()
