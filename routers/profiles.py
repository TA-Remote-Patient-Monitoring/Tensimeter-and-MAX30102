from fastapi import APIRouter, Depends, HTTPException
from fastapi import File, Form, UploadFile
from sqlalchemy.orm import Session
from typing import List
from pathlib import Path
import os
import uuid
from database import get_db
import models, schemas

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
def create_profile(
    id_user : int = Form(...),
    name    : str = Form(...),
    age     : int = Form(...),
    gender  : str = Form(...),
    tb      : float = Form(...),
    bb      : float = Form(...),
    image   : UploadFile | None = File(None),
    db      : Session = Depends(get_db)
):
    """Buat profile baru untuk user tertentu. Contoh: Ayah, Ibu, Anak."""
    user = db.query(models.User).filter(models.User.id == id_user).first()
    if not user:
        raise HTTPException(status_code=404, detail="User tidak ditemukan.")

    image_path = None
    if image and image.filename:
        suffix = Path(image.filename).suffix.lower()
        filename = f"profile_{uuid.uuid4().hex}{suffix}"
        file_path = UPLOAD_DIR / filename
        with file_path.open("wb") as buffer:
            buffer.write(image.file.read())
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
    db.refresh(profile)
    return profile_to_response(profile)


@router.get("/{id_user}", response_model=List[schemas.ProfileOut])
def get_profiles(id_user: int, db: Session = Depends(get_db)):
    """Ambil semua profile milik satu user (untuk ditampilkan di profile selector)."""
    profiles = db.query(models.Profile)\
                 .filter(models.Profile.id_user == id_user)\
                 .all()
    if not profiles:
        raise HTTPException(status_code=404, detail="Belum ada profile untuk user ini.")
    return [profile_to_response(profile) for profile in profiles]


@router.delete("/{id_profile}")
def delete_profile(id_profile: int, db: Session = Depends(get_db)):
    """Hapus profile berdasarkan id."""
    profile = db.query(models.Profile).filter(models.Profile.id == id_profile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile tidak ditemukan.")

    if profile.image_path and os.path.exists(profile.image_path):
        os.remove(profile.image_path)

    db.delete(profile)
    db.commit()
    return {"message": "Profile berhasil dihapus."}