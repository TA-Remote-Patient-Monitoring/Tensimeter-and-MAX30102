from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from database import get_db
import models, schemas
from routers.auth import get_current_user, get_current_user_or_service
import os
import logging
import threading
from ml_model.predictor import predict_glucose, is_available as ml_is_available

from cache import (
    profile_owner_cache, profile_owner_cache_lock,
    latest_measurement_cache, latest_measurement_cache_lock,
    measurements_cache, measurements_cache_lock,
)

import pusher
import os
from dotenv import load_dotenv
load_dotenv()

pusher_client = pusher.Pusher(
  app_id=os.getenv("PUSHER_APP_ID", "local"),
  key=os.getenv("PUSHER_KEY", "local"),
  secret=os.getenv("PUSHER_SECRET", "local"),
  cluster=os.getenv("PUSHER_CLUSTER", "mt1"),
  ssl=True
)

def get_bp_status(sys: int, dia: int) -> str:
    if sys < 120 and dia < 80:
        return 'Normal'
    elif (120 <= sys < 140) or (80 <= dia < 90):
        return 'Normal Tinggi'
    else:
        return 'Hipertensi Tinggi'


router = APIRouter()
logger = logging.getLogger("measurements")

# ML model ter-load langsung di memory (tanpa perlu server terpisah)
if ml_is_available():
    logger.info("ML Predictor tersedia — prediksi gula darah aktif.")
else:
    logger.warning("ML Predictor tidak tersedia — prediksi gula darah nonaktif.")

# ─── ACTIVE SESSION (multiuser SpO2) ─────────────────────
# In-memory store: siapa yang sedang mengukur SpO2.
# Diset oleh Expo app saat user klik "Mau Prediksi Gula Darah?"
# Dipakai oleh ESP32 yang kirim data tanpa id_user/id_profile.
_active_session: Optional[dict] = None  # {"id_user": int, "id_profile": int}
_active_session_lock = threading.Lock()


def _check_profile_ownership(db: Session, id_profile: int, user_id: int, is_service: bool = False):
    """
    Validasi profile ownership dengan caching.
    Cache key: profile_id -> user_id. TTL 120 detik.
    Service call (is_service=True) → skip ownership check, hanya validasi profile exists.
    """
    # Service call → hanya cek apakah profile ada
    if is_service:
        profile = db.query(models.Profile).filter(models.Profile.id == id_profile).first()
        if not profile:
            raise HTTPException(status_code=404, detail="Profile tidak ditemukan.")
        return True

    with profile_owner_cache_lock:
        cached_owner = profile_owner_cache.get(id_profile)

    if cached_owner is not None:
        if cached_owner != user_id:
            raise HTTPException(status_code=403, detail="Tidak diizinkan melihat data profile user lain.")
        return True

    # Cache miss — query DB
    profile = db.query(models.Profile).filter(models.Profile.id == id_profile).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile tidak ditemukan.")
    if profile.id_user != user_id:
        raise HTTPException(status_code=403, detail="Tidak diizinkan melihat data profile user lain.")

    with profile_owner_cache_lock:
        profile_owner_cache[id_profile] = profile.id_user

    return True


def _serialize_measurement(record: models.Measurement) -> dict:
    """Konversi measurement ORM object ke dict untuk caching."""
    return {
        "id": record.id,
        "id_user": record.id_user,
        "id_profile": record.id_profile,
        "sys": record.sys,
        "dia": record.dia,
        "bpm": record.bpm,
        "ihb": record.ihb,
        "mov": record.mov,
        "datetime": record.datetime,
    }


@router.post("", response_model=schemas.MeasurementOut)
def save_measurement(
    data: schemas.MeasurementIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Simpan hasil pengukuran dari Flutter.
    Flutter mengirim data Omron + id_user + id_profile yang sudah dipilih.
    """
    if data.id_user != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Tidak diizinkan menyimpan data untuk user lain."
        )

    # Validasi profile milik user yang benar (cached)
    _check_profile_ownership(db, data.id_profile, current_user.id)

    record = models.Measurement(
        id_user    = current_user.id,
        id_profile = data.id_profile,
        sys        = data.sys,
        dia        = data.dia,
        bpm        = data.bpm,
        ihb        = bool(data.ihb),
        mov        = bool(data.mov),
        status     = get_bp_status(data.sys, data.dia),
        datetime   = data.datetime,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    
    # Broadcast event via Pusher
    try:
        pusher_client.trigger(
            f'patient.{data.id_profile}', 
            '.BloodPressureDataEvent', 
            {'id': record.id, 'sys': record.sys, 'dia': record.dia, 'bpm': record.bpm, 'status': record.status}
        )
    except Exception as e:
        logger.warning(f"Failed to trigger pusher event: {e}")

    # TIDAK invalidate cache — biarkan TTL yang handle (10-15 detik).
    return record


@router.get("/{id_profile}", response_model=List[schemas.MeasurementOut])
def get_measurements(
    id_profile: int,
    skip: int = Query(0, ge=0, description="Jumlah record yang di-skip (offset)"),
    limit: int = Query(50, ge=1, le=200, description="Maks record per halaman"),
    current_user=Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Ambil data pengukuran berdasarkan profile dengan pagination.
    Flutter pakai ini untuk tampilkan riwayat per profile.
    """
    is_service = getattr(current_user, 'is_service', False)
    # Validasi profile ownership (cached) — service call skip ownership
    _check_profile_ownership(db, id_profile, current_user.id, is_service=is_service)

    # Cache lookup — key: (profile_id, skip, limit)
    cache_key = (id_profile, skip, limit)
    with measurements_cache_lock:
        cached = measurements_cache.get(cache_key)
    if cached is not None:
        return cached

    # Service call → ambil semua data profile tanpa filter user
    query = db.query(models.Measurement)\
              .filter(models.Measurement.id_profile == id_profile)
    if not is_service:
        query = query.filter(models.Measurement.id_user == current_user.id)

    records = query.order_by(models.Measurement.datetime.desc())\
                   .offset(skip)\
                   .limit(limit)\
                   .all()
    if not records:
        raise HTTPException(status_code=404, detail="Belum ada data untuk profile ini.")

    result = [_serialize_measurement(r) for r in records]

    with measurements_cache_lock:
        measurements_cache[cache_key] = result

    return result


@router.get("/{id_profile}/latest", response_model=schemas.MeasurementOut)
def get_latest_measurement(
    id_profile: int,
    current_user=Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """Ambil pengukuran terbaru saja untuk ditampilkan di dashboard."""
    is_service = getattr(current_user, 'is_service', False)
    # Validasi profile ownership (cached)
    _check_profile_ownership(db, id_profile, current_user.id, is_service=is_service)

    # Cache lookup — TTL 15 detik
    with latest_measurement_cache_lock:
        cached = latest_measurement_cache.get(id_profile)
    if cached is not None:
        return cached

    query = db.query(models.Measurement)\
              .filter(models.Measurement.id_profile == id_profile)
    if not is_service:
        query = query.filter(models.Measurement.id_user == current_user.id)

    record = query.order_by(models.Measurement.datetime.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="Belum ada data untuk profile ini.")

    result = _serialize_measurement(record)

    with latest_measurement_cache_lock:
        latest_measurement_cache[id_profile] = result

    return result


# ─── ACTIVE SESSION ENDPOINTS ─────────────────────────────

@router.post("/spo2/active-session", response_model=schemas.ActiveSessionOut)
def set_active_session(
    data: schemas.ActiveSessionIn,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Expo app memanggil ini saat user klik "Mau Prediksi Gula Darah?".
    Menyimpan id_user + id_profile yang sedang aktif mengukur SpO2.
    ESP32 yang kirim data tanpa id_user/id_profile akan otomatis
    di-assign ke session ini.
    """
    global _active_session

    # Validasi: user hanya bisa set session untuk dirinya sendiri
    if data.id_user != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Tidak diizinkan mengatur session untuk user lain."
        )

    # Validasi profile ownership
    _check_profile_ownership(db, data.id_profile, current_user.id)

    with _active_session_lock:
        _active_session = {
            "id_user": data.id_user,
            "id_profile": data.id_profile,
        }

    logger.info("Active session diset: user=%d, profile=%d", data.id_user, data.id_profile)
    return schemas.ActiveSessionOut(
        message="Active session berhasil diset.",
        id_user=data.id_user,
        id_profile=data.id_profile,
    )


@router.get("/spo2/active-session", response_model=schemas.ActiveSessionOut)
def get_active_session():
    """Cek session yang sedang aktif (untuk debugging / ESP32)."""
    with _active_session_lock:
        session = _active_session

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Tidak ada session aktif. User harus klik 'Mau Prediksi Gula Darah?' di app terlebih dahulu."
        )

    return schemas.ActiveSessionOut(
        message="Session aktif ditemukan.",
        id_user=session["id_user"],
        id_profile=session["id_profile"],
    )


# ─── SPO2 MEASUREMENTS ───────────────────────────────────

@router.post("/spo2", response_model=schemas.Spo2MeasurementOut)
async def save_spo2_measurement(
    data: schemas.Spo2MeasurementIn,
    current_user=Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Simpan hasil pengukuran dari sensor SpO2 (MAX30102).

    Dua mode:
    1. ESP32 (X-Service-Key): kirim tanpa id_user/id_profile
       → otomatis ambil dari active session yang di-set oleh Expo app.
    2. Mobile app (Bearer JWT): kirim dengan id_user/id_profile.

    Sebelum disimpan, akan mengambil data Omron terakhir untuk prediksi gula darah.
    """
    global _active_session
    is_service = getattr(current_user, "is_service", False)

    # ── Resolve id_user & id_profile ──────────────────────
    if is_service and (data.id_user is None or data.id_profile is None):
        # ESP32 tanpa id_user/id_profile → ambil dari active session
        with _active_session_lock:
            session = _active_session

        if not session:
            raise HTTPException(
                status_code=400,
                detail="ESP32 mengirim tanpa id_user/id_profile dan tidak ada active session. "
                       "User harus klik 'Mau Prediksi Gula Darah?' di app terlebih dahulu."
            )

        effective_user_id = session["id_user"]
        effective_profile_id = session["id_profile"]
        logger.info(
            "ESP32 data resolved via active session: user=%d, profile=%d",
            effective_user_id, effective_profile_id
        )
    elif not is_service:
        # Mobile app → user harus kirim id_user/id_profile
        if data.id_user is None or data.id_profile is None:
            raise HTTPException(
                status_code=422,
                detail="id_user dan id_profile wajib diisi."
            )
        if data.id_user != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="Tidak diizinkan menyimpan data untuk user lain."
            )
        effective_user_id = current_user.id
        effective_profile_id = data.id_profile
    else:
        # Service call dengan id_user/id_profile eksplisit (backward compat)
        effective_user_id = data.id_user
        effective_profile_id = data.id_profile

    # 1. Validasi profile (cached)
    _check_profile_ownership(db, effective_profile_id, effective_user_id, is_service=is_service)

    # 2. Ambil data Omron terakhir
    omron_latest = db.query(models.Measurement).filter(
        models.Measurement.id_profile == effective_profile_id,
        models.Measurement.id_user == effective_user_id
    ).order_by(models.Measurement.datetime.desc()).first()

    if not omron_latest:
        raise HTTPException(
            status_code=400,
            detail="Harus mengukur tekanan darah (Omron) terlebih dahulu sebelum mengukur SpO2 untuk prediksi gula darah."
        )

    # 3. Ambil data profil untuk prediksi ML (gender, age, tinggi, berat)
    profile = db.query(models.Profile).filter(
        models.Profile.id == effective_profile_id
    ).first()

    # 4. Prediksi Gula Darah secara langsung (in-process, tanpa HTTP)
    predicted_glucose = None

    if ml_is_available() and profile:
        try:
            # SpO2 digunakan sebagai proxy ratio_r (R-value)
            # Rumus pendekatan: ratio_r ≈ (110 - spo2) / 25
            ratio_r = round((110.0 - data.spo2) / 25.0, 4) if data.spo2 > 0 else 0.5

            result = predict_glucose(
                gender    = profile.gender or "M",
                age       = profile.age or 30,
                height_cm = profile.tb or 170.0,
                weight_kg = profile.bb or 70.0,
                sbp       = float(omron_latest.sys),
                dbp       = float(omron_latest.dia),
                bpm       = float(data.bpm),
                ratio_r   = ratio_r,
            )

            if result:
                predicted_glucose = result["predicted_glucose_mg_dl"]
                logger.info(
                    "Prediksi gula darah: %.2f mg/dL (%s)",
                    predicted_glucose, result["glucose_category"]
                )
        except Exception as e:
            logger.warning("Gagal prediksi gula darah: %s", e)
    elif not ml_is_available():
        logger.warning("ML model tidak tersedia, skip prediksi gula darah.")

    # 4. Simpan ke database (tanpa refresh, expire_on_commit=False)
    record = models.Spo2Measurement(
        id_user    = effective_user_id,
        id_profile = effective_profile_id,
        spo2       = data.spo2,
        bpm        = data.bpm,
        temperature= data.temperature,
        blood_sugar= predicted_glucose,
        datetime   = data.datetime,
    )
    db.add(record)
    db.commit()

    # 5. Clear active session setelah data berhasil disimpan
    #    Mencegah data berikutnya masuk ke session yang salah
    if is_service:
        with _active_session_lock:
            _active_session = None
        logger.info("Active session di-clear setelah data SpO2 disimpan.")
    return record


@router.get("/{id_profile}/spo2", response_model=List[schemas.Spo2MeasurementOut])
def get_spo2_measurements(
    id_profile: int,
    skip: int = Query(0, ge=0, description="Jumlah record yang di-skip (offset)"),
    limit: int = Query(50, ge=1, le=200, description="Maks record per halaman"),
    current_user=Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """
    Ambil data pengukuran SpO2 berdasarkan profile dengan pagination.
    """
    is_service = getattr(current_user, 'is_service', False)
    # Validasi profile ownership (cached)
    _check_profile_ownership(db, id_profile, current_user.id, is_service=is_service)

    query = db.query(models.Spo2Measurement)\
              .filter(models.Spo2Measurement.id_profile == id_profile)
    if not is_service:
        query = query.filter(models.Spo2Measurement.id_user == current_user.id)

    records = query.order_by(models.Spo2Measurement.datetime.desc())\
                   .offset(skip)\
                   .limit(limit)\
                   .all()
    if not records:
        raise HTTPException(status_code=404, detail="Belum ada data SpO2 untuk profile ini.")
    return records


@router.get("/{id_profile}/spo2/latest", response_model=schemas.Spo2MeasurementOut)
def get_latest_spo2_measurement(
    id_profile: int,
    current_user=Depends(get_current_user_or_service),
    db: Session = Depends(get_db)
):
    """Ambil pengukuran SpO2 terbaru saja untuk ditampilkan di dashboard."""
    is_service = getattr(current_user, 'is_service', False)
    # Validasi profile ownership (cached)
    _check_profile_ownership(db, id_profile, current_user.id, is_service=is_service)

    query = db.query(models.Spo2Measurement)\
              .filter(models.Spo2Measurement.id_profile == id_profile)
    if not is_service:
        query = query.filter(models.Spo2Measurement.id_user == current_user.id)

    record = query.order_by(models.Spo2Measurement.datetime.desc()).first()
    if not record:
        raise HTTPException(status_code=404, detail="Belum ada data SpO2 untuk profile ini.")
    return record