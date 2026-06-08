# 📖 Dokumentasi API — Omron HEM-7155T Backend

Backend API untuk mengelola data tekanan darah dari perangkat Omron HEM-7155T via Bluetooth Low Energy (BLE).

---

## 📋 Daftar Isi

- [Instalasi & Menjalankan Server](#-instalasi--menjalankan-server)
- [Konfigurasi Environment](#-konfigurasi-environment)
- [Daftar Endpoint API](#-daftar-endpoint-api)
  - [General](#1-general)
  - [Auth (Autentikasi)](#2-auth-autentikasi)
  - [Profiles (Profil)](#3-profiles-profil)
  - [Measurements (Pengukuran)](#4-measurements-pengukuran)
  - [SpO2 Measurements (Sensor SpO2)](#5-spo2-measurements-sensor-spo2)
  - [BLE Device (Perangkat Bluetooth)](#6-ble-device-perangkat-bluetooth)
- [Cara Menggunakan di Postman](#-cara-menggunakan-di-postman)
- [Alur Penggunaan (Flow)](#-alur-penggunaan-flow)

---

## 🚀 Instalasi & Menjalankan Server

### 1. Install Dependencies

```bash
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt
```

> **Catatan:** Flag `--trusted-host` diperlukan jika berada di jaringan kampus/proxy yang memblokir SSL.

### 2. Buat File `.env`

```bash
# Copy dari template
cp .env.example .env
```

Atau generate secret key secara otomatis:

```bash
python -c "import secrets; print('SECRET_KEY=' + secrets.token_hex(32))" > .env
```

### 3. Jalankan Server

```bash
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

> Ganti `0.0.0.0` dengan IP address komputer jika ingin diakses dari perangkat lain dalam jaringan yang sama.

Server akan berjalan di: `http://<IP_ADDRESS>:8000`

### 4. Cek Dokumentasi Otomatis (Swagger UI)

Buka di browser:
- **Swagger UI**: `http://<IP_ADDRESS>:8000/docs`
- **ReDoc**: `http://<IP_ADDRESS>:8000/redoc`

---

## 🔐 Konfigurasi Environment

File `.env` harus berisi:

```env
SECRET_KEY=ganti-dengan-string-acak-yang-panjang
```

Secret key ini digunakan untuk mengenkripsi JWT token pada fitur login.

---

## 📡 Daftar Endpoint API

**Base URL:** `http://<IP_ADDRESS>:8000`

---

### 1. General

#### `GET /`
Cek apakah server berjalan.

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/` |
| Body | Tidak ada |

**Response (200):**
```json
{
  "message": "Omron BLE Python Backend is running"
}
```

---

### 2. Auth (Autentikasi)

#### `POST /api/auth/register`
Mendaftarkan user baru.

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/api/auth/register` |
| Content-Type | `application/json` |

**Body (JSON):**
```json
{
  "name": "Ardi Pradiva",
  "email": "ardi@example.com",
  "phone": "081234567890",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "message": "Registrasi berhasil.",
  "id_user": 1
}
```

**Response (400) — Email sudah terdaftar:**
```json
{
  "detail": "Email sudah terdaftar."
}
```

---

#### `POST /api/auth/login`
Login dan mendapatkan JWT token.

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/api/auth/login` |
| Content-Type | `application/json` |

**Body (JSON):**
```json
{
  "email": "ardi@example.com",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "id_user": 1,
  "name": "Ardi Pradiva",
  "email": "ardi@example.com",
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (401) — Kredensial salah:**
```json
{
  "detail": "Email atau password salah."
}
```

---

### 3. Profiles (Profil)

Satu user bisa punya banyak profil (misal: Ayah, Ibu, Anak).

#### `POST /api/profiles`
Buat profil baru untuk user tertentu (mendukung upload foto).

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/api/profiles` |
| Content-Type | `multipart/form-data` |

**Body (form-data):**

| Key | Type | Value | Keterangan |
|-----|------|-------|------------|
| `id_user` | Text | `1` | ID user pemilik profil |
| `name` | Text | `Ayah` | Nama profil |
| `age` | Text | `45` | Umur |
| `gender` | Text | `Laki-laki` | Jenis kelamin |
| `tb` | Text | `170.5` | Tinggi badan (cm) |
| `bb` | Text | `75.0` | Berat badan (kg) |
| `image` | File | *(pilih file gambar)* | Opsional, foto profil |

**Response (200):**
```json
{
  "id": 1,
  "id_user": 1,
  "name": "Ayah",
  "age": 45,
  "gender": "Laki-laki",
  "tb": 170.5,
  "bb": 75.0,
  "image_url": "/uploads/profile_abc123.jpg"
}
```

> **Catatan:** `image_url` akan `null` jika tidak upload gambar.

---

#### `GET /api/profiles/{id_user}`
Ambil semua profil milik satu user.

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/api/profiles/1` |
| Body | Tidak ada |

**Response (200):**
```json
[
  {
    "id": 1,
    "id_user": 1,
    "name": "Ayah",
    "age": 45,
    "gender": "Laki-laki",
    "tb": 170.5,
    "bb": 75.0,
    "image_url": "/uploads/profile_abc123.jpg"
  },
  {
    "id": 2,
    "id_user": 1,
    "name": "Ibu",
    "age": 42,
    "gender": "Perempuan",
    "tb": 160.0,
    "bb": 60.0,
    "image_url": null
  }
]
```

**Response (404):**
```json
{
  "detail": "Belum ada profile untuk user ini."
}
```

---

#### `DELETE /api/profiles/{id_profile}`
Hapus profil berdasarkan ID profil.

| Item | Detail |
|------|--------|
| Method | `DELETE` |
| URL | `http://<IP>:8000/api/profiles/1` |
| Body | Tidak ada |

**Response (200):**
```json
{
  "message": "Profile berhasil dihapus."
}
```

**Response (404):**
```json
{
  "detail": "Profile tidak ditemukan."
}
```

---

### 4. Measurements (Pengukuran)

#### `POST /api/measurements`
Simpan data pengukuran tekanan darah.

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/api/measurements` |
| Content-Type | `application/json` |

**Body (JSON):**
```json
{
  "id_user": 1,
  "id_profile": 1,
  "sys": 120,
  "dia": 80,
  "bpm": 72,
  "ihb": 0,
  "mov": 0,
  "datetime": "2026-06-03T15:00:00"
}
```

| Field | Tipe | Keterangan |
|-------|------|------------|
| `sys` | int | Tekanan sistolik (mmHg) |
| `dia` | int | Tekanan diastolik (mmHg) |
| `bpm` | int | Detak jantung per menit |
| `ihb` | int | Irregular Heartbeat (0 = normal, 1 = terdeteksi) |
| `mov` | int | Movement detected (0 = normal, 1 = terdeteksi gerakan) |
| `datetime` | string | Waktu pengukuran format ISO 8601 |

**Response (200):**
```json
{
  "id": 1,
  "id_user": 1,
  "id_profile": 1,
  "sys": 120,
  "dia": 80,
  "bpm": 72,
  "ihb": false,
  "mov": false,
  "datetime": "2026-06-03T15:00:00"
}
```

**Response (404):**
```json
{
  "detail": "Profile tidak ditemukan atau bukan milik user ini."
}
```

---

#### `GET /api/measurements/{id_profile}`
Ambil semua riwayat pengukuran berdasarkan profil (terbaru duluan).

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/api/measurements/1` |
| Body | Tidak ada |

**Response (200):**
```json
[
  {
    "id": 2,
    "id_user": 1,
    "id_profile": 1,
    "sys": 118,
    "dia": 78,
    "bpm": 70,
    "ihb": false,
    "mov": false,
    "datetime": "2026-06-03T16:00:00"
  },
  {
    "id": 1,
    "id_user": 1,
    "id_profile": 1,
    "sys": 120,
    "dia": 80,
    "bpm": 72,
    "ihb": false,
    "mov": false,
    "datetime": "2026-06-03T15:00:00"
  }
]
```

---

#### `GET /api/measurements/{id_profile}/latest`
Ambil hanya pengukuran terbaru untuk ditampilkan di dashboard.

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/api/measurements/1/latest` |
| Body | Tidak ada |

**Response (200):**
```json
{
  "id": 2,
  "id_user": 1,
  "id_profile": 1,
  "sys": 118,
  "dia": 78,
  "bpm": 70,
  "ihb": false,
  "mov": false,
  "datetime": "2026-06-03T16:00:00"
}
```

---

### 5. SpO2 Measurements (Sensor SpO2)

#### `POST /api/measurements/spo2`
Simpan data pengukuran dari sensor SpO2 (MAX30102).

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/api/measurements/spo2` |
| Content-Type | `application/json` |

**Body (JSON):**
```json
{
  "id_user": 1,
  "id_profile": 1,
  "spo2": 98.5,
  "bpm": 75.0,
  "temperature": 36.5,
  "datetime": "2026-06-03T15:00:00"
}
```

| Field | Tipe | Keterangan |
|-------|------|------------|
| `spo2` | float | Nilai saturasi oksigen (%) |
| `bpm` | float | Detak jantung per menit (BPM) |
| `temperature` | float | Suhu tubuh (Celcius) |
| `datetime` | string | Waktu pengukuran format ISO 8601 |

**Response (200):**
```json
{
  "id": 1,
  "id_user": 1,
  "id_profile": 1,
  "spo2": 98.5,
  "bpm": 75.0,
  "temperature": 36.5,
  "datetime": "2026-06-03T15:00:00"
}
```

---

#### `GET /api/measurements/{id_profile}/spo2`
Ambil semua riwayat pengukuran SpO2 berdasarkan profil (terbaru duluan).

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/api/measurements/1/spo2` |
| Body | Tidak ada |

**Response (200):**
```json
[
  {
    "id": 1,
    "id_user": 1,
    "id_profile": 1,
    "spo2": 98.5,
    "bpm": 75.0,
    "temperature": 36.5,
    "datetime": "2026-06-03T15:00:00"
  }
]
```

---

#### `GET /api/measurements/{id_profile}/spo2/latest`
Ambil hanya pengukuran SpO2 terbaru.

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/api/measurements/1/spo2/latest` |
| Body | Tidak ada |

**Response (200):**
```json
{
  "id": 1,
  "id_user": 1,
  "id_profile": 1,
  "spo2": 98.5,
  "bpm": 75.0,
  "temperature": 36.5,
  "datetime": "2026-06-03T15:00:00"
}
```

---

### 6. BLE Device (Perangkat Bluetooth)

> ⚠️ Endpoint ini hanya bisa digunakan pada komputer yang memiliki Bluetooth dan perangkat Omron dalam jangkauan.

#### `GET /scan`
Scan perangkat BLE di sekitar.

| Item | Detail |
|------|--------|
| Method | `GET` |
| URL | `http://<IP>:8000/scan` |

**Response (200):**
```json
{
  "devices": [
    {
      "mac": "00:5F:BF:1B:AF:01",
      "name": "BLEsmart_00000564005FBF1BAF01",
      "rssi": -47
    }
  ],
  "message": "Perangkat BLE berhasil dipindai"
}
```

---

#### `POST /connect-and-read`
Hubungkan ke perangkat Omron dan baca semua data pengukuran.

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/connect-and-read` |
| Content-Type | `application/json` |

**Body (JSON) — Mode Pairing:**
```json
{
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "hem-7155t",
  "new_records_only": false,
  "sync_time": false,
  "pairing": true,
  "user_index": 0
}
```

**Body (JSON) — Mode Baca Data:**
```json
{
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "hem-7155t",
  "new_records_only": false,
  "sync_time": true,
  "pairing": false,
  "user_index": 0
}
```

| Field | Tipe | Keterangan |
|-------|------|------------|
| `mac_address` | string | MAC address perangkat Omron |
| `device_name` | string | Nama driver perangkat (misal: `hem-7155t`) |
| `pairing` | bool | `true` = hanya pairing, `false` = baca data |
| `new_records_only` | bool | `true` = hanya data baru yang belum dibaca |
| `sync_time` | bool | `true` = sinkronkan jam perangkat |
| `user_index` | int | `0` = User 1, `1` = User 2 (slot pada alat) |

**Response (200) — Pairing:**
```json
{
  "message": "Pairing sucessful."
}
```

**Response (200) — Baca Data:**
```json
{
  "message": "Data read successfully.",
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "BLEsmart_00000564005FBF1BAF01",
  "records": [...]
}
```

---

#### `POST /latest-bp-records`
Hubungkan ke perangkat Omron dan baca hanya data pengukuran terbaru.

| Item | Detail |
|------|--------|
| Method | `POST` |
| URL | `http://<IP>:8000/latest-bp-records` |
| Content-Type | `application/json` |

**Body (JSON):** *(Sama seperti `/connect-and-read`)*
```json
{
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "hem-7155t",
  "new_records_only": false,
  "sync_time": true,
  "pairing": false,
  "user_index": 0
}
```

**Response (200):**
```json
{
  "message": "Newest record read with success.",
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "BLEsmart_00000564005FBF1BAF01",
  "latest_record": {
    "sys": 120,
    "dia": 80,
    "bpm": 72,
    "ihb": false,
    "mov": false,
    "datetime": "2026-06-03T15:00:00"
  }
}
```

---

## 🧪 Cara Menggunakan di Postman

### Setup Awal

1. **Buka Postman** dan buat Collection baru bernama `Omron HEM-7155T API`
2. **Buat Variable** di Collection:
   - `base_url` = `http://<IP_ADDRESS>:8000` (ganti sesuai IP server)

### Step-by-Step Testing

#### Step 1: Cek Server
```
GET {{base_url}}/
```

#### Step 2: Register User
```
POST {{base_url}}/api/auth/register
```
- Tab **Body** → pilih **raw** → pilih **JSON**
- Paste body JSON register di atas

#### Step 3: Login
```
POST {{base_url}}/api/auth/login
```
- Tab **Body** → pilih **raw** → pilih **JSON**
- Paste body JSON login
- Catat `id_user` dan `token` dari response

#### Step 4: Buat Profile
```
POST {{base_url}}/api/profiles
```
- Tab **Body** → pilih **form-data**
- Isi field `id_user`, `name`, `age`, `gender`, `tb`, `bb`
- (Opsional) Tambahkan field `image` → ubah tipe ke **File** → pilih gambar

#### Step 5: Lihat Profiles
```
GET {{base_url}}/api/profiles/1
```
> Ganti `1` dengan `id_user` dari Step 3

#### Step 6: Simpan Measurement
```
POST {{base_url}}/api/measurements
```
- Tab **Body** → pilih **raw** → pilih **JSON**
- Paste body JSON measurement

#### Step 7: Lihat Riwayat
```
GET {{base_url}}/api/measurements/1
```
> Ganti `1` dengan `id_profile` dari Step 4

#### Step 8: Lihat Data Terbaru
```
GET {{base_url}}/api/measurements/1/latest
```

---

## 🔄 Alur Penggunaan (Flow)

```
┌─────────────┐
│  Register   │  POST /api/auth/register
└──────┬──────┘
       │
       ▼
┌─────────────┐
│    Login     │  POST /api/auth/login → dapat id_user & token
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Buat Profile │  POST /api/profiles (Ayah/Ibu/Anak)
└──────┬──────┘
       │
       ▼
┌──────────────────┐
│ Scan BLE Device   │  GET /scan
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Pairing Omron     │  POST /connect-and-read (pairing=true)
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Baca Data Omron   │  POST /connect-and-read (pairing=false)
│ atau              │  POST /latest-bp-records
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Simpan ke DB      │  POST /api/measurements
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ Lihat Riwayat     │  GET /api/measurements/{id_profile}
│ atau Terbaru      │  GET /api/measurements/{id_profile}/latest
└──────────────────┘
```

---

## 📁 Struktur Database

### Tabel `users`
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | INTEGER (PK) | Auto increment |
| name | TEXT | Nama lengkap |
| email | TEXT (UNIQUE) | Email untuk login |
| phone | TEXT | Nomor telepon |
| password | TEXT | Password ter-hash (bcrypt) |

### Tabel `profiles`
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | INTEGER (PK) | Auto increment |
| id_user | INTEGER (FK) | Referensi ke `users.id` |
| name | TEXT | Nama profil (Ayah, Ibu, dll) |
| age | INTEGER | Umur |
| gender | TEXT | Jenis kelamin |
| tb | FLOAT | Tinggi badan (cm) |
| bb | FLOAT | Berat badan (kg) |
| image_path | TEXT | Path file gambar profil |

### Tabel `measurements`
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | INTEGER (PK) | Auto increment |
| id_user | INTEGER (FK) | Referensi ke `users.id` |
| id_profile | INTEGER (FK) | Referensi ke `profiles.id` |
| sys | INTEGER | Tekanan sistolik (mmHg) |
| dia | INTEGER | Tekanan diastolik (mmHg) |
| bpm | INTEGER | Detak jantung / menit |
| ihb | BOOLEAN | Irregular Heartbeat detected |
| mov | BOOLEAN | Movement detected |
| datetime | DATETIME | Waktu pengukuran |

### Tabel `spo2_measurements`
| Kolom | Tipe | Keterangan |
|-------|------|------------|
| id | INTEGER (PK) | Auto increment |
| id_user | INTEGER (FK) | Referensi ke `users.id` |
| id_profile | INTEGER (FK) | Referensi ke `profiles.id` |
| spo2 | FLOAT | Saturasi oksigen (%) |
| bpm | FLOAT | Detak jantung (BPM) |
| temperature | FLOAT | Suhu tubuh (Celcius) |
| datetime | DATETIME | Waktu pengukuran |

---

## ⚠️ Troubleshooting

| Masalah | Solusi |
|---------|--------|
| `ModuleNotFoundError` | Jalankan `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
| `SECRET_KEY belum diset` | Buat file `.env` dengan `SECRET_KEY=<random_string>` |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Tambahkan `--trusted-host pypi.org --trusted-host files.pythonhosted.org` pada perintah pip |
| 404 pada `/api/profiles/{id}` | User tersebut belum punya profile. Buat dulu via `POST /api/profiles` |
| `Invalid HTTP request received` | Client mengirim request non-HTTP (kemungkinan WebSocket atau raw TCP) ke port HTTP |
