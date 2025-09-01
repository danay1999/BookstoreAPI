import os

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Body, Header, Query, Request
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, Session
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

# --- Settings ---
JWT_SECRET = os.getenv("JWT_SECRET", "change-me-in-secrets")
JWT_ALG = "HS256"
ACCESS_TOKEN_MINUTES = 60
MAX_BODY = 1 * 1024 * 1024


async def _limit_body_mw(request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_BODY:
        raise HTTPException(status_code=413, detail="Payload too large")
    return await call_next(request)


# --- App/DB bootstrap ---
app = FastAPI(title="Bookstore API", version="0.1")
engine = create_engine(
    "sqlite:///./bookstore.db", connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
Base = declarative_base()
limiter = Limiter(key_func=get_remote_address, default_limits=["60/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(BaseHTTPMiddleware, dispatch=_limit_body_mw)

# --- Auth plumbing (demo users) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
DEMO_USERS = {
    # username: (hashed_password, role)
    "admin": (pwd_context.hash("password"), "admin"),
    "user": (pwd_context.hash("password"), "user"),
}


def create_access_token(sub: str, role: str) -> str:
    payload = {
        "sub": sub,
        "role": role,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class AuthUser(BaseModel):
    username: str
    role: str


def get_current_user(authorization: str = Header(...)) -> AuthUser:
    # Expect "Bearer <token>"
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise ValueError
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return AuthUser(username=payload["sub"], role=payload["role"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_admin(user: AuthUser = Depends(get_current_user)) -> AuthUser:
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return user


# --- Models ---
class Book(Base):
    __tablename__ = "books"
    id = Column(Integer, primary_key=True)
    title = Column(String(200), nullable=False)
    author = Column(String(120), nullable=False)
    genre = Column(String(80))
    price = Column(Float, nullable=False, default=0)
    popularity = Column(Integer, nullable=False, default=0)
    isbn = Column(String(32))
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


Base.metadata.create_all(bind=engine)


# --- Schemas ---
class LoginIn(BaseModel):
    username: str
    password: str


class BookIn(BaseModel):
    title: str
    author: str
    genre: Optional[str] = None
    price: float
    isbn: Optional[str] = None
    popularity: int = 0


class BookPatch(BaseModel):
    title: Optional[str] = None
    author: Optional[str] = None
    genre: Optional[str] = None
    price: Optional[float] = None
    isbn: Optional[str] = None
    popularity: Optional[int] = None


class BookOut(BookIn):
    id: int
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


# --- Routes ---
@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/auth/token", response_model=TokenOut)
@limiter.limit("5/minute")
def login_json(creds: LoginIn, request: Request):
    rec = DEMO_USERS.get(creds.username)
    if not rec or not pwd_context.verify(creds.password, rec[0]):
        raise HTTPException(status_code=401, detail="Bad credentials")
    token = create_access_token(creds.username, rec[1])
    return {"access_token": token}


# GET /books (search + filters + cursor pagination)
@app.get("/books", response_model=List[BookOut])
@limiter.limit("60/minute")
def list_books(
    request: Request,
    db: Session = Depends(get_db),
    search: Optional[str] = Query(None),
    genre: Optional[str] = None,
    author: Optional[str] = None,
    sort: str = Query("popularity"),
    limit: int = Query(20, ge=1, le=100),
    cursor: Optional[int] = None,
):
    if sort not in {"popularity", "price", "title"}:
        raise HTTPException(400, "invalid sort")
    q = db.query(Book)
    if search:
        like = f"%{search}%"
        q = q.filter((Book.title.like(like)) | (Book.author.like(like)))
    if genre:
        q = q.filter(Book.genre == genre)
    if author:
        q = q.filter(Book.author == author)
    # simple cursor: id > cursor
    if cursor:
        q = q.filter(Book.id > cursor)
    # ordering
    if sort == "popularity":
        q = q.order_by(Book.popularity.desc(), Book.id.asc())
    elif sort == "price":
        q = q.order_by(Book.price.asc(), Book.id.asc())
    else:
        q = q.order_by(Book.title.asc(), Book.id.asc())
    items = q.limit(limit).all()
    return items


@app.post("/books", response_model=BookOut)
@limiter.limit("10/minute")
def create_book(
    request: Request,
    data: BookIn,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    book = Book(**data.model_dump())
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


@app.get("/books/{book_id}", response_model=BookOut)
@limiter.limit("10/minute")
def get_book(request: Request, book_id: int, db: Session = Depends(get_db)):
    book = db.query(Book).get(book_id)
    if not book:
        raise HTTPException(404, "not found")
    return book


@app.patch("/books/{book_id}", response_model=BookOut)
@limiter.limit("10/minute")
def patch_book(
    request: Request,
    book_id: int,
    data: BookPatch,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    book = db.query(Book).get(book_id)
    if not book:
        raise HTTPException(404, "not found")

    updates = data.model_dump(exclude_unset=True, exclude_none=True)
    if not updates:
        return book  # nothing to change

    for k, v in updates.items():
        setattr(book, k, v)

    db.commit()
    db.refresh(book)
    return book


@app.delete("/books/{book_id}", status_code=204)
def delete_book(
    request: Request,
    book_id: int,
    db: Session = Depends(get_db),
    _: AuthUser = Depends(require_admin),
):
    book = db.query(Book).get(book_id)
    if not book:
        raise HTTPException(404, "not found")
    db.delete(book)
    db.commit()
    return
