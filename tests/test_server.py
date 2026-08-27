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

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.app import create_app


class TestArea303Server(unittest.TestCase):
    """Test suite for Flask routes and AI decision engine."""

    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

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


if __name__ == "__main__":
    unittest.main()
