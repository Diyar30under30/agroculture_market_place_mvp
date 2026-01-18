from __future__ import annotations

import hashlib
import secrets
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional
import os
from dotenv import load_dotenv
from io import BytesIO
from PIL import Image

from fastapi import FastAPI, HTTPException, Query, Request, Response, UploadFile, File
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

# Load environment variables from .env file
ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")
DB_PATH = ROOT_DIR / "app" / "data.db"
UPLOADS_DIR = ROOT_DIR / "app" / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

app = FastAPI(title="Marketplace API", version="0.1.0")
app.mount("/static", StaticFiles(directory=ROOT_DIR), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

HOME_PAGE = ROOT_DIR / "tolik.html"
PROFILE_PAGE = ROOT_DIR / "profile.html"
PRODUCTS_PAGE = ROOT_DIR / "products.html"
STORAGE_PAGE = ROOT_DIR / "storage.html"
ABOUT_PAGE = ROOT_DIR / "about.html"
ADMIN_PAGE = ROOT_DIR / "admin.html"

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
        ensure_column(conn, "profiles", "is_admin", "BOOLEAN DEFAULT 0")
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
        ensure_column(conn, "products", "photo_filename", "TEXT")
        
        # Set preloaded admin IDs from .env
        admin_ids_str = os.getenv("ADMIN_IDS", "").strip()
        if admin_ids_str:
            try:
                admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
                for admin_id in admin_ids:
                    conn.execute(
                        "UPDATE profiles SET is_admin = 1 WHERE id = ?",
                        (admin_id,),
                    )
            except (ValueError, AttributeError):
                pass  # Invalid ADMIN_IDS format, skip silently


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
    is_admin: bool = False


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
    photo_filename: Optional[str] = None


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


@app.get("/")
def home() -> FileResponse:
    if not HOME_PAGE.exists():
        raise HTTPException(status_code=404, detail="Home page not found")
    return FileResponse(HOME_PAGE)


@app.get("/profile")
def profile_page() -> FileResponse:
    if not PROFILE_PAGE.exists():
        raise HTTPException(status_code=404, detail="Profile page not found")
    return FileResponse(PROFILE_PAGE)


@app.get("/products")
def products_page() -> FileResponse:
    if not PRODUCTS_PAGE.exists():
        raise HTTPException(status_code=404, detail="Products page not found")
    return FileResponse(PRODUCTS_PAGE)


@app.get("/shop")
def shop_redirect() -> RedirectResponse:
    return RedirectResponse(url="/products")


@app.get("/storage")
def storage_page() -> FileResponse:
    if not STORAGE_PAGE.exists():
        raise HTTPException(status_code=404, detail="Storage page not found")
    return FileResponse(STORAGE_PAGE)


@app.get("/about")
def about_page() -> FileResponse:
    if not ABOUT_PAGE.exists():
        raise HTTPException(status_code=404, detail="About page not found")
    return FileResponse(ABOUT_PAGE)


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
            "SELECT id, name, email, phone, city, about, created_at, is_admin FROM profiles WHERE id = ?",
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
            SELECT id, name, email, phone, city, about, created_at, password_hash, is_admin
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
        is_admin=bool(row["is_admin"]),
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
            "SELECT id, name, email, phone, city, about, created_at, is_admin FROM profiles WHERE id = ?",
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
            "SELECT id, name, email, phone, city, about, created_at, is_admin FROM profiles WHERE id = ?",
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
            "SELECT id, name, email, phone, city, about, created_at, is_admin FROM profiles WHERE id = ?",
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
            INSERT INTO products (owner_id, title, description, price, currency, quantity, created_at, photo_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.owner_id,
                payload.title,
                payload.description,
                payload.price,
                payload.currency,
                payload.quantity,
                created_at,
                None,
            ),
        )
    return ProductOut(
        id=cursor.lastrowid,
        created_at=created_at,
        **payload.model_dump(),
        photo_filename=None,
    )


@app.post("/api/products/by-me", response_model=ProductOut)
def create_product_for_me(payload: ProductSelfCreate, request: Request) -> ProductOut:
    user_id = require_user_id(request)
    created_at = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        cursor = conn.execute(
            """
            INSERT INTO products (owner_id, title, description, price, currency, quantity, created_at, photo_filename)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                payload.title,
                payload.description,
                payload.price,
                payload.currency,
                payload.quantity,
                created_at,
                None,
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
        photo_filename=None,
    )


@app.get("/api/products", response_model=list[ProductOut])
def list_products(
    owner_id: Optional[int] = None,
    q: Optional[str] = Query(default=None, min_length=2, max_length=100),
) -> list[ProductOut]:
    query = "SELECT id, owner_id, title, description, price, currency, quantity, created_at, photo_filename FROM products"
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


@app.post("/api/products/{product_id}/upload-photo")
async def upload_product_photo(product_id: int, file: UploadFile = File(...)) -> dict:
    # Validate file type
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Only image files are allowed")
    
    # Read file contents
    contents = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB
    
    # Compress if larger than 5MB
    if len(contents) > max_size:
        try:
            # Open image and compress
            image = Image.open(BytesIO(contents))
            
            # Convert RGBA to RGB if needed (for JPEG compatibility)
            if image.mode in ("RGBA", "LA", "P"):
                rgb_image = Image.new("RGB", image.size, (255, 255, 255))
                rgb_image.paste(image, mask=image.split()[-1] if image.mode in ("RGBA", "LA") else None)
                image = rgb_image
            
            # Compress with decreasing quality until under 5MB
            quality = 95
            while quality > 10:
                output = BytesIO()
                image.save(output, format="JPEG", quality=quality, optimize=True)
                compressed_data = output.getvalue()
                
                if len(compressed_data) <= max_size:
                    contents = compressed_data
                    break
                
                quality -= 10
            
            # If still too large, resize image
            if len(contents) > max_size:
                scale = 0.9
                while len(contents) > max_size and scale > 0.3:
                    new_size = (int(image.width * scale), int(image.height * scale))
                    resized = image.resize(new_size, Image.Resampling.LANCZOS)
                    
                    output = BytesIO()
                    resized.save(output, format="JPEG", quality=85, optimize=True)
                    contents = output.getvalue()
                    
                    scale -= 0.1
        except Exception as e:
            # If compression fails, reject the file
            raise HTTPException(status_code=400, detail=f"Failed to compress image: {str(e)}")
    
    # Verify product exists
    with get_conn() as conn:
        product = conn.execute(
            "SELECT id FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
    
    # Generate filename with product_id and timestamp
    file_ext = "jpg" if len(contents) > max_size // 2 or file.content_type == "image/jpeg" else (file.filename.split(".")[-1] if "." in file.filename else "jpg")
    filename = f"product_{product_id}_{uuid.uuid4().hex}.{file_ext}"
    filepath = UPLOADS_DIR / filename
    
    # Save compressed file
    with open(filepath, "wb") as f:
        f.write(contents)
    
    # Update database
    with get_conn() as conn:
        conn.execute(
            "UPDATE products SET photo_filename = ? WHERE id = ?",
            (filename, product_id),
        )
    
    return {
        "filename": filename,
        "url": f"/uploads/{filename}",
    }

@app.get("/api/profiles/{profile_id}/products", response_model=list[ProductOut])
def list_products_by_profile(profile_id: int) -> list[ProductOut]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, owner_id, title, description, price, currency, quantity, created_at, photo_filename FROM products WHERE owner_id = ? ORDER BY created_at DESC",
            (profile_id,),
        ).fetchall()
    return [ProductOut(**dict(row)) for row in rows]


@app.delete("/api/products/{product_id}")
def delete_product(product_id: int, request: Request) -> dict:
    user_id = require_user_id(request)
    with get_conn() as conn:
        # Get product and check ownership/admin status
        product = conn.execute(
            "SELECT owner_id FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()
        
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        # Check if user is owner or admin
        user = conn.execute(
            "SELECT is_admin FROM profiles WHERE id = ?",
            (user_id,),
        ).fetchone()
        
        is_admin = bool(user and user["is_admin"])
        is_owner = product["owner_id"] == user_id
        
        if not (is_owner or is_admin):
            raise HTTPException(status_code=403, detail="Only owner or admin can delete this product")
        
        # Delete the product
        conn.execute("DELETE FROM products WHERE id = ?", (product_id,))
    
    return {"status": "deleted", "product_id": product_id}


@app.post("/api/profiles/{profile_id}/make-admin")
def make_admin(profile_id: int, request: Request) -> dict:
    user_id = require_user_id(request)
    
    # Only admins can promote other users
    with get_conn() as conn:
        current_user = conn.execute(
            "SELECT is_admin FROM profiles WHERE id = ?",
            (user_id,),
        ).fetchone()
        
        if not current_user or not current_user["is_admin"]:
            raise HTTPException(status_code=403, detail="Only admins can promote users")
        
        # Promote user to admin
        cursor = conn.execute(
            "UPDATE profiles SET is_admin = 1 WHERE id = ?",
            (profile_id,),
        )
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Profile not found")
    
    return {"status": "promoted", "profile_id": profile_id, "is_admin": True}


@app.get("/admin")
def admin_page() -> FileResponse:
    if not ADMIN_PAGE.exists():
        raise HTTPException(status_code=404, detail="Admin page not found")
    return FileResponse(ADMIN_PAGE)


@app.get("/api/admin/users", response_model=list[ProfileOut])
def admin_get_all_users(request: Request) -> list[ProfileOut]:
    user_id = require_user_id(request)
    
    # Check if user is admin
    with get_conn() as conn:
        current_user = conn.execute(
            "SELECT is_admin FROM profiles WHERE id = ?",
            (user_id,),
        ).fetchone()
        
        if not current_user or not current_user["is_admin"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get all users
        rows = conn.execute("SELECT * FROM profiles ORDER BY created_at DESC").fetchall()
        return [
            ProfileOut(
                id=row["id"],
                name=row["name"],
                email=row["email"],
                phone=row["phone"],
                city=row["city"],
                about=row["about"],
                created_at=row["created_at"],
                is_admin=bool(row["is_admin"]),
            )
            for row in rows
        ]


@app.get("/api/admin/products", response_model=list[ProductOut])
def admin_get_all_products(request: Request) -> list[ProductOut]:
    user_id = require_user_id(request)
    
    # Check if user is admin
    with get_conn() as conn:
        current_user = conn.execute(
            "SELECT is_admin FROM profiles WHERE id = ?",
            (user_id,),
        ).fetchone()
        
        if not current_user or not current_user["is_admin"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get all products
        rows = conn.execute("SELECT * FROM products ORDER BY created_at DESC").fetchall()
        return [
            ProductOut(
                id=row["id"],
                owner_id=row["owner_id"],
                title=row["title"],
                description=row["description"],
                price=row["price"],
                currency=row["currency"],
                quantity=row["quantity"],
                created_at=row["created_at"],
                email="",  # Dummy field for response model
                phone=None,
                city=None,
                about=None,
                name="",
                photo_filename=row["photo_filename"],
            )
            for row in rows
        ]


@app.delete("/api/admin/users/{user_id}")
def admin_delete_user(user_id: int, request: Request) -> dict:
    admin_user_id = require_user_id(request)
    
    # Check if requester is admin
    with get_conn() as conn:
        admin_check = conn.execute(
            "SELECT is_admin FROM profiles WHERE id = ?",
            (admin_user_id,),
        ).fetchone()
        
        if not admin_check or not admin_check["is_admin"]:
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Prevent self-deletion
        if user_id == admin_user_id:
            raise HTTPException(status_code=400, detail="Cannot delete your own account")
        
        # Delete user's products first
        conn.execute("DELETE FROM products WHERE owner_id = ?", (user_id,))
        
        # Delete user
        cursor = conn.execute("DELETE FROM profiles WHERE id = ?", (user_id,))
        
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="User not found")
    
    return {"status": "deleted", "user_id": user_id}
