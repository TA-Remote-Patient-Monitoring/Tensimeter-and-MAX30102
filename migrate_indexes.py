"""
Script migrasi untuk membuat index pada database SQLite yang sudah ada.
Jalankan sekali saja sebelum stress test untuk memastikan semua index terbuat.

Usage:
    python migrate_indexes.py
"""

import sqlite3
import os
import sys


def migrate():
    db_path = os.path.join(os.path.dirname(__file__), "omron.db")
    if not os.path.exists(db_path):
        print(f"[ERROR] Database tidak ditemukan: {db_path}")
        sys.exit(1)

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    indexes = [
        # ── Users ──────────────────────────────────────────────
        ("ix_users_email",       "CREATE INDEX IF NOT EXISTS ix_users_email ON users(email)"),
        ("ix_users_phone",       "CREATE INDEX IF NOT EXISTS ix_users_phone ON users(phone)"),

        # ── Profiles ──────────────────────────────────────────
        ("ix_profiles_id_user",  "CREATE INDEX IF NOT EXISTS ix_profiles_id_user ON profiles(id_user)"),

        # ── Measurements ──────────────────────────────────────
        ("ix_meas_user_profile",       "CREATE INDEX IF NOT EXISTS ix_meas_user_profile ON measurements(id_user, id_profile)"),
        ("ix_meas_datetime",           "CREATE INDEX IF NOT EXISTS ix_meas_datetime ON measurements(datetime)"),
        ("ix_meas_profile_user_dt",    "CREATE INDEX IF NOT EXISTS ix_meas_profile_user_dt ON measurements(id_profile, id_user, datetime)"),

        # ── SpO2 Measurements ────────────────────────────────
        ("ix_spo2_user_profile",       "CREATE INDEX IF NOT EXISTS ix_spo2_user_profile ON spo2_measurements(id_user, id_profile)"),
        ("ix_spo2_datetime",           "CREATE INDEX IF NOT EXISTS ix_spo2_datetime ON spo2_measurements(datetime)"),
        ("ix_spo2_profile_user_dt",    "CREATE INDEX IF NOT EXISTS ix_spo2_profile_user_dt ON spo2_measurements(id_profile, id_user, datetime)"),
    ]

    print(f"[INFO] Migrasi index pada: {db_path}")
    print(f"[INFO] Membuat {len(indexes)} index...\n")

    for name, sql in indexes:
        try:
            cursor.execute(sql)
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAIL] {name} - Error: {e}")

    # Aktifkan WAL mode
    cursor.execute("PRAGMA journal_mode=WAL")
    wal_mode = cursor.fetchone()[0]
    print(f"\n[INFO] Journal mode: {wal_mode}")

    # Jalankan ANALYZE untuk update statistik query planner
    print("[INFO] Menjalankan ANALYZE untuk update query planner statistik...")
    cursor.execute("ANALYZE")

    conn.commit()
    conn.close()

    print("\n[DONE] Migrasi index selesai!")
    print("[TIP]  Jalankan 'python -c \"import database\"' untuk verifikasi PRAGMA settings.")


if __name__ == "__main__":
    migrate()
