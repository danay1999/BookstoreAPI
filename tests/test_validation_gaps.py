import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from fastapi.testclient import TestClient
from jose import jwt

import app as bookstore_app
from app import app


client = TestClient(app)


def _forged_admin_header() -> dict[str, str]:
    token = jwt.encode(
        {
            "sub": "mallory",
            "role": "admin",
            "exp": datetime.utcnow() + timedelta(minutes=30),
        },
        bookstore_app.JWT_SECRET,
        algorithm=bookstore_app.JWT_ALG,
    )
    return {"Authorization": f"Bearer {token}"}


def test_known_validation_gap_negative_price_is_accepted():
    response = client.post(
        "/books",
        headers=_forged_admin_header(),
        json={
            "title": "Validation Gap",
            "author": "Mallory",
            "price": -10.0,
            "popularity": -50,
        },
    )

    assert response.status_code == 200
    assert response.json()["price"] == -10.0
    assert response.json()["popularity"] == -50
