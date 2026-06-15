import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from jose import jwt

import app as bookstore_app
from app import app


client = TestClient(app)


def _login(username: str, password: str) -> str:
    response = client.post(
        "/auth/token",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_admin_write_route_requires_authentication():
    response = client.post(
        "/books",
        json={"title": "Secure APIs", "author": "Dana", "price": 25.0},
    )

    assert response.status_code == 422


def test_user_role_cannot_create_books():
    token = _login("user", "password")

    response = client.post(
        "/books",
        headers=_auth_header(token),
        json={"title": "Secure APIs", "author": "Dana", "price": 25.0},
    )

    assert response.status_code == 403


def test_known_vulnerability_default_secret_allows_forged_admin_token():
    forged_token = jwt.encode(
        {
            "sub": "mallory",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        },
        bookstore_app.JWT_SECRET,
        algorithm=bookstore_app.JWT_ALG,
    )

    response = client.post(
        "/books",
        headers=_auth_header(forged_token),
        json={
            "title": "Forged Admin Token",
            "author": "Mallory",
            "price": 0.01,
        },
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Forged Admin Token"
