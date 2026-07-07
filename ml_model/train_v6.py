import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold, cross_validate
import joblib
import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

# Paths
csv_path = "Hb_PPG_processed_dataset.csv"
model_path = "model_v6.joblib"
scaler_path = "scaler_v6.joblib"
metadata_path = "metadata_v6.joblib"

print("="*60)
print("             TRAINING BACKEND API V6 MODEL")
print("="*60)

# 1. Load dataset
if not os.path.exists(csv_path):
    print(f"Error: {csv_path} not found!")
    sys.exit(1)

print(f"Loading dataset: {csv_path}...")
df = pd.read_csv(csv_path)
print(f"Original shape: {df.shape}")

# 2. Clean data (coerce all object columns to float and drop NaNs)
for col in df.columns:
    if df[col].dtype == 'object':
        df[col] = pd.to_numeric(df[col], errors='coerce')

df_clean = df.dropna()
print(f"Cleaned shape (after dropping NaNs/missing values): {df_clean.shape}")
print(f"Dropped {len(df) - len(df_clean)} rows containing invalid data.")

# 3. Features and target definition
features = ['Gender_Male', 'Age', 'Height_cm', 'Weight_kg', 'SBP', 'DBP', 'BPM', 'Ratio_R', 'AC_Red', 'DC_Red', 'AC_IR', 'DC_IR']
X = df_clean[features]
y = df_clean['Glucose_mg_dL']

# 4. Calculate feature means for future API imputation fallbacks
feature_means = X.mean().to_dict()
print("\nFeature means (used as fallbacks in API server):")
for feat, val in feature_means.items():
    print(f"  - {feat:<15}: {val:.4f}")

# 5. Fit the StandardScaler
print("\nFitting StandardScaler...")
scaler = StandardScaler()
X_scaled = scaler.fit_transform(X)

# 6. Evaluate model via 5-Fold Cross Validation
print("\nEvaluating model with 5-Fold Cross-Validation...")
kf = KFold(n_splits=5, shuffle=True, random_state=42)
rf_cv = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
cv_results = cross_validate(
    rf_cv, X_scaled, y, cv=kf,
    scoring=['r2', 'neg_mean_absolute_error'],
    return_train_score=False
)
r2_mean = np.mean(cv_results['test_r2'])
r2_std = np.std(cv_results['test_r2'])
mae_mean = np.mean(-cv_results['test_neg_mean_absolute_error'])
mae_std = np.std(-cv_results['test_neg_mean_absolute_error'])

print(f"  CV R2  = {r2_mean:.4f} +/- {r2_std:.4f}")
print(f"  CV MAE = {mae_mean:.2f} +/- {mae_std:.2f} mg/dL")

# 7. Train final model on all clean data
print("\nTraining final model on all clean data...")
model_final = RandomForestRegressor(n_estimators=100, max_depth=6, random_state=42)
model_final.fit(X_scaled, y)

# 8. Save artifacts
print(f"\nSaving model to: {model_path}")
joblib.dump(model_final, model_path)

print(f"Saving scaler to: {scaler_path}")
joblib.dump(scaler, scaler_path)

metadata = {
    'model_name': 'Random Forest Regressor (v6)',
    'features': features,
    'feature_means': feature_means,
    'r2_cv_mean': float(r2_mean),
    'r2_cv_std': float(r2_std),
    'mae_cv_mean': float(mae_mean),
    'mae_cv_std': float(mae_std),
    'train_samples': int(len(df_clean))
}
print(f"Saving metadata to: {metadata_path}")
joblib.dump(metadata, metadata_path)

print("\n[OK] Training completed successfully!")
print("="*60)
