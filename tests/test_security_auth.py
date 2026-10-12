import os
import sys
from datetime import datetime, timedelta, timezone

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


def _forge(claims: dict, secret: str) -> str:
    claims = {"exp": datetime.now(timezone.utc) + timedelta(minutes=30), **claims}
    return jwt.encode(claims, secret, algorithm=bookstore_app.JWT_ALG)


NEW_BOOK = {"title": "Forged Admin Token", "author": "Mallory", "price": 0.01}


def test_token_signed_with_old_default_secret_is_rejected():
    token = _forge(
        {"sub": "admin", "iss": bookstore_app.JWT_ISSUER, "aud": bookstore_app.JWT_AUDIENCE},
        "change-me-in-secrets",
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 401


def test_role_claim_in_token_is_ignored():
    # Even with the real secret, a regular user cannot promote themselves.
    token = _forge(
        {
            "sub": "user",
            "role": "admin",
            "iss": bookstore_app.JWT_ISSUER,
            "aud": bookstore_app.JWT_AUDIENCE,
        },
        bookstore_app.JWT_SECRET,
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 403


def test_token_for_unknown_user_is_rejected():
    token = _forge(
        {"sub": "mallory", "iss": bookstore_app.JWT_ISSUER, "aud": bookstore_app.JWT_AUDIENCE},
        bookstore_app.JWT_SECRET,
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 401


def test_token_for_another_audience_is_rejected():
    token = _forge(
        {"sub": "admin", "iss": bookstore_app.JWT_ISSUER, "aud": "some-other-service"},
        bookstore_app.JWT_SECRET,
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 401


def test_token_from_another_issuer_is_rejected():
    token = _forge(
        {"sub": "admin", "iss": "some-other-issuer", "aud": bookstore_app.JWT_AUDIENCE},
        bookstore_app.JWT_SECRET,
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 401


def test_expired_token_is_rejected():
    token = _forge(
        {
            "sub": "admin",
            "iss": bookstore_app.JWT_ISSUER,
            "aud": bookstore_app.JWT_AUDIENCE,
            "exp": datetime.now(timezone.utc) - timedelta(minutes=1),
        },
        bookstore_app.JWT_SECRET,
    )

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 401


def test_real_admin_login_can_still_create_books():
    token = _login("admin", "password")

    response = client.post("/books", headers=_auth_header(token), json=NEW_BOOK)

    assert response.status_code == 200
