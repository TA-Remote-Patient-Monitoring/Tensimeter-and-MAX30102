"""
Glucose Prediction v6 — in-process predictor.

Modul ini memuat model ML (Random Forest) dan menyediakan fungsi
`predict_glucose()` yang bisa dipanggil langsung dari endpoint FastAPI
tanpa perlu HTTP call ke server terpisah.

Berdasarkan: Prediksi-gula-darah/ml backend final/api_server.py
"""

import os
import logging
import numpy as np
import pandas as pd
import joblib

logger = logging.getLogger("ml_predictor")

# ── Load model artifacts saat modul di-import ─────────────────
_BASE_DIR = os.path.dirname(__file__)
_model_path = os.path.join(_BASE_DIR, "model_v6.joblib")
_scaler_path = os.path.join(_BASE_DIR, "scaler_v6.joblib")
_metadata_path = os.path.join(_BASE_DIR, "metadata_v6.joblib")

_model = None
_scaler = None
_metadata = None

if os.path.exists(_model_path) and os.path.exists(_scaler_path) and os.path.exists(_metadata_path):
    _model = joblib.load(_model_path)
    _scaler = joblib.load(_scaler_path)
    _metadata = joblib.load(_metadata_path)
    logger.info(
        "ML Model Loaded: %s (train=%d, R2=%.4f, MAE=%.2f)",
        _metadata["model_name"],
        _metadata["train_samples"],
        _metadata["r2_cv_mean"],
        _metadata["mae_cv_mean"],
    )
else:
    logger.warning(
        "ML model files tidak ditemukan di %s. Prediksi gula darah tidak tersedia.", _BASE_DIR
    )


def is_available() -> bool:
    """Cek apakah model sudah ter-load dan siap digunakan."""
    return _model is not None


def predict_glucose(
    gender: str,
    age: int,
    height_cm: float,
    weight_kg: float,
    sbp: float,
    dbp: float,
    bpm: float,
    ratio_r: float,
    ac_red: float = None,
    dc_red: float = None,
    ac_ir: float = None,
    dc_ir: float = None,
) -> dict:
    """
    Prediksi kadar gula darah berdasarkan data pasien.

    Returns:
        dict dengan keys:
        - predicted_glucose_mg_dl (float)
        - glucose_category (str)
        - risk_level (str)
        - cardiovascular_analysis (dict)
        Atau None jika model belum ter-load.
    """
    if _model is None:
        return None

    # 1. Process Gender
    gender_str = gender.strip().upper()
    if gender_str in ("M", "MALE", "L", "LAKI-LAKI", "LAKI"):
        gender_male = 1
    else:
        gender_male = 0

    # 2. Impute optional raw PPG signals menggunakan dataset means
    means = _metadata["feature_means"]
    imputed_fields = []

    if ac_red is None:
        ac_red = means["AC_Red"]
        imputed_fields.append("ac_red")
    if dc_red is None:
        dc_red = means["DC_Red"]
        imputed_fields.append("dc_red")
    if ac_ir is None:
        ac_ir = means["AC_IR"]
        imputed_fields.append("ac_ir")
    if dc_ir is None:
        dc_ir = means["DC_IR"]
        imputed_fields.append("dc_ir")

    # 3. Construct input vector (exact training order)
    input_vector = np.array([[
        gender_male, age, height_cm, weight_kg,
        sbp, dbp, bpm, ratio_r,
        ac_red, dc_red, ac_ir, dc_ir
    ]])

    # 4. Scale and Predict
    input_df = pd.DataFrame(input_vector, columns=_metadata["features"])
    input_scaled = _scaler.transform(input_df)
    predicted_val = _model.predict(input_scaled)[0]

    # Clip ke rentang fisiologis (50–300 mg/dL)
    predicted_val = float(np.clip(predicted_val, 50.0, 300.0))

    # 5. Klasifikasi ADA
    if predicted_val < 70.0:
        category, risk = "Hypoglycemia (Rendah)", "TINGGI"
    elif predicted_val <= 99.0:
        category, risk = "Normal", "RENDAH"
    elif predicted_val <= 125.0:
        category, risk = "Prediabetes (IFG)", "SEDANG"
    elif predicted_val <= 199.0:
        category, risk = "Diabetes", "TINGGI"
    else:
        category, risk = "Diabetes Berat", "KRITIS"

    # 6. Analisis kardiovaskular tambahan
    bmi = weight_kg / ((height_cm / 100.0) ** 2)
    if bmi < 18.5:
        bmi_cat = "Underweight"
    elif bmi < 25.0:
        bmi_cat = "Normal"
    elif bmi < 30.0:
        bmi_cat = "Overweight"
    else:
        bmi_cat = "Obese"

    pulse_pressure = sbp - dbp
    map_val = dbp + (pulse_pressure / 3.0)

    if sbp < 120 and dbp < 80:
        bp_cat = "Normal"
    elif 120 <= sbp < 130 and dbp < 80:
        bp_cat = "Elevated"
    elif (130 <= sbp < 140) or (80 <= dbp < 90):
        bp_cat = "Hypertension Stage 1"
    else:
        bp_cat = "Hypertension Stage 2"

    rpp = bpm * sbp
    if rpp < 10000:
        rpp_cat = "Normal (Rendah)"
    elif rpp <= 12000:
        rpp_cat = "Normal (Aktif)"
    else:
        rpp_cat = "Tinggi (Stres Miokardial)"

    return {
        "predicted_glucose_mg_dl": round(predicted_val, 2),
        "glucose_category": category,
        "risk_level": risk,
        "imputed_fields": imputed_fields,
        "cardiovascular_analysis": {
            "bmi": round(bmi, 2),
            "bmi_category": bmi_cat,
            "pulse_pressure_mmHg": round(pulse_pressure, 2),
            "mean_arterial_pressure_mmHg": round(map_val, 2),
            "bp_category": bp_cat,
            "rate_pressure_product_bpm_mmHg": int(rpp),
            "rpp_category": rpp_cat,
        },
    }
