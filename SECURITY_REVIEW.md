# BookstoreAPI Security Review

Review date: 2026-06-14

## Application Structure

BookstoreAPI is a compact FastAPI service implemented primarily in `app.py`.

- `app.py`: FastAPI app, SQLite bootstrap, SQLAlchemy model, Pydantic schemas, auth helpers, rate limiting, and book routes.
- `requirements.txt`: pinned runtime dependencies.
- `.Dockerfile`: Python 3.12 slim container image that runs Uvicorn on port 8080.
- `.github/workflows/ci.yml`: GitHub Actions workflow for pytest, Bandit, and Semgrep.
- `tests/test_health.py`: single health-check test.
- `http files/BookstoreAPI.http`: manual request collection for local API testing.
- `k6/`: smoke and spike load scripts.

The API surface is small:

- `GET /health`
- `POST /auth/token`
- `GET /books`
- `POST /books`
- `GET /books/{book_id}`
- `PATCH /books/{book_id}`
- `DELETE /books/{book_id}`

## Current Security Posture

### Strengths

- Admin-only write routes exist for create, update, and delete operations.
- User-supplied search and filter input is passed through SQLAlchemy query builders, avoiding obvious string-built SQL injection.
- Login is rate-limited to `5/minute`; list and write routes have endpoint-level limits.
- Request body size is capped using a middleware that rejects large `Content-Length` values.
- Passwords are hashed with bcrypt in the demo user store.
- CI runs pytest, Bandit, and Semgrep.
- Dependencies are pinned for core runtime packages.

### High-Priority Findings

1. Default JWT secret allows token forgery.

   `JWT_SECRET` defaults to `change-me-in-secrets` when the environment variable is not set. With that known secret, an attacker can mint an admin token and call admin-only routes.

   Evidence:

   ```text
   forged admin create 200
   ```

   The test used `python-jose` to create a token with `{"sub":"mallory","role":"admin"}` signed using the default secret. The API accepted it.

   Recommended remediation:

   - Fail startup if `JWT_SECRET` is missing or still set to a known demo value outside a deliberate local-demo mode.
   - Use a long random secret stored in a secret manager or environment-specific secret store.
   - Add a regression test that forged tokens with the demo secret fail in non-demo mode.

2. Demo credentials are hardcoded and weak.

   `admin/password` and `user/password` are available in source and the HTTP sample file. This is acceptable only for a deliberately vulnerable lab mode.

   Recommended remediation:

   - Move users to a persistent user store or dedicated seed script.
   - Disable demo accounts by default.
   - Document demo credentials only in a lab README, not as production behavior.

3. JWT validation trusts role claims directly.

   Authorization depends on the `role` value inside the JWT. If signing is compromised, role escalation is immediate.

   Recommended remediation:

   - Include standard claims such as `iss`, `aud`, `iat`, `exp`, and `jti`.
   - Require expected issuer and audience during decode.
   - Consider loading user role from trusted server-side state for sensitive actions.
   - Add tests for missing/invalid role, missing expiration, wrong issuer, wrong audience, and expired token.

4. CI security gates are not currently blocking.

   Bandit is configured as `bandit -r app.py || true`, so findings do not fail CI.

   Recommended remediation:

   - Keep non-blocking mode during early learning if desired, but document it.
   - For the remediation phase, remove `|| true` or use a severity threshold policy.

### Medium-Priority Findings

1. Input validation is thin.

   The API does not constrain book title, author, genre, ISBN length, minimum price, or popularity range at the Pydantic schema layer. SQLAlchemy column lengths exist, but they are not a complete API validation strategy.

   Recommended remediation:

   - Use Pydantic `Field` constraints such as `min_length`, `max_length`, `ge`, and `le`.
   - Reject negative prices and unreasonable popularity values.
   - Add tests for invalid create and patch payloads.

2. Request body limit can be bypassed by clients that omit `Content-Length`.

   The middleware checks only the `Content-Length` header. Chunked or streaming requests without that header may not be constrained by this code path.

   Recommended remediation:

   - Rely on reverse proxy/server request limits for production.
   - Keep the app-level check as a secondary guard.
   - Add deployment notes for Nginx, Azure App Service, or container ingress limits.

3. SQLite local file database is fine for a demo, not production.

   The app uses `sqlite:///./bookstore.db` and creates tables at import time.

   Recommended remediation:

   - Move database URL into configuration.
   - Use migrations instead of `Base.metadata.create_all`.
   - Use a production database for deployed environments.

4. Security test coverage is minimal.

   Current tests only assert that `/health` returns `200`.

   Recommended remediation:

   - Add tests for authentication success/failure.
   - Add tests for admin-only route enforcement.
   - Add tests for token tampering and expired tokens.
   - Add tests for validation boundaries.

### Lower-Priority Observations

- `Body` and `relationship` imports are unused.
- `Query` constraints are used for `limit`, which is good, but `cursor` could also use `ge=1`.
- `db.query(Book).get(book_id)` is legacy SQLAlchemy style; prefer `db.get(Book, book_id)`.
- The Dockerfile runs as root by default. For a production-hardening pass, add a non-root user.
- The app does not configure CORS, which is safer by default unless browser clients need cross-origin access.

## Verification Performed

Commands run locally:

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m bandit -r app.py
```

Results:

- Pytest: `1 passed, 1 warning`
- Bandit: `No issues identified`

Targeted behavior checks:

```text
health 200
list unauth 200
create no auth 422
login bad 401
login user 200
create user role 403
forged admin create 200
```

The forged admin token behavior is the most important current finding.

## Burp Suite Exploration Plan

Use this only against your local instance.

1. Run the API locally.

   ```powershell
   cd C:\git\app-sec-ready\BookstoreAPI
   .venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
   ```

2. Open Burp Suite and use the embedded browser.

   Visit:

   ```text
   http://localhost:8000/docs
   ```

3. Capture baseline traffic.

   Exercise:

   - `GET /health`
   - `GET /books`
   - `POST /auth/token`
   - `POST /books`
   - `PATCH /books/{book_id}`
   - `DELETE /books/{book_id}`

4. Test authentication boundaries.

   - Send `POST /books` without `Authorization`.
   - Send `POST /books` with a malformed bearer token.
   - Log in as `user/password` and replay admin actions.
   - Log in as `admin/password` and confirm admin actions succeed.

5. Test JWT weaknesses.

   - Decode a valid token in Burp Decoder or jwt.io.
   - Change the role from `user` to `admin` without resigning and verify it fails.
   - Re-sign a modified token with the default secret `change-me-in-secrets` and verify it succeeds.
   - Remove or alter `exp` and observe server behavior.

6. Test input validation.

   Try payloads such as:

   ```json
   {"title":"","author":"","price":-1,"popularity":-999}
   ```

   ```json
   {"title":"A very long title repeated many times","author":"A","price":1}
   ```

7. Test rate limiting.

   Use Burp Intruder against `POST /auth/token` with repeated bad passwords and confirm `429` behavior after the configured limit.

8. Document findings.

   For each issue, capture:

   - Request
   - Response
   - Impact
   - Root cause
   - Remediation
   - Before/after evidence after a fix

## Suggested Vulnerability List For The Portfolio Lab

- Weak/default JWT secret leading to admin token forgery.
- Hardcoded demo credentials.
- Missing issuer/audience/strict JWT claim validation.
- Insufficient input validation for book data.
- Non-blocking security gates in CI.
- Production hardening gaps in Docker and database configuration.

