"""
Tests for restocking API endpoints.
"""
from datetime import datetime, timedelta

import pytest

import main


@pytest.fixture(autouse=True)
def reset_restock_orders():
    """Clear in-memory restock orders so every test starts from an empty list."""
    main.restock_orders.clear()
    yield
    main.restock_orders.clear()


class TestDemandForecastPricing:
    """Test suite for pricing fields added to demand forecasts."""

    def test_demand_forecasts_include_pricing(self, client):
        """Test that every forecast has a unit cost and lead time."""
        response = client.get("/api/demand")
        assert response.status_code == 200

        data = response.json()
        assert len(data) > 0
        for forecast in data:
            assert isinstance(forecast["unit_cost"], (int, float))
            assert isinstance(forecast["lead_time_days"], int)
            assert forecast["unit_cost"] > 0, f"{forecast['item_sku']} has no price"
            assert forecast["lead_time_days"] > 0, f"{forecast['item_sku']} has no lead time"


class TestRestockingRecommendations:
    """Test suite for restock recommendation endpoint."""

    def test_default_budget_recommendations(self, client):
        """Test the default $5,000 budget fills two items fully and one partially."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert data["budget"] == 5000
        recs = data["recommendations"]
        assert [r["item_sku"] for r in recs] == ["FLT-405", "WDG-001", "GSK-203"]
        assert [r["recommended_quantity"] for r in recs] == [150, 150, 1]
        assert [r["partial"] for r in recs] == [False, False, True]
        assert abs(data["total_cost"] - 4998.75) < 0.01
        assert abs(data["remaining_budget"] - 1.25) < 0.01
        assert data["item_count"] == 3
        assert data["max_lead_time_days"] == 7

    def test_recommendations_structure(self, client):
        """Test that each recommendation has all required fields."""
        response = client.get("/api/restocking/recommendations?budget=10000")
        data = response.json()

        for rec in data["recommendations"]:
            for field in [
                "item_sku", "item_name", "trend", "current_demand", "forecasted_demand",
                "demand_gap", "recommended_quantity", "unit_cost", "line_total",
                "lead_time_days", "partial",
            ]:
                assert field in rec, f"Missing field {field}"
            assert isinstance(rec["recommended_quantity"], int)
            assert rec["recommended_quantity"] > 0

    def test_increasing_trend_ranked_first(self, client):
        """Test that increasing-demand items come before stable ones and shrinking demand is skipped."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        recs = response.json()["recommendations"]

        trends = [r["trend"] for r in recs]
        last_increasing = max(i for i, t in enumerate(trends) if t == "increasing")
        first_stable = min(i for i, t in enumerate(trends) if t == "stable")
        assert last_increasing < first_stable
        assert "MTR-304" not in [r["item_sku"] for r in recs]
        assert all(r["demand_gap"] > 0 for r in recs)

    def test_large_budget_covers_all_gaps(self, client):
        """Test that a large budget recommends every positive gap in full."""
        response = client.get("/api/restocking/recommendations?budget=100000")
        data = response.json()

        assert data["item_count"] == 8
        assert abs(data["total_cost"] - 6877.98) < 0.01
        assert data["max_lead_time_days"] == 14
        for rec in data["recommendations"]:
            assert rec["partial"] is False
            assert rec["recommended_quantity"] == rec["demand_gap"]

    def test_partial_first_item_stops_filling(self, client):
        """Test that when the top item doesn't fit, it is partial and nothing else is added."""
        response = client.get("/api/restocking/recommendations?budget=1000")
        data = response.json()

        assert len(data["recommendations"]) == 1
        rec = data["recommendations"][0]
        assert rec["item_sku"] == "FLT-405"
        assert rec["recommended_quantity"] == 121
        assert rec["partial"] is True
        assert abs(data["total_cost"] - 998.25) < 0.01

    @pytest.mark.parametrize("budget", [0, 5])
    def test_budget_too_small(self, client, budget):
        """Test that a budget below the cheapest top-priority unit gives no recommendations."""
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        assert response.status_code == 200

        data = response.json()
        assert data["recommendations"] == []
        assert data["item_count"] == 0
        assert data["total_cost"] == 0
        assert data["max_lead_time_days"] == 0

    @pytest.mark.parametrize("budget", [0, 50, 1000, 2500, 5000, 6000, 6877.98, 10000])
    def test_total_within_budget_calculation(self, client, budget):
        """Test that totals never exceed the budget and add up line by line."""
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        data = response.json()

        assert data["total_cost"] <= budget + 0.001
        assert abs(data["total_cost"] + data["remaining_budget"] - budget) < 0.01
        for rec in data["recommendations"]:
            assert abs(rec["line_total"] - rec["recommended_quantity"] * rec["unit_cost"]) < 0.01
        assert abs(sum(r["line_total"] for r in data["recommendations"]) - data["total_cost"]) < 0.01

    @pytest.mark.parametrize("budget", ["-1", "abc"])
    def test_invalid_budget(self, client, budget):
        """Test that negative or non-numeric budgets are rejected."""
        response = client.get(f"/api/restocking/recommendations?budget={budget}")
        assert response.status_code == 422


class TestRestockingOrders:
    """Test suite for submitting and listing restocking orders."""

    def test_create_restock_order(self, client):
        """Test submitting a valid restocking order."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "FLT-405", "quantity": 10}, {"item_sku": "VLV-506", "quantity": 2}]},
        )
        assert response.status_code == 201

        order = response.json()
        assert order["id"] == "RST-0001"
        assert order["status"] == "Submitted"
        assert abs(order["total_cost"] - (10 * 8.25 + 2 * 156.00)) < 0.01
        assert order["lead_time_days"] == 14
        assert len(order["items"]) == 2

        submitted_at = datetime.fromisoformat(order["submitted_at"])
        expected_delivery = datetime.fromisoformat(order["expected_delivery"])
        assert expected_delivery - submitted_at == timedelta(days=14)

    def test_create_order_ignores_client_prices(self, client):
        """Test that prices sent by the client are ignored in favor of server data."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "FLT-405", "quantity": 10, "unit_cost": 0.01, "line_total": 0.1}]},
        )
        assert response.status_code == 201

        order = response.json()
        assert order["items"][0]["unit_cost"] == 8.25
        assert abs(order["total_cost"] - 82.50) < 0.01

    @pytest.mark.parametrize("payload", [
        {},
        {"items": []},
        {"items": [{"item_sku": "FLT-405", "quantity": 0}]},
        {"items": [{"item_sku": "FLT-405", "quantity": -3}]},
        {"items": [{"item_sku": "NOPE-000", "quantity": 1}]},
        {"items": [{"item_sku": "FLT-405", "quantity": 1}, {"item_sku": "FLT-405", "quantity": 2}]},
        {"items": [{"item_sku": "FLT-405", "quantity": 1}], "budget": -5},
    ])
    def test_create_order_validation_errors(self, client, payload):
        """Test that invalid orders are rejected and not stored."""
        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 422
        assert "detail" in response.json()

        assert client.get("/api/restocking/orders").json() == []

    def test_create_order_unknown_sku_message(self, client):
        """Test that an unknown SKU error names the SKU."""
        response = client.post("/api/restocking/orders", json={"items": [{"item_sku": "NOPE-000", "quantity": 1}]})
        assert response.status_code == 422
        assert "NOPE-000" in response.json()["detail"]

    def test_create_order_over_budget(self, client):
        """Test that an order costing more than its budget is rejected."""
        response = client.post(
            "/api/restocking/orders",
            json={"items": [{"item_sku": "FLT-405", "quantity": 150}], "budget": 100},
        )
        assert response.status_code == 422
        assert "exceeds budget" in response.json()["detail"]

    def test_get_restock_orders_empty(self, client):
        """Test that the order list starts empty."""
        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert response.json() == []

    def test_get_restock_orders_newest_first(self, client):
        """Test that submitted orders are listed newest first."""
        for quantity in (1, 2):
            client.post("/api/restocking/orders", json={"items": [{"item_sku": "GSK-203", "quantity": quantity}]})

        response = client.get("/api/restocking/orders")
        assert response.status_code == 200
        assert [o["id"] for o in response.json()] == ["RST-0002", "RST-0001"]

    def test_recommendations_round_trip(self, client):
        """Test that recommendations posted as an order are accepted with the same total."""
        recommendations = client.get("/api/restocking/recommendations?budget=5000").json()
        payload = {
            "items": [
                {"item_sku": r["item_sku"], "quantity": r["recommended_quantity"]}
                for r in recommendations["recommendations"]
            ],
            "budget": recommendations["budget"],
        }

        response = client.post("/api/restocking/orders", json=payload)
        assert response.status_code == 201

        order = response.json()
        assert abs(order["total_cost"] - recommendations["total_cost"]) < 0.01
        assert order["lead_time_days"] == recommendations["max_lead_time_days"]
