from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime, timedelta
import pytz

from database import get_db
from models import Profile, Measurement, Spo2Measurement

router = APIRouter()

@router.get("/patients")
def get_all_patients(page: int = 1, db: Session = Depends(get_db)):
    per_page = 10
    skip = (page - 1) * per_page
    
    total = db.query(Profile).count()
    profiles = db.query(Profile).order_by(Profile.id.desc()).offset(skip).limit(per_page).all()
    
    data = []
    for p in profiles:
        latest_meas = db.query(Measurement).filter(Measurement.id_profile == p.id).order_by(Measurement.datetime.desc()).first()
        data.append({
            "id": p.id,
            "uuid": p.uuid,
            "first_name": p.first_name or p.name,
            "last_name": p.last_name or "",
            "phone_number": p.phone_number,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "healthData": [{
                "patient_id": p.id,
                "sys": latest_meas.sys if latest_meas else None,
                "dia": latest_meas.dia if latest_meas else None,
                "status": latest_meas.status if latest_meas else None,
                "created_at": latest_meas.datetime.isoformat() if latest_meas else None
            }] if latest_meas else []
        })
    
    return {
        "success": True,
        "patients": {
            "current_page": page,
            "data": data,
            "total": total,
            "per_page": per_page
        }
    }


@router.get("/patients/summary/status")
def get_patient_status(db: Session = Depends(get_db)):
    total_patient = db.query(Profile).count()
    
    # Get latest measurement for each profile
    subq = db.query(
        Measurement.id_profile, 
        func.max(Measurement.datetime).label("max_date")
    ).group_by(Measurement.id_profile).subquery()
    
    latest_measurements = db.query(Measurement).join(
        subq, 
        (Measurement.id_profile == subq.c.id_profile) & (Measurement.datetime == subq.c.max_date)
    ).all()
    
    normal_patients = sum(1 for m in latest_measurements if m.status == 'Normal')
    hyper_patients = sum(1 for m in latest_measurements if m.status == 'Hipertensi Tinggi')
    
    today = datetime.utcnow().date()
    checked_today = 0
    for p in db.query(Profile).all():
        has_today = db.query(Measurement).filter(
            Measurement.id_profile == p.id,
            func.date(Measurement.datetime) == today
        ).first()
        if has_today:
            checked_today += 1
            
    not_checked_today = total_patient - checked_today
    
    return {
        "success": True,
        "total_patient": total_patient,
        "normal_patient": normal_patients,
        "hyper_patient": hyper_patients,
        "not_checked_today": not_checked_today,
        "checked_today": checked_today
    }


@router.get("/patients/recent")
def recent_patients(db: Session = Depends(get_db)):
    subq = db.query(
        Measurement.id_profile, 
        func.max(Measurement.datetime).label("max_date")
    ).group_by(Measurement.id_profile).subquery()
    
    # Sort by the most recent measurement
    recent_profiles_measurements = db.query(Measurement).join(
        subq, 
        (Measurement.id_profile == subq.c.id_profile) & (Measurement.datetime == subq.c.max_date)
    ).order_by(Measurement.datetime.desc()).limit(5).all()
    
    recent_patients = []
    for m in recent_profiles_measurements:
        p = m.profile
        recent_patients.append({
            "id": p.id,
            "uuid": p.uuid,
            "first_name": p.first_name or p.name,
            "last_name": p.last_name or "",
            "lastBP": f"{m.sys}/{m.dia}",
            "status": m.status,
            "lastVisit": m.datetime.isoformat()
        })
        
    return {
        "success": True,
        "recent_patients": recent_patients
    }


@router.get("/patients/statistics/distribution")
def distribution_bp_status(db: Session = Depends(get_db)):
    # This requires returning 5 weeks of data
    data = []
    today = datetime.utcnow().date()
    
    for i in range(4, -1, -1):
        # Calculate start and end of week (Monday to Sunday)
        target_date = today - timedelta(weeks=i)
        start_of_week = target_date - timedelta(days=target_date.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        
        # Get profiles that have measurements in this week
        measurements_in_week = db.query(Measurement).filter(
            func.date(Measurement.datetime) >= start_of_week,
            func.date(Measurement.datetime) <= end_of_week
        ).all()
        
        # Count by status
        normal = len(set([m.id_profile for m in measurements_in_week if m.status == 'Normal']))
        prehyper = len(set([m.id_profile for m in measurements_in_week if m.status == 'Normal Tinggi']))
        hyper = len(set([m.id_profile for m in measurements_in_week if m.status == 'Hipertensi Tinggi']))
        
        data.append({
            "date": start_of_week.strftime("%d %b"),
            "normal": normal,
            "Normal Tinggi": prehyper,
            "Hipertensi Tinggi": hyper
        })
        
    return {
        "success": True,
        "data": data
    }


@router.get("/patients/{uuid_or_id}")
def get_patient_by_uuid(uuid_or_id: str, page: int = 1, db: Session = Depends(get_db)):
    patient = db.query(Profile).filter(Profile.uuid == uuid_or_id).first()
    if not patient:
        patient = db.query(Profile).filter(Profile.id == uuid_or_id).first()
        
    if not patient:
        raise HTTPException(status_code=404, detail="Pasien not found")
        
    per_page = 5
    skip = (page - 1) * per_page
    
    measurements = db.query(Measurement).filter(Measurement.id_profile == patient.id)\
                     .order_by(Measurement.datetime.desc()).offset(skip).limit(per_page).all()
                     
    total_meas = db.query(Measurement).filter(Measurement.id_profile == patient.id).count()
    
    formatted_health_data = []
    for m in measurements:
        formatted_health_data.append({
            "id": m.id,
            "patient_id": patient.id,
            "sys": m.sys,
            "dia": m.dia,
            "bpm": m.bpm,
            "mov": m.mov,
            "ihb": m.ihb,
            "status": m.status,
            "device": m.device,
            "created_at": m.datetime.isoformat()
        })
        
    latest_meas = formatted_health_data[0] if formatted_health_data else None
        
    return {
        "success": True,
        "patient_data": {
            "id": patient.id,
            "uuid": patient.uuid,
            "first_name": patient.first_name or patient.name,
            "last_name": patient.last_name or "",
            "phone_number": patient.phone_number,
            "date_of_birth": patient.date_of_birth,
            "gender": patient.gender,
            "address": patient.address,
            "height": patient.tb,
            "weight": patient.bb,
            "created_at": patient.created_at.isoformat() if patient.created_at else None
        },
        "health_data": {
            "current_page": page,
            "data": formatted_health_data,
            "total": total_meas,
            "per_page": per_page
        },
        "lastVisit": latest_meas["created_at"] if latest_meas else "-"
    }


@router.get("/patients/{id_profile}/blood-pressures")
def get_patient_blood_pressures(id_profile: int, db: Session = Depends(get_db)):
    measurements = db.query(Measurement).filter(Measurement.id_profile == id_profile).order_by(Measurement.datetime.asc()).all()
    data = []
    for m in measurements:
        data.append({
            "date": m.datetime.strftime("%Y-%m-%d"),
            "systolic": m.sys,
            "diastolic": m.dia
        })
    return data


@router.get("/patients/{id_profile}/vital-signs")
def get_patient_vital_signs(id_profile: int, db: Session = Depends(get_db)):
    vitals = db.query(Spo2Measurement).filter(Spo2Measurement.id_profile == id_profile).order_by(Spo2Measurement.datetime.asc()).all()
    data = []
    for v in vitals:
        data.append({
            "date": v.datetime.strftime("%Y-%m-%d"),
            "bpm": v.bpm,
            "spo2": v.spo2
        })
    return data
