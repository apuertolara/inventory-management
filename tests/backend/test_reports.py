"""
Tests for reports API endpoints (quarterly performance and monthly trends).
"""
import pytest


class TestQuarterlyReportEndpoints:
    """Test suite for the quarterly report endpoint."""

    def test_get_all_quarterly_reports(self, client):
        """Test getting quarterly reports without filters."""
        response = client.get("/api/reports/quarterly")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        first = data[0]
        for field in ["quarter", "total_orders", "total_revenue", "delivered_orders",
                      "avg_order_value", "fulfillment_rate"]:
            assert field in first

    def test_quarterly_reports_sorted(self, client):
        """Test that quarters are returned in chronological order."""
        data = client.get("/api/reports/quarterly").json()
        quarters = [q["quarter"] for q in data]
        assert quarters == sorted(quarters)

    def test_quarterly_totals_match_orders(self, client):
        """Test that quarterly totals add up to the raw orders."""
        orders = client.get("/api/orders").json()
        data = client.get("/api/reports/quarterly").json()

        assert sum(q["total_orders"] for q in data) == len(orders)
        expected_revenue = sum(o["total_value"] for o in orders)
        assert abs(sum(q["total_revenue"] for q in data) - expected_revenue) < 1

    def test_quarterly_calculations(self, client):
        """Test average order value and fulfillment rate calculations."""
        data = client.get("/api/reports/quarterly").json()

        for q in data:
            assert q["total_orders"] > 0
            assert abs(q["avg_order_value"] - q["total_revenue"] / q["total_orders"]) < 0.01
            expected_rate = q["delivered_orders"] / q["total_orders"] * 100
            assert abs(q["fulfillment_rate"] - expected_rate) < 0.1
            assert 0 <= q["fulfillment_rate"] <= 100

    def test_get_quarterly_reports_by_warehouse(self, client):
        """Test filtering quarterly reports by warehouse."""
        orders = client.get("/api/orders?warehouse=Tokyo").json()
        data = client.get("/api/reports/quarterly?warehouse=Tokyo").json()

        assert sum(q["total_orders"] for q in data) == len(orders)

    def test_get_quarterly_reports_by_status(self, client):
        """Test that a Delivered status filter yields 100% fulfillment."""
        data = client.get("/api/reports/quarterly?status=delivered").json()

        assert len(data) > 0
        for q in data:
            assert q["fulfillment_rate"] == 100.0

    def test_get_quarterly_reports_by_quarter(self, client):
        """Test filtering quarterly reports by a quarter value."""
        data = client.get("/api/reports/quarterly?month=Q2-2025").json()

        assert [q["quarter"] for q in data] == ["Q2-2025"]

    def test_get_quarterly_reports_by_month(self, client):
        """Test that a single-month filter maps to its quarter."""
        orders = client.get("/api/orders?month=2025-05").json()
        data = client.get("/api/reports/quarterly?month=2025-05").json()

        assert len(data) == 1
        assert data[0]["quarter"] == "Q2-2025"
        assert data[0]["total_orders"] == len(orders)

    def test_get_quarterly_reports_no_matches(self, client):
        """Test that a filter with no matching orders returns an empty list."""
        response = client.get("/api/reports/quarterly?warehouse=Nowhere")
        assert response.status_code == 200
        assert response.json() == []


class TestMonthlyTrendEndpoints:
    """Test suite for the monthly trends endpoint."""

    def test_get_all_monthly_trends(self, client):
        """Test getting monthly trends without filters."""
        response = client.get("/api/reports/monthly-trends")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        for month in data:
            assert set(month.keys()) == {"month", "order_count", "revenue", "delivered_count"}
            assert isinstance(month["order_count"], int)
            assert isinstance(month["revenue"], (int, float))
            assert len(month["month"]) == 7  # YYYY-MM

    def test_monthly_trends_sorted(self, client):
        """Test that months are returned in chronological order."""
        data = client.get("/api/reports/monthly-trends").json()
        months = [m["month"] for m in data]
        assert months == sorted(months)

    def test_get_monthly_trends_multiple_filters(self, client):
        """Test monthly trends with warehouse, category and status filters."""
        query = "warehouse=San Francisco&category=sensors&status=shipped"
        orders = client.get(f"/api/orders?{query}").json()
        data = client.get(f"/api/reports/monthly-trends?{query}").json()

        assert sum(m["order_count"] for m in data) == len(orders)
        for m in data:
            assert m["delivered_count"] == 0

    def test_get_monthly_trends_by_month(self, client):
        """Test filtering monthly trends by a single month."""
        data = client.get("/api/reports/monthly-trends?month=2025-03").json()

        assert [m["month"] for m in data] == ["2025-03"]

    def test_get_monthly_trends_by_quarter(self, client):
        """Test filtering monthly trends by a quarter."""
        data = client.get("/api/reports/monthly-trends?month=Q4-2025").json()

        assert len(data) > 0
        for m in data:
            assert m["month"] in ["2025-10", "2025-11", "2025-12"]

    def test_monthly_and_quarterly_reports_consistent(self, client):
        """Test that monthly and quarterly revenue agree under the same filter."""
        query = "category=actuators"
        monthly = client.get(f"/api/reports/monthly-trends?{query}").json()
        quarterly = client.get(f"/api/reports/quarterly?{query}").json()

        assert sum(m["order_count"] for m in monthly) == sum(q["total_orders"] for q in quarterly)
        assert abs(sum(m["revenue"] for m in monthly) - sum(q["total_revenue"] for q in quarterly)) < 1
