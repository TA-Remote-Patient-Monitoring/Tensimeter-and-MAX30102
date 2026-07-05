from fastapi import APIRouter, Depends, HTTPException
from fastapi import File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import os
import uuid
import aiofiles
from database import get_db
import models, schemas
from routers.auth import get_current_user, get_current_user_or_service
from cache import (
    profile_cache, profile_cache_lock,
    invalidate_profile_cache, invalidate_profile_owner,
)

router = APIRouter()

UPLOAD_DIR = Path(os.path.dirname(os.path.dirname(__file__))) / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def profile_to_response(profile: models.Profile) -> dict:
    image_url = None
    if profile.image_path:
        image_url = f"/uploads/{Path(profile.image_path).name}"
    return {
        "id": profile.id,
        "id_user": profile.id_user,
        "name": profile.name,
        "age": profile.age,
        "gender": profile.gender,
        "tb": profile.tb,
        "bb": profile.bb,
        "image_url": image_url,
    }


@router.post("", response_model=schemas.ProfileOut)
async def create_profile(
    id_user : int = Form(...),
    name    : str = Form(...),
    age     : int = Form(...),
    gender  : str = Form(...),
    tb      : float = Form(...),
    bb      : float = Form(...),
    image   : UploadFile | None = File(None),
    current_user: models.User = Depends(get_current_user),
    db      : Session = Depends(get_db)
):
    """Buat profile baru untuk user tertentu. Contoh: Ayah, Ibu, Anak."""
    if id_user != current_user.id:
        raise HTTPException(status_code=403, detail="Tidak diizinkan membuat profile untuk user lain.")

    user = db.query(models.User).filter(models.User.id == id_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    image_path = None
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        filename = f"profile_{uuid.uuid4().hex}{suffix}"
        file_path = UPLOAD_DIR / filename
        # Async file write — tidak memblokir event loop
        content = await image.read()
        async with aiofiles.open(file_path, "wb") as buffer:
            await buffer.write(content)
        image_path = str(file_path)

    profile = models.Profile(
        id_user = id_user,
        name    = name,
        age     = age,
        gender  = gender,
        tb      = tb,
        bb      = bb,
        image_path = image_path,
    )
    db.add(profile)
    db.commit()
    # Tanpa db.refresh() — expire_on_commit=False membuat atribut tetap accessible

    # Invalidate profile cache untuk user ini
    invalidate_profile_cache(id_user)

    return profile_to_response(profile)


@router.get("/search", response_model=None)
def search_user_by_phone(
    phone: str,
    current_user = Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """Cari user berdasarkan nomor telepon — dipakai oleh dashboard dokter untuk assign pasien."""
    user = db.query(models.User).filter(models.User.phone == phone).first()
    if not user:
        raise HTTPException(status_code=404, detail="User dengan nomor tersebut tidak ditemukan.")

    profiles = db.query(models.Profile)\
                 .filter(models.Profile.id_user == user.id)\
                 .all()

    return {
        "id_user": user.id,
        "name": user.name,
        "phone": user.phone,
        "profiles": [profile_to_response(p) for p in profiles],
    }


@router.get("/{id_user}", response_model=List[schemas.ProfileOut])
def get_profiles(
    id_user: int,
    current_user = Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """Ambil semua profile milik satu user (untuk ditampilkan di profile selector)."""
    # Service call (dashboard dokter) → skip ownership check
    if not getattr(current_user, 'is_service', False):
        if id_user != current_user.id:
            raise HTTPException(status_code=403, detail="Tidak diizinkan melihat profile user lain.")

    # Cache lookup — profile jarang berubah, TTL 60 detik
    with profile_cache_lock:
        cached = profile_cache.get(id_user)
    if cached is not None:
        return cached

    profiles = db.query(models.Profile)\
                 .filter(models.Profile.id_user == id_user)\
                 .all()
    if not profiles:
        raise HTTPException(status_code=404, detail="Belum ada profile untuk user ini.")

    result = [profile_to_response(profile) for profile in profiles]

    # Simpan ke cache
    with profile_cache_lock:
        profile_cache[id_user] = result

    return result


@router.delete("/{id_profile}")
def delete_profile(
    id_profile: int,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Hapus profile berdasarkan id."""
    profile = db.query(models.Profile).filter(models.Profile.id == id_profile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile tidak ditemukan.")

    if profile.id_user != current_user.id:
        raise HTTPException(status_code=403, detail="Tidak diizinkan menghapus profile user lain.")

    user_id = profile.id_user

    if profile.image_path and os.path.exists(profile.image_path):
        os.remove(profile.image_path)

    db.delete(profile)
    db.commit()

    # Invalidate caches
    invalidate_profile_cache(user_id)
    invalidate_profile_owner(id_profile)

    return {"message": "Profile berhasil dihapus."}