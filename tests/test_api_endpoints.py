"""Tests for the FastAPI adapter endpoints."""

import pytest
from starlette.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_api_status(client):
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "total_applicants" in data
    assert "total_programs" in data
    assert data["total_applicants"] > 0
    assert data["total_programs"] > 0


def test_api_programs(client):
    res = client.get("/api/programs")
    assert res.status_code == 200
    data = res.json()
    assert "programs" in data
    assert len(data["programs"]) > 0


def test_api_applicants(client):
    res = client.get("/api/applicants")
    assert res.status_code == 200
    data = res.json()
    assert "applicants" in data
    assert len(data["applicants"]) > 0


def test_api_validation(client):
    res = client.get("/api/validation")
    assert res.status_code == 200
    data = res.json()
    assert "is_valid" in data
    assert "errors" in data
    assert "warnings" in data


def test_api_undo_status(client):
    res = client.get("/api/undo/status")
    assert res.status_code == 200
    data = res.json()
    assert "can_undo" in data
    assert "undo_count" in data


def test_api_solve_allocation(client):
    res = client.post("/api/allocation/solve", json={
        "config": {
            "priority_mode": "lexicographic",
            "time_limit_seconds": 5.0,
            "only_assign_preferred": True,
        },
        "scenario_type": "initial",
        "scenario_description": "Test solve",
    })
    assert res.status_code == 200
    data = res.json()
    assert "result" in data
    result = data["result"]
    assert result["solver_status"] in ["Optimal", "Feasible, not proven optimal"]
    assert result["total_assigned"] > 0

