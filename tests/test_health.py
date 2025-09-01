import os, sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))  # add project root

from app import app
from fastapi.testclient import TestClient


def test_health():
    c = TestClient(app)
    r = c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
