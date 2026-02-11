"""
Integration tests for the FastAPI webhook endpoint.
v1.1: Added flashcard action, dashboard endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """TestClient as context manager fires lifespan → init_db + start_worker."""
    with TestClient(app) as c:
        yield c


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "1.1" in data["version"]
        assert "flashcards" in data["features"]
        assert "notes_integration" in data["features"]
        assert "versioning" in data["features"]


class TestWebhook:
    def test_valid_checklist(self, client):
        resp = client.post("/webhook/notion", json={
            "task_page_id": "abc123", "action_type": "checklist", "secret": "test-secret"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "queued"

    def test_valid_flashcards(self, client):
        resp = client.post("/webhook/notion", json={
            "task_page_id": "abc456", "action_type": "flashcards", "secret": "test-secret"})
        assert resp.status_code == 200
        assert "job_id" in resp.json()

    def test_invalid_secret(self, client):
        resp = client.post("/webhook/notion", json={
            "task_page_id": "abc", "action_type": "checklist", "secret": "wrong"})
        assert resp.status_code == 401

    def test_invalid_action(self, client):
        resp = client.post("/webhook/notion", json={
            "task_page_id": "abc", "action_type": "invalid", "secret": "test-secret"})
        assert resp.status_code == 422

    def test_all_five_actions(self, client):
        for action in ["checklist", "tree", "pages", "flashcards", "approve"]:
            resp = client.post("/webhook/notion", json={
                "task_page_id": f"task_{action}_test", "action_type": action, "secret": "test-secret"})
            assert resp.status_code == 200, f"Failed for {action}"


class TestJobEndpoint:
    def test_not_found(self, client):
        resp = client.get("/jobs/nonexistent")
        assert resp.status_code == 404

    def test_created_via_webhook(self, client):
        resp = client.post("/webhook/notion", json={
            "task_page_id": "test789_fc", "action_type": "flashcards", "secret": "test-secret"})
        job_id = resp.json()["job_id"]
        resp2 = client.get(f"/jobs/{job_id}")
        assert resp2.status_code == 200
        assert resp2.json()["action_type"] == "flashcards"


class TestDashboard:
    def test_stats(self, client):
        resp = client.get("/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_tasks" in data
        assert "runs" in data
        assert "tokens" in data
        assert "outputs" in data

    def test_runs(self, client):
        resp = client.get("/dashboard/runs")
        assert resp.status_code == 200
        assert "runs" in resp.json()

    def test_runs_limit(self, client):
        resp = client.get("/dashboard/runs?limit=5")
        assert resp.status_code == 200

    def test_versions(self, client):
        resp = client.get("/dashboard/versions/some-task-id")
        assert resp.status_code == 200
        data = resp.json()
        assert "versions" in data
        assert "checklist" in data["versions"]
        assert "flashcards" in data["versions"]
