"""
Tests for task API endpoints used by the My Tasks modal.
"""
import pytest

import main


@pytest.fixture(autouse=True)
def reset_tasks():
    """Keep the in-memory task store isolated between tests."""
    main.tasks.clear()
    yield
    main.tasks.clear()


def create(client, title="Review stock", priority="high", due_date="2025-10-08"):
    return client.post("/api/tasks", json={"title": title, "priority": priority, "dueDate": due_date})


class TestTaskEndpoints:
    """Test suite for task-related endpoints."""

    def test_get_all_tasks_empty(self, client):
        """Test getting tasks when none exist."""
        response = client.get("/api/tasks")
        assert response.status_code == 200
        assert response.json() == []

    def test_create_task(self, client):
        """Test creating a task."""
        response = create(client)
        assert response.status_code == 201

        task = response.json()
        assert set(task.keys()) == {"id", "title", "priority", "dueDate", "status"}
        assert task["title"] == "Review stock"
        assert task["priority"] == "high"
        assert task["dueDate"] == "2025-10-08"
        assert task["status"] == "pending"
        assert isinstance(task["id"], str)

    def test_created_tasks_listed_newest_first(self, client):
        """Test that new tasks appear at the start of the list."""
        first = create(client, title="First").json()
        second = create(client, title="Second").json()

        data = client.get("/api/tasks").json()
        assert [t["id"] for t in data] == [second["id"], first["id"]]
        assert first["id"] != second["id"]

    def test_create_task_trims_title(self, client):
        """Test that the title is stored without surrounding whitespace."""
        task = create(client, title="  Approve order  ").json()
        assert task["title"] == "Approve order"

    @pytest.mark.parametrize("payload", [
        {"title": "", "priority": "high", "dueDate": "2025-10-08"},
        {"title": "   ", "priority": "high", "dueDate": "2025-10-08"},
        {"title": "Task", "priority": "urgent", "dueDate": "2025-10-08"},
        {"title": "Task", "priority": "low", "dueDate": "10/08/2025"},
        {"title": "Task", "priority": "low"},
    ])
    def test_create_task_invalid_payload(self, client, payload):
        """Test that invalid task payloads are rejected."""
        response = client.post("/api/tasks", json=payload)
        assert response.status_code == 422

    def test_toggle_task(self, client):
        """Test toggling a task to completed and back."""
        task_id = create(client).json()["id"]

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        response = client.patch(f"/api/tasks/{task_id}")
        assert response.json()["status"] == "pending"

    def test_toggle_nonexistent_task(self, client):
        """Test toggling a task that doesn't exist."""
        response = client.patch("/api/tasks/nonexistent-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_delete_task(self, client):
        """Test deleting a task."""
        task_id = create(client).json()["id"]

        response = client.delete(f"/api/tasks/{task_id}")
        assert response.status_code == 200
        assert client.get("/api/tasks").json() == []

    def test_delete_nonexistent_task(self, client):
        """Test deleting a task that doesn't exist."""
        response = client.delete("/api/tasks/nonexistent-999")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
