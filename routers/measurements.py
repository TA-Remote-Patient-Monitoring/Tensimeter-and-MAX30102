from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas

router = APIRouter()


@router.post("", response_model=schemas.MeasurementOut)
def save_measurement(data: schemas.MeasurementIn, db: Session = Depends(get_db)):
    """
    Simpan hasil pengukuran dari Flutter.
    Flutter mengirim data Omron + id_user + id_profile yang sudah dipilih.
    """
    # Validasi profile milik user yang benar
    profile = db.query(models.Profile).filter(
        models.Profile.id      == data.id_profile,
        models.Profile.id_user == data.id_user
    ).first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile tidak ditemukan atau bukan milik user ini."
        )

    record = models.Measurement(
        id_user    = data.id_user,
        id_profile = data.id_profile,
        sys        = data.sys,
        dia        = data.dia,
        bpm        = data.bpm,
        ihb        = bool(data.ihb),
        mov        = bool(data.mov),
        datetime   = data.datetime,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{id_profile}", response_model=List[schemas.MeasurementOut])
def get_measurements(id_profile: int, db: Session = Depends(get_db)):
    """
    Ambil semua data pengukuran berdasarkan profile.
    Flutter pakai ini untuk tampilkan riwayat per profile.
    """
    records = db.query(models.Measurement)\
                .filter(models.Measurement.id_profile == id_profile)\
                .order_by(models.Measurement.datetime.desc())\
                .all()
    if not records:
        raise HTTPException(status_code=404, detail="Belum ada data untuk profile ini.")
    return records


@router.get("/{id_profile}/latest", response_model=schemas.MeasurementOut)
def get_latest_measurement(id_profile: int, db: Session = Depends(get_db)):
    """Ambil pengukuran terbaru saja untuk ditampilkan di dashboard."""
    record = db.query(models.Measurement)\
               .filter(models.Measurement.id_profile == id_profile)\
               .order_by(models.Measurement.datetime.desc())\
               .first()
    if not record:
        raise HTTPException(status_code=404, detail="Belum ada data untuk profile ini.")
    return record