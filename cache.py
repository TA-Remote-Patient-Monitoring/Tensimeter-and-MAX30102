"""
In-memory TTL Cache Module — Optimasi performa untuk mengurangi
round-trip ke SQLite pada request yang berulang.

Menggunakan cachetools.TTLCache:
- Thread-safe access dengan lock per cache
- Otomatis expire berdasarkan TTL
- Max size mencegah memory leak
"""

import threading
from cachetools import TTLCache

# ── User Lookup Cache ──────────────────────────────────────
# Cache user object by email/phone (untuk login & get_current_user).
# TTL panjang karena user data hampir tidak berubah.
user_cache = TTLCache(maxsize=500, ttl=300)  # 5 menit
user_cache_lock = threading.Lock()

# ── User by ID Cache ───────────────────────────────────────
# Cache user object by ID (untuk get_current_user dari JWT token).
user_by_id_cache = TTLCache(maxsize=500, ttl=300)  # 5 menit
user_by_id_cache_lock = threading.Lock()

# ── Profile Cache ──────────────────────────────────────────
# Cache profile list per user_id.
# TTL 60 detik — profile jarang berubah.
profile_cache = TTLCache(maxsize=1000, ttl=60)  # 1 menit
profile_cache_lock = threading.Lock()

# ── Profile Ownership Cache ────────────────────────────────
# Cache profile ownership check (profile_id -> user_id).
# Dipakai di measurements untuk validasi akses.
profile_owner_cache = TTLCache(maxsize=2000, ttl=120)  # 2 menit
profile_owner_cache_lock = threading.Lock()

# ── Latest Measurement Cache ──────────────────────────────
# Cache latest measurement per profile.
# TTL pendek karena bisa berubah saat save measurement baru.
latest_measurement_cache = TTLCache(maxsize=2000, ttl=15)  # 15 detik
latest_measurement_cache_lock = threading.Lock()

# ── Measurements List Cache ───────────────────────────────
# Cache measurement list per profile + pagination key.
# TTL pendek karena data bisa bertambah.
measurements_cache = TTLCache(maxsize=2000, ttl=10)  # 10 detik
measurements_cache_lock = threading.Lock()


# ── Invalidation Helpers ──────────────────────────────────

def invalidate_profile_cache(user_id: int):
    """Hapus profile cache saat profile dibuat/dihapus."""
    with profile_cache_lock:
        profile_cache.pop(user_id, None)


def invalidate_latest_measurement(profile_id: int):
    """Hapus latest measurement cache saat measurement baru disimpan."""
    with latest_measurement_cache_lock:
        latest_measurement_cache.pop(profile_id, None)


def invalidate_measurements_list(profile_id: int):
    """Hapus semua cached measurement lists untuk profile tertentu."""
    with measurements_cache_lock:
        # Hapus semua key yang mengandung profile_id
        keys_to_remove = [k for k in measurements_cache if k[0] == profile_id]
        for k in keys_to_remove:
            measurements_cache.pop(k, None)


def invalidate_profile_owner(profile_id: int):
    """Hapus profile ownership cache."""
    with profile_owner_cache_lock:
        profile_owner_cache.pop(profile_id, None)
