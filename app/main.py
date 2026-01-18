from __future__ import annotations

import hashlib
import secrets
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field


ROOT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = ROOT_DIR / "app" / "data.db"

app = FastAPI(title="Marketplace API", version="0.1.0")

FRONTEND_DIR = ROOT_DIR / "frontend"

# Раздаём только фронт как статику (а не весь проект)
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


SESSION_COOKIE = "session_id"
SESSIONS: dict[str, int] = {}


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def ensure_column(conn: sqlite3.Connection, table: str, column: str, col_def: str) -> None:
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")


def init_db() -> None:
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS profiles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                phone TEXT,
                city TEXT,
                about TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        ensure_column(conn, "profiles", "password_hash", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(owner_id) REFERENCES profiles(id)
            )
            """
        )


@app.on_event("startup")
def on_startup() -> None:
    init_db()


class ProfileCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    phone: Optional[str] = Field(default=None, max_length=50)
    city: Optional[str] = Field(default=None, max_length=100)
    about: Optional[str] = Field(default=None, max_length=500)


class ProfileOut(ProfileCreate):
    id: int
    created_at: str


class ProfileUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = Field(default=None, max_length=50)
    city: Optional[str] = Field(default=None, max_length=100)
    about: Optional[str] = Field(default=None, max_length=500)


class ProductCreate(BaseModel):
    owner_id: int
    title: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: float = Field(..., gt=0)
    currency: str = Field(default="KZT", min_length=3, max_length=3)
    quantity: int = Field(default=1, ge=1, le=10_000)


class ProductSelfCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=150)
    description: Optional[str] = Field(default=None, max_length=1000)
    price: float = Field(..., gt=0)
    currency: str = Field(default="KZT", min_length=3, max_length=3)
    quantity: int = Field(default=1, ge=1, le=10_000)


class ProductOut(ProductCreate):
    id: int
    created_at: str


class RegisterPayload(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


class LoginPayload(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=100)


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def get_session_user_id(request: Request) -> Optional[int]:
    session_id = request.cookies.get(SESSION_COOKIE)
    if not session_id:
        return None
    return SESSIONS.get(session_id)


def require_user_id(request: Request) -> int:
    user_id = get_session_user_id(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Login required")
    return user_id


def issue_session(response: Response, user_id: int) -> None:
    session_id = secrets.token_hex(16)
    SESSIONS[session_id] = user_id
    response.set_cookie(
        key=SESSION_COOKIE,
        value=session_id,
        httponly=True,
        samesite="lax",
    )


def clear_session(request: Request, response: Response) -> None:
    session_id = request.cookies.get(SESSION_COOKIE)
    if session_id and session_id in SESSIONS:
        del SESSIONS[session_id]
    response.delete_cookie(SESSION_COOKIE)


@app.get("/health")
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


"""@app.get("/")
def home() -> FileResponse:
    if not HOME_PAGE.exists():
        raise HTTPException(status_code=404, detail="Home page not found")
    return FileResponse(HOME_PAGE)
"""



"""@app.get("/profile")
def profile_page() -> FileResponse:
    if not PROFILE_PAGE.exists():
        raise HTTPException(status_code=404, detail="Profile page not found")
    return FileResponse(PROFILE_PAGE)
"""

"""@app.get("/products")
def products_page() -> FileResponse:
    if not PRODUCTS_PAGE.exists():
        raise HTTPException(status_code=404, detail="Products page not found")
    return FileResponse(PRODUCTS_PAGE)
""""


"""@app.get("/shop")
def shop_redirect() -> RedirectResponse:
    return RedirectResponse(url="/products")
"""


@app.post("/api/auth/register", response_model=ProfileOut)
def register(payload: RegisterPayload, response: Response) -> ProfileOut:
    created_at = datetime.now(timezone.utc).isoformat()
    password_hash = hash_password(payload.password)
    with get_conn() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO profiles (name, email, password_hash, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.email,
                    password_hash,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists")
        row = conn.execute(
            "SELECT id, name, email, phone, city, about, created_at FROM profiles WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    issue_session(response, row["id"])
    return ProfileOut(**dict(row))


@app.post("/api/auth/login", response_model=ProfileOut)
def login(payload: LoginPayload, response: Response) -> ProfileOut:
    password_hash = hash_password(payload.password)
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT id, name, email, phone, city, about, created_at, password_hash
            FROM profiles
            WHERE email = ?
            """,
            (payload.email,),
        ).fetchone()
    if not row or row["password_hash"] != password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    issue_session(response, row["id"])
    return ProfileOut(
        id=row["id"],
        name=row["name"],
        email=row["email"],
        phone=row["phone"],
        city=row["city"],
        about=row["about"],
        created_at=row["created_at"],
    )


@app.post("/api/auth/logout")
def logout(request: Request, response: Response) -> dict:
    clear_session(request, response)
    return {"status": "ok"}


@app.get("/api/me", response_model=ProfileOut)
def get_me(request: Request) -> ProfileOut:
    user_id = require_user_id(request)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, city, about, created_at FROM profiles WHERE id = ?",
            (user_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileOut(**dict(row))


@app.post("/api/profiles", response_model=ProfileOut)
def create_profile(payload: ProfileCreate) -> ProfileOut:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        try:
            cursor = conn.execute(
                """
                INSERT INTO profiles (name, email, phone, city, about, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    payload.name,
                    payload.email,
                    payload.phone,
                    payload.city,
                    payload.about,
                    created_at,
                ),
            )
        except sqlite3.IntegrityError:
            raise HTTPException(status_code=409, detail="Email already exists")
    return ProfileOut(
        id=cursor.lastrowid,
        created_at=created_at,
        **payload.model_dump(),
    )


@app.get("/api/profiles/{profile_id}", response_model=ProfileOut)
def get_profile(profile_id: int) -> ProfileOut:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id, name, email, phone, city, about, created_at FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Profile not found")
    return ProfileOut(**dict(row))


@app.patch("/api/profiles/{profile_id}", response_model=ProfileOut)
def update_profile(profile_id: int, payload: ProfileUpdate) -> ProfileOut:
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{key} = ?" for key in updates)
    values = list(updates.values()) + [profile_id]

    with get_conn() as conn:
        cursor = conn.execute(
            f"UPDATE profiles SET {set_clause} WHERE id = ?",
            values,
        )
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Profile not found")
        row = conn.execute(
            "SELECT id, name, email, phone, city, about, created_at FROM profiles WHERE id = ?",
            (profile_id,),
        ).fetchone()
    return ProfileOut(**dict(row))


@app.post("/api/products", response_model=ProductOut)
def create_product(payload: ProductCreate) -> ProductOut:
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        owner = conn.execute(
            "SELECT id FROM profiles WHERE id = ?",
            (payload.owner_id,),
        ).fetchone()
        if not owner:
            raise HTTPException(status_code=404, detail="Owner profile not found")
        cursor = conn.execute(
            """
            INSERT INTO products (owner_id, title, description, price, currency, quantity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.owner_id,
                payload.title,
                payload.description,
                payload.price,
                payload.currency,
                payload.quantity,
                created_at,
            ),
        )
    return ProductOut(
        id=cursor.lastrowid,
        created_at=created_at,
        **payload.model_dump(),
    )


@app.post("/api/products/by-me", response_model=ProductOut)
def create_product_for_me(payload: ProductSelfCreate, request: Request) -> ProductOut:
    user_id = require_user_id(request)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products (owner_id, title, description, price, currency, quantity, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload.title,
                payload.description,
                payload.price,
                payload.currency,
                payload.quantity,
                created_at,
            ),
        )
    return ProductOut(
        id=cursor.lastrowid,
        created_at=created_at,
        owner_id=user_id,
        title=payload.title,
        description=payload.description,
        price=payload.price,
        currency=payload.currency,
        quantity=payload.quantity,
    )


@app.get("/api/products", response_model=list[ProductOut])
def list_products(
    owner_id: Optional[int] = None,
    q: Optional[str] = Query(default=None, min_length=2, max_length=100),
) -> list[ProductOut]:
    query = "SELECT * FROM products"
    params: list[object] = []

    if owner_id is not None and q:
        query += " WHERE owner_id = ? AND title LIKE ?"
        params.extend([owner_id, f"%{q}%"])
    elif owner_id is not None:
        query += " WHERE owner_id = ?"
        params.append(owner_id)
    elif q:
        query += " WHERE title LIKE ?"
        params.append(f"%{q}%")

    query += " ORDER BY created_at DESC"

    with get_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [ProductOut(**dict(row)) for row in rows]


@app.get("/api/profiles/{profile_id}/products", response_model=list[ProductOut])
def list_products_by_profile(profile_id: int) -> list[ProductOut]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM products WHERE owner_id = ? ORDER BY created_at DESC",
            (profile_id,),
        ).fetchall()
    return [ProductOut(**dict(row)) for row in rows]
