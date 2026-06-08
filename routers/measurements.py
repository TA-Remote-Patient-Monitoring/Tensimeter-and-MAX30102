from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from database import get_db
import models, schemas
import os
import httpx

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


# ─── SPO2 MEASUREMENTS ───────────────────────────────────

@router.post("/spo2", response_model=schemas.Spo2MeasurementOut)
def save_spo2_measurement(data: schemas.Spo2MeasurementIn, db: Session = Depends(get_db)):
    """
    Simpan hasil pengukuran dari sensor SpO2 (MAX30102).
    ESP32/Flutter mengirim data SpO2 + temperature + bpm + id_user + id_profile.
    Sebelum disimpan, akan mengambil data Omron terakhir untuk prediksi gula darah.
    """
    # 1. Validasi profile milik user yang benar
    profile = db.query(models.Profile).filter(
        models.Profile.id      == data.id_profile,
        models.Profile.id_user == data.id_user
    ).first()
    if not profile:
        raise HTTPException(
            status_code=404,
            detail="Profile tidak ditemukan atau bukan milik user ini."
        )

    # 2. Ambil data Omron terakhir
    omron_latest = db.query(models.Measurement).filter(
        models.Measurement.id_profile == data.id_profile
    ).order_by(models.Measurement.datetime.desc()).first()

    if not omron_latest:
        raise HTTPException(
            status_code=400,
            detail="Harus mengukur tekanan darah (Omron) terlebih dahulu sebelum mengukur SpO2 untuk prediksi gula darah."
        )

    # 3. Prediksi Gula Darah ke ML API
    ml_api_url = os.getenv("ML_API_URL", "http://127.0.0.1:8001/predict")
    predicted_glucose = None

    try:
        payload = {
            "bpm": data.bpm,
            "spo2": data.spo2,
            "sys": omron_latest.sys,
            "dia": omron_latest.dia
        }
        # Hit ML API
        response = httpx.post(ml_api_url, json=payload, timeout=10.0)
        
        if response.status_code == 200:
            ml_data = response.json()
            predicted_glucose = ml_data.get("prediction", {}).get("glucose_mg_dl")
        else:
            print(f"ML API Error: {response.text}")
    except Exception as e:
        print(f"Gagal menghubungi ML API: {e}")

    # 4. Simpan ke database
    record = models.Spo2Measurement(
        id_user    = data.id_user,
        id_profile = data.id_profile,
        spo2       = data.spo2,
        bpm        = data.bpm,
        temperature= data.temperature,
        blood_sugar= predicted_glucose,
        datetime   = data.datetime,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{id_profile}/spo2", response_model=List[schemas.Spo2MeasurementOut])
def get_spo2_measurements(id_profile: int, db: Session = Depends(get_db)):
    """
    Ambil semua data pengukuran SpO2 berdasarkan profile.
    """
    records = db.query(models.Spo2Measurement)\
                .filter(models.Spo2Measurement.id_profile == id_profile)\
                .order_by(models.Spo2Measurement.datetime.desc())\
                .all()
    if not records:
        raise HTTPException(status_code=404, detail="Belum ada data SpO2 untuk profile ini.")
    return records


@router.get("/{id_profile}/spo2/latest", response_model=schemas.Spo2MeasurementOut)
def get_latest_spo2_measurement(id_profile: int, db: Session = Depends(get_db)):
    """Ambil pengukuran SpO2 terbaru saja untuk ditampilkan di dashboard."""
    record = db.query(models.Spo2Measurement)\
               .filter(models.Spo2Measurement.id_profile == id_profile)\
               .order_by(models.Spo2Measurement.datetime.desc())\
               .first()
    if not record:
        raise HTTPException(status_code=404, detail="Belum ada data SpO2 untuk profile ini.")
    return record