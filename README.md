# BookstoreAPI Secure SDLC Lab

BookstoreAPI is a compact FastAPI application used as a portfolio lab for practical application security work. The goal is to show an end-to-end Secure SDLC workflow: find issues, prove impact, wire security checks into CI, remediate, and document the before/after results.

## Security Story

This repo is intentionally small so the security work is easy to inspect. It currently demonstrates:

- FastAPI API routes with authentication and admin-only write operations.
- JWT-based authorization with deliberately weak default configuration.
- SQLite persistence for local development.
- Rate limiting on login and book routes.
- GitHub Actions checks for tests, Bandit, and Semgrep.
- A written security review with findings, exploit notes, and remediation guidance.

## Current API Surface

- `GET /health`
- `POST /auth/token`
- `GET /books`
- `POST /books`
- `GET /books/{book_id}`
- `PATCH /books/{book_id}`
- `DELETE /books/{book_id}`

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app:app --reload --port 8000
```

Open the Swagger UI at:

```text
http://localhost:8000/docs
```

## Run Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Some tests intentionally document vulnerable behavior. Those tests are evidence for the security review and should be flipped during the remediation phase.

## Current Security Findings

See `SECURITY_REVIEW.md` for details. The highest-priority findings are:

- Default JWT secret allows forged admin tokens.
- Demo credentials are hardcoded and weak.
- JWT validation trusts role claims directly and lacks issuer/audience checks.
- Security gates exist, but Bandit is currently non-blocking.
- Input validation is thin for book data.

## Portfolio Roadmap

1. Keep the vulnerable baseline and document exploit evidence.
2. Add tests that prove auth, authorization, and validation behavior.
3. Add or tune CI security scans: Semgrep, Bandit, secret scanning, Trivy, and DAST.
4. Remediate the findings in a separate pass.
5. Capture before/after test and scan output.
6. Add a threat model and architecture diagram.
7. Write a short project walkthrough suitable for Product Security interviews.
