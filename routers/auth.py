import fastapi
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from database import get_db
import models, schemas
from passlib.context import CryptContext
from jose import jwt, JWTError
import asyncio
import concurrent.futures
import datetime
import os
from dotenv import load_dotenv

from cache import (
    user_cache, user_cache_lock,
    user_by_id_cache, user_by_id_cache_lock,
)

router = APIRouter()

load_dotenv()
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY belum diset di environment.")
ALGORITHM  = "HS256"

# Bcrypt rounds dikontrol via env var:
# - Development/testing: BCRYPT_ROUNDS=4 (~6ms per hash, cukup untuk stress test)
# - Production: BCRYPT_ROUNDS=10 (~100ms per hash, aman untuk brute force)
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "4"))
pwd_ctx    = CryptContext(
    schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS
)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# Dedicated thread pool untuk operasi bcrypt CPU-bound.
_bcrypt_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=32,
    thread_name_prefix="bcrypt",
)


class CachedUser:
    """
    Lightweight user representation untuk caching.
    Menghindari SQLAlchemy DetachedInstanceError karena tidak terikat session.
    """
    __slots__ = ("id", "name", "email", "phone", "password")

    def __init__(self, user):
        self.id = user.id
        self.name = user.name
        self.email = user.email
        self.phone = user.phone
        self.password = user.password


def _hash_password_sync(pw: str) -> str:
    return pwd_ctx.hash(pw)


def _verify_password_sync(pw: str, hashed: str) -> bool:
    return pwd_ctx.verify(pw, hashed)


async def hash_password(pw: str) -> str:
    """Offload CPU-bound bcrypt hashing ke dedicated thread pool (32 workers)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_bcrypt_executor, _hash_password_sync, pw)


async def verify_password(pw: str, hashed: str) -> bool:
    """Offload CPU-bound bcrypt verification ke dedicated thread pool (32 workers)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_bcrypt_executor, _verify_password_sync, pw, hashed)


def create_token(id_user: int) -> str:
    payload = {
        "sub"  : str(id_user),
        "exp"  : datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token tidak valid atau sudah kedaluwarsa.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        id_user = payload.get("sub")
        if id_user is None:
            raise credentials_exception
        user_id_int = int(id_user)
    except (JWTError, ValueError):
        raise credentials_exception

    # Cache user by ID — hindari DB query berulang untuk JWT verification
    # Menggunakan CachedUser (plain object) bukan ORM object untuk menghindari
    # DetachedInstanceError saat session asli sudah ditutup.
    with user_by_id_cache_lock:
        cached_user = user_by_id_cache.get(user_id_int)
    if cached_user is not None:
        return cached_user

    user = db.query(models.User).filter(models.User.id == user_id_int).first()
    if not user:
        raise credentials_exception

    cached = CachedUser(user)
    with user_by_id_cache_lock:
        user_by_id_cache[user_id_int] = cached

    return cached


# ── Service Token Auth (server-to-server) ──────────────────────
SERVICE_KEY = os.getenv("SERVICE_KEY")


class ServiceUser:
    """
    Representasi khusus untuk service call (dashboard dokter).
    is_service=True → downstream skip ownership check.
    """
    __slots__ = ("id", "name", "email", "phone", "is_service")

    def __init__(self):
        self.id = None
        self.name = "ServiceAccount"
        self.email = None
        self.phone = None
        self.is_service = True


# OAuth2 scheme yang tidak auto-error jika tidak ada Bearer token
_oauth2_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


def get_current_user_or_service(
    token: str | None = Depends(_oauth2_optional),
    db: Session = Depends(get_db),
    x_service_key: str | None = fastapi.Header(None, alias="X-Service-Key"),
):
    """
    Dependency yang mendukung 2 mode autentikasi:
      1. X-Service-Key header → return ServiceUser (untuk dashboard dokter)
      2. Bearer JWT token     → return CachedUser  (untuk mobile app)
    """
    # Mode 1: Service key dari dashboard
    if x_service_key and SERVICE_KEY and x_service_key == SERVICE_KEY:
        return ServiceUser()

    # Mode 2: JWT token biasa (mobile app)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah kedaluwarsa.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_current_user(token=token, db=db)


@router.post("/register")
async def register(data: schemas.RegisterIn, db: Session = Depends(get_db)):
    # Cek apakah email sudah terdaftar
    existing_email = db.query(models.User).filter(models.User.email == data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email sudah terdaftar.")
    
    # Cek apakah nomor HP sudah terdaftar
    existing_phone = db.query(models.User).filter(models.User.phone == data.phone).first()
    if existing_phone:
        raise HTTPException(status_code=400, detail="Nomor HP sudah terdaftar.")

    user = models.User(
        name     = data.name,
        email    = data.email,
        phone    = data.phone,
        password = await hash_password(data.password),
    )
    db.add(user)
    db.commit()
    # Tanpa db.refresh() — expire_on_commit=False membuat atribut tetap accessible
    return {"message": "Registrasi berhasil.", "id_user": user.id}


@router.post("/login", response_model=schemas.LoginOut)
async def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    # Validasi bahwa minimal salah satu dari email atau phone disediakan
    if not data.email and not data.phone:
        raise HTTPException(status_code=400, detail="Email atau nomor HP harus diisi.")
    
    # Cache lookup — hindari DB query untuk user yang sama
    # Menyimpan CachedUser (plain object), bukan ORM object
    cache_key = data.email or data.phone
    with user_cache_lock:
        cached = user_cache.get(cache_key)

    if cached is not None:
        # Cache hit — gunakan password dari CachedUser untuk verifikasi
        if not await verify_password(data.password, cached.password):
            raise HTTPException(status_code=401, detail="Email/nomor HP atau password salah.")
        return {
            "id_user" : cached.id,
            "name"    : cached.name,
            "email"   : cached.email,
            "token"   : create_token(cached.id),
        }

    # Cache miss — query DB
    user = None
    if data.email:
        user = db.query(models.User).filter(models.User.email == data.email).first()
    elif data.phone:
        user = db.query(models.User).filter(models.User.phone == data.phone).first()

    if not user or not await verify_password(data.password, user.password):
        raise HTTPException(status_code=401, detail="Email/nomor HP atau password salah.")

    # Simpan ke cache sebagai CachedUser (plain object)
    cached = CachedUser(user)
    with user_cache_lock:
        user_cache[cache_key] = cached

    return {
        "id_user" : user.id,
        "name"    : user.name,
        "email"   : user.email,
        "token"   : create_token(user.id),
    }