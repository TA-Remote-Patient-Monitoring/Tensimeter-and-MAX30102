# 📖 Dokumentasi Teknis Lengkap — Tensimeter and MAX30102 Backend

> **Proyek Skripsi:** Sistem Remote Patient Monitoring Terintegrasi  
> **Perangkat:** Omron HEM-7155T (Tensimeter BLE) + ESP32-S3/MAX30102 (Oksimeter & SpO2)  
> **Bahasa:** Python 3.10+ (Backend) + C/C++ (Firmware ESP32)  
> **Framework:** FastAPI + SQLAlchemy + Bleak (BLE) + Arduino (ESP32)  
> **Branch:** `optimasi`

---

## 📋 Daftar Isi

- [1. Gambaran Umum Sistem](#1-gambaran-umum-sistem)
- [2. Prasyarat (Prerequisites)](#2-prasyarat-prerequisites)
- [3. Arsitektur Sistem](#3-arsitektur-sistem)
- [4. Struktur Direktori & Penjelasan File](#4-struktur-direktori--penjelasan-file)
- [5. Skema Database (ERD)](#5-skema-database-erd)
- [6. Modul BLE Omron (omblepy)](#6-modul-ble-omron-omblepy)
- [7. Device Driver (deviceSpecific)](#7-device-driver-devicespecific)
- [8. REST API Endpoints](#8-rest-api-endpoints)
- [9. Integrasi Machine Learning (Prediksi Gula Darah)](#9-integrasi-machine-learning-prediksi-gula-darah)
- [10. Firmware ESP32 + MAX30102](#10-firmware-esp32--max30102)
- [11. Optimasi Performa (Branch Optimasi)](#11-optimasi-performa-branch-optimasi)
- [12. WebSocket](#12-websocket)
- [13. Utility Scripts](#13-utility-scripts)
- [14. Instalasi & Deployment](#14-instalasi--deployment)
- [15. Konfigurasi Environment](#15-konfigurasi-environment)
- [16. Alur Penggunaan End-to-End](#16-alur-penggunaan-end-to-end)
- [17. Troubleshooting](#17-troubleshooting)
- [18. Catatan Keamanan](#18-catatan-keamanan)

---

## 1. Gambaran Umum Sistem

Sistem ini adalah **backend server** yang berfungsi sebagai:

1. **Gateway BLE** — Menjembatani komunikasi Bluetooth Low Energy antara perangkat tensimeter Omron HEM-7155T dengan aplikasi client (mobile/web).
2. **REST API Server** — Menyediakan endpoint untuk autentikasi pengguna, manajemen profil keluarga, dan penyimpanan/pengambilan data pengukuran kesehatan.
3. **Data Aggregator** — Menggabungkan data dari dua sumber perangkat keras berbeda (Omron via BLE dan ESP32/MAX30102 via WiFi/HTTP) ke dalam satu database terpadu.
4. **ML Gateway** — Menghubungkan data sensor ke layanan Machine Learning eksternal untuk prediksi kadar gula darah (*blood glucose estimation*).
5. **Firmware Sensor** — Menyertakan firmware Arduino untuk ESP32-S3 + MAX30102 yang mengukur SpO2 dan BPM secara real-time.

### Konteks Perangkat Keras

| Perangkat | Fungsi | Koneksi ke Backend |
|-----------|--------|-------------------|
| **Omron HEM-7155T** | Mengukur tekanan darah (Sistolik, Diastolik, BPM) + deteksi IHB & gerakan | Bluetooth Low Energy (BLE) via library `bleak` |
| **ESP32-S3 + MAX30102** | Mengukur saturasi oksigen (SpO2), detak jantung (BPM), dan suhu tubuh | WiFi → HTTP POST ke endpoint `/api/measurements/spo2` |

### Perbedaan dengan HEM7155T-Python (Branch Sebelumnya)

Branch `optimasi` ini memiliki peningkatan signifikan dibanding versi sebelumnya:

| Aspek | Sebelumnya | Branch `optimasi` |
|-------|------------|-------------------|
| **Caching** | Tidak ada | In-memory TTL Cache (cachetools) per modul |
| **Database** | Default SQLite config | SQLite PRAGMA tuning (WAL, 64MB cache, mmap 256MB) |
| **Connection Pool** | Default | pool_size=40, max_overflow=60 |
| **Bcrypt** | Sinkron (blocking event loop) | Async via dedicated thread pool (32 workers) |
| **HTTP Client (ML)** | Buat client baru per request | Singleton AsyncClient dengan connection pooling |
| **Compression** | Tidak ada | GZip middleware (500B+ payloads) |
| **File I/O** | Sinkron | Async file write via `aiofiles` |
| **Stress Test** | Tidak ada | k6 script (50→200 VU ramp-up) |
| **Firmware MAX30102** | Terpisah di folder ARDUINO | Disertakan langsung dalam project |

---

## 2. Prasyarat (Prerequisites)

### 2.1 Perangkat Keras (Hardware)

| Komponen | Spesifikasi | Keterangan |
|----------|-------------|------------|
| **Komputer/Laptop** | Windows 10/11 dengan adapter Bluetooth 4.0+ (BLE) | Sebagai host server backend |
| **Omron HEM-7155T** | Tensimeter digital Omron dengan BLE | Mendukung 2 user slot, masing-masing 60 record |
| **ESP32-S3 DevKit** | ESP32-S3 atau ESP32-C3 | Mikrokontroler untuk sensor SpO2 |
| **MAX30102** | Sensor pulse oximeter dan heart-rate (GY-MAX30102 breakout) | Terhubung ke ESP32 via I2C (SDA→GPIO8, SCL→GPIO9) |
| **Jaringan WiFi** | LAN yang sama antara ESP32 dan server | Untuk komunikasi HTTP ESP32 → Backend |

### 2.2 Perangkat Lunak (Software)

| Software | Versi Minimum | Fungsi |
|----------|---------------|--------|
| **Python** | 3.10+ | Runtime utama backend |
| **pip** | Latest | Package manager Python |
| **Git** | Latest | Version control |
| **Bluetooth Driver** | Windows built-in | Driver BLE untuk `bleak` |
| **Arduino IDE** | 2.x | Untuk flash firmware ESP32 + MAX30102 |

### 2.3 Pustaka Python (Dependencies)

Semua tercantum di [requirements.txt](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/requirements.txt):

| Package | Versi | Fungsi |
|---------|-------|--------|
| `fastapi` | 0.115.12 | Web framework async untuk REST API |
| `uvicorn` | 0.34.2 | ASGI server untuk menjalankan FastAPI |
| `bleak` | 0.22.3 | Library BLE cross-platform untuk Python |
| `sqlalchemy` | 2.0.40 | ORM untuk interaksi database SQLite |
| `pydantic` | 2.11.4 | Validasi data dan serialisasi (sudah termasuk dalam FastAPI) |
| `passlib[bcrypt]` | 1.7.4 | Hashing password (bcrypt) |
| `bcrypt` | <5 | Backend hashing untuk passlib |
| `python-jose[cryptography]` | 3.3.0 | Pembuatan dan verifikasi JWT token |
| `python-dotenv` | 1.0.1 | Memuat variabel environment dari file `.env` |
| `python-multipart` | 0.0.20 | Parsing `multipart/form-data` (upload file) |
| `matplotlib` | 3.10.1 | Plotting grafik CSV (utility) |
| `numpy` | 2.2.5 | Komputasi numerik untuk plotting |
| `terminaltables` | 3.1.10 | Tabel ASCII untuk CLI mode |
| `aiofiles` | 24.1.0 | Async file I/O (upload foto profil) |
| `httpx` | ≥0.27.0 | HTTP client async untuk memanggil ML API |
| `cachetools` | ≥5.3.0 | In-memory TTL cache (user, profile, measurement) |
| `orjson` | ≥3.9.0 | JSON serialization cepat (opsional, FastAPI auto-detect) |

### 2.4 Library Arduino (untuk ESP32 + MAX30102)

| Library | Sumber | Fungsi |
|---------|--------|--------|
| `SparkFun MAX3010x Pulse and Proximity Sensor Library` | Arduino Library Manager | Driver sensor MAX30102, algoritma SpO2 dan Heart Rate |

---

## 3. Arsitektur Sistem

### 3.1 Diagram Arsitektur High-Level

```mermaid
graph TB
    subgraph "Perangkat Keras (Hardware)"
        OMRON["🩺 Omron HEM-7155T<br/>Tensimeter BLE"]
        ESP32["📡 ESP32-S3 + MAX30102<br/>Oksimeter WiFi"]
    end

    subgraph "Backend Server (Python/FastAPI)"
        MAIN["main.py<br/>FastAPI App Entry"]
        
        subgraph "Routers (API Layer)"
            AUTH["auth.py<br/>Register & Login"]
            PROF["profiles.py<br/>Manajemen Profil"]
            MEAS["measurements.py<br/>Data Tensi & SpO2"]
        end
        
        subgraph "BLE Layer"
            OMBLEPY["omblepy.py<br/>BLE Tx/Rx Handler"]
            SHARED["sharedDriver.py<br/>Shared EEPROM Logic"]
            DEVDRV["deviceSpecific/<br/>hem-7155t.py"]
        end
        
        subgraph "Performance Layer (Branch Optimasi)"
            CACHE["cache.py<br/>In-memory TTL Cache"]
            DBOPT["database.py<br/>SQLite PRAGMA Tuning"]
        end
        
        subgraph "Data Layer"
            MODELS["models.py<br/>SQLAlchemy Models"]
            SCHEMAS["schemas.py<br/>Pydantic Schemas"]
            DB_MOD["database.py<br/>DB Engine & Session"]
        end
    end
    
    subgraph "Storage"
        SQLITE[("SQLite<br/>omron.db")]
        CSV["CSV Files<br/>user1.csv, user2.csv"]
        JSON["ubpm.json"]
        UPLOADS["uploads/<br/>Profile Images"]
    end
    
    subgraph "External Services"
        ML_API["🤖 ML API Server<br/>:8001/predict<br/>Prediksi Gula Darah"]
    end
    
    subgraph "Client Applications"
        FLUTTER["📱 Flutter App"]
        POSTMAN["🔧 Postman / Web"]
    end

    OMRON -->|"BLE GATT"| OMBLEPY
    OMBLEPY --> SHARED
    SHARED --> DEVDRV
    
    ESP32 -->|"HTTP POST<br/>/api/measurements/spo2"| MEAS
    
    MAIN --> AUTH
    MAIN --> PROF
    MAIN --> MEAS
    
    AUTH --> CACHE
    PROF --> CACHE
    MEAS --> CACHE
    AUTH --> DB_MOD
    PROF --> DB_MOD
    MEAS --> DB_MOD
    MEAS -->|"httpx POST"| ML_API
    
    DB_MOD --> DBOPT
    DB_MOD --> SQLITE
    OMBLEPY --> CSV
    OMBLEPY --> JSON
    PROF --> UPLOADS
    
    FLUTTER -->|"HTTP/REST"| MAIN
    POSTMAN -->|"HTTP/REST"| MAIN
    
    MODELS --> DB_MOD
    SCHEMAS --> AUTH
    SCHEMAS --> PROF
    SCHEMAS --> MEAS
```

### 3.2 Diagram Sequence — Alur Lengkap Pengukuran

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant App as 📱 Flutter App
    participant API as ⚙️ FastAPI Backend
    participant Cache as 🗃️ TTL Cache
    participant BLE as 🔵 Bleak (BLE Stack)
    participant Omron as 🩺 Omron HEM-7155T
    participant ESP as 📡 ESP32+MAX30102
    participant ML as 🤖 ML API
    participant DB as 🗄️ SQLite DB

    Note over U, DB: FASE 1 — Registrasi & Login
    U->>App: Buka aplikasi, register
    App->>API: POST /api/auth/register
    API->>API: hash_password (async, thread pool)
    API->>DB: INSERT INTO users
    DB-->>API: OK (id_user)
    API-->>App: {"message": "Registrasi berhasil", "id_user": 1}
    
    U->>App: Login
    App->>API: POST /api/auth/login
    API->>Cache: Check user_cache (email)
    Cache-->>API: Cache miss
    API->>DB: SELECT user WHERE email
    API->>API: verify_password (async, thread pool)
    API->>Cache: Store CachedUser
    API->>API: generate JWT (exp: 7 hari)
    API-->>App: {"token": "eyJ...", "id_user": 1}

    Note over U, DB: FASE 2 — Buat Profil Keluarga
    U->>App: Buat profil "Ayah"
    App->>API: POST /api/profiles (form-data + foto)
    API->>API: Async file write (aiofiles)
    API->>DB: INSERT INTO profiles
    API->>Cache: Invalidate profile_cache
    API-->>App: {"id": 1, "name": "Ayah", "image_url": "/uploads/..."}

    Note over U, DB: FASE 3 — Pengukuran Tekanan Darah (Omron)
    U->>Omron: Tekan tombol START di alat
    Omron->>Omron: Mengukur → simpan ke EEPROM internal
    
    U->>App: Tap "Baca Data Omron"
    App->>API: GET /scan
    API->>BLE: BleakScanner.discover()
    BLE-->>API: List devices [{mac, name, rssi}]
    API-->>App: {"devices": [...]}
    
    App->>API: POST /connect-and-read
    API->>BLE: BleakClient.connect(mac)
    BLE->>Omron: BLE Connection Request
    Omron-->>BLE: Connected
    
    API->>BLE: unlockWithUnlockKey(pairing_key)
    BLE->>Omron: Write to Unlock UUID
    Omron-->>BLE: Unlock OK (0x8100)
    
    API->>BLE: startTransmission()
    BLE->>Omron: Write 0x0800000000100018
    Omron-->>BLE: ACK (0x8000)
    
    API->>BLE: readContinuousEepromData(0x0098, 960)
    loop Untuk setiap block 16 bytes
        BLE->>Omron: Read EEPROM block
        Omron-->>BLE: 16 bytes data
    end
    
    API->>API: Parse binary → {sys, dia, bpm, ihb, mov, datetime}
    API->>BLE: endTransmission()
    BLE->>Omron: Write 0x080f000000000007
    Omron-->>BLE: End ACK (0x8f00)
    BLE->>Omron: Disconnect
    
    API-->>App: {"records": [[{sys:120, dia:80, ...}]]}
    App->>API: POST /api/measurements (simpan ke DB)
    API->>Cache: Check profile_owner_cache
    API->>DB: INSERT INTO measurements
    API-->>App: OK

    Note over U, DB: FASE 4 — Pengukuran SpO2 (ESP32)
    U->>ESP: Letakkan jari di sensor MAX30102
    ESP->>ESP: Kalkulasi SpO2, BPM, Suhu
    ESP->>API: POST /api/measurements/spo2
    
    API->>Cache: Check profile_owner_cache
    API->>DB: SELECT latest measurement (Omron data)
    DB-->>API: {sys: 120, dia: 80}
    
    API->>ML: POST /predict {bpm, spo2, sys, dia}
    ML-->>API: {"prediction": {"glucose_mg_dl": 105.2}}
    
    API->>DB: INSERT INTO spo2_measurements (+ blood_sugar)
    API-->>ESP: HTTP 200 OK

    Note over U, DB: FASE 5 — Dashboard
    U->>App: Lihat dashboard
    App->>API: GET /api/measurements/1/latest
    API->>Cache: Check latest_measurement_cache
    Cache-->>API: Cache miss (TTL 15s)
    API->>DB: SELECT ... ORDER BY datetime DESC LIMIT 1
    DB-->>API: Record
    API->>Cache: Store result
    API-->>App: {"sys": 120, "dia": 80, ...}
    
    App->>API: GET /api/measurements/1/spo2/latest
    API->>DB: SELECT ... ORDER BY datetime DESC LIMIT 1
    DB-->>API: Record
    API-->>App: {"spo2": 98.5, "blood_sugar": 105.2, ...}
```

### 3.3 Diagram Komponen Layer

```mermaid
graph LR
    subgraph "Presentation Layer"
        A1["Flutter Mobile App"]
        A2["Postman / Swagger UI"]
    end
    
    subgraph "API Layer (Routers)"
        B1["auth.py"]
        B2["profiles.py"]
        B3["measurements.py"]
    end
    
    subgraph "Cache Layer (Optimasi)"
        C0["cache.py<br/>(TTL Cache per modul)"]
    end
    
    subgraph "Business Logic Layer"
        C1["main.py<br/>(BLE endpoints)"]
        C2["omblepy.py<br/>(BLE protocol)"]
        C3["sharedDriver.py<br/>(EEPROM r/w)"]
    end
    
    subgraph "Data Access Layer"
        D1["database.py<br/>(PRAGMA tuning)"]
        D2["models.py"]
        D3["schemas.py"]
    end
    
    subgraph "Storage Layer"
        E1[("SQLite DB<br/>(WAL mode)")]
        E2["File System<br/>(CSV, JSON, uploads)"]
    end
    
    subgraph "Hardware Layer"
        F1["MAX30102_BPM_SPO2.ino<br/>(ESP32-S3 Firmware)"]
    end
    
    A1 --> B1
    A1 --> B2
    A1 --> B3
    A2 --> B1
    A2 --> B2
    A2 --> B3
    
    B1 --> C0
    B2 --> C0
    B3 --> C0
    B1 --> D1
    B2 --> D1
    B3 --> D1
    
    C1 --> C2
    C2 --> C3
    
    D1 --> E1
    D2 --> D1
    D3 --> B1
    D3 --> B2
    D3 --> B3
    C2 --> E2
    
    F1 -.->|"HTTP POST via WiFi"| B3
```

---

## 4. Struktur Direktori & Penjelasan File

```
tensimeter and max30102/
├── .env.example                # Template variabel environment
├── .gitignore                  # File yang diabaikan Git
├── requirements.txt            # Daftar dependency Python
├── README.md                   # Dokumentasi ringkas
├── readmeNEW.md                # Dokumentasi API lengkap
│
├── main.py                     # ⭐ Entry point aplikasi FastAPI
├── database.py                 # Konfigurasi engine SQLAlchemy & PRAGMA tuning
├── models.py                   # Definisi ORM model (User, Profile, Measurement, Spo2)
├── schemas.py                  # Pydantic schema validasi request/response
├── cache.py                    # ⭐ In-memory TTL Cache (user, profile, measurement)
│
├── routers/                    # API Route handlers
│   ├── __init__.py             # Package init
│   ├── auth.py                 # Register & Login (JWT + bcrypt async)
│   ├── profiles.py             # CRUD profil keluarga (+ async file upload)
│   └── measurements.py         # CRUD data pengukuran (tensi + SpO2 + ML)
│
├── omblepy.py                  # ⭐ Core BLE handler (Tx/Rx, EEPROM r/w, pairing)
├── sharedDriver.py             # ⭐ Shared driver logic (record read, ring buffer)
├── omblepy_bridge.py           # Bridge via ESP32 Serial (alternatif BLE)
├── websocket.py                # WebSocket endpoint untuk BLE real-time
│
├── deviceSpecific/             # Driver per model perangkat Omron
│   ├── hem-7155t.py            # ⭐ Driver HEM-7155T (parse binary, time sync)
│   ├── hem-6232t.py            # Driver HEM-6232T
│   ├── hem-7142t.py            # Driver HEM-7142T
│   ├── hem-7150t.py            # Driver HEM-7150T
│   ├── hem-7322t.py            # Driver HEM-7322T
│   ├── hem-7342t.py            # Driver HEM-7342T
│   ├── hem-7361t.py            # Driver HEM-7361T
│   ├── hem-7530t.py            # Driver HEM-7530T
│   ├── hem-7600t.py            # Driver HEM-7600T
│   └── hem_7142t.py            # Alias driver (underscore variant)
│
├── MAX30102_BPM_SPO2.ino       # ⭐ Firmware Arduino ESP32-S3 + MAX30102
│
├── omblepy-esp32bridge/        # Subproject: ESP32 sebagai BLE bridge
│   ├── README.md               # Dokumentasi bridge
│   ├── omblepy.py              # Versi omblepy untuk bridge
│   ├── omblepy_bridge.py       # Serial communication handler
│   ├── sharedDriver.py         # Shared driver (bridge version)
│   ├── plotCsv.py              # Plot utility
│   ├── deviceSpecific/         # Device drivers (bridge version)
│   └── esp32bridge/            # Firmware ESP32 untuk BLE bridge
│       └── esp32bridge.ino     # Firmware bridge
│
├── plotCsv.py                  # 📊 Utility: plot tekanan darah dari CSV
├── migrate_db.py               # 🔧 Migrasi DB: tambah kolom blood_sugar
├── migrate_indexes.py          # 🔧 Migrasi DB: buat index untuk performa
├── secretkey-generate.py       # 🔑 Utility: generate SECRET_KEY
├── debug_test.py               # 🧪 Script debug: test endpoint secara sequential
├── k6_stress_test.js           # 🧪 k6 Stress Test (50→200 VU ramp-up)
│
├── omron.db                    # 🗄️ File database SQLite
├── ubpm.json                   # Output JSON format UBPM
├── uploads/                    # Direktori penyimpanan foto profil
├── DOKUMENTASI_HEM7155T.md     # Dokumentasi lama
├── DOKUMENTASI_LENGKAP_080626.md # Dokumentasi lengkap sebelumnya
└── .vscode/                    # Konfigurasi VS Code
```

### Penjelasan Detail Per File

#### File Utama (Core)

| File | Baris | Fungsi |
|------|-------|--------|
| [main.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/main.py) | 371 | Entry point FastAPI. Mendaftarkan router, middleware CORS & GZip, endpoint BLE (`/scan`, `/connect-and-read`, `/latest-bp-records`), dan melakukan auto-migration kolom database saat startup. |
| [database.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/database.py) | 45 | Konfigurasi SQLAlchemy engine (`sqlite:///./omron.db`) dengan PRAGMA tuning (WAL, 64MB cache, mmap 256MB), connection pool (40+60), dan dependency injection `get_db()`. |
| [models.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/models.py) | 76 | Definisi 4 tabel ORM: `User`, `Profile`, `Measurement`, `Spo2Measurement` beserta relasi antar tabel dan composite index. |
| [schemas.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/schemas.py) | 97 | Pydantic schema untuk validasi input dan serialisasi output pada setiap endpoint API. |
| [cache.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/cache.py) | 77 | In-memory TTL Cache dengan 6 cache instance (user, user_by_id, profile, profile_owner, latest_measurement, measurements_list) dan helper invalidation. |

#### Router Files

| File | Baris | Fungsi |
|------|-------|--------|
| [auth.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/routers/auth.py) | 191 | `POST /register` — async bcrypt hash (32 thread pool), simpan user. `POST /login` — cached user lookup, async verify password, generate JWT token (exp 7 hari, HS256). Includes `CachedUser` class untuk menghindari DetachedInstanceError. |
| [profiles.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/routers/profiles.py) | 146 | `POST /` — buat profil dengan async file upload (aiofiles). `GET /{id_user}` — cached profile list (TTL 60s). `DELETE /{id_profile}` — hapus profil + file foto + invalidate cache. |
| [measurements.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/routers/measurements.py) | 301 | CRUD data tensi & SpO2 dengan caching. Pada `POST /spo2`: cached profile ownership → ambil Omron terakhir → async ML API call (singleton httpx client) → simpan hasil prediksi gula darah. |

#### BLE Layer

| File | Baris | Fungsi |
|------|-------|--------|
| [omblepy.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/omblepy.py) | 448+ | **Core BLE handler.** Class `bluetoothTxRxHandler` mengelola: Rx/Tx via 4 channel UUID, CRC check (XOR), EEPROM read/write, pairing key management, dan transmission control. Juga berisi fungsi utilitas: `scanBLEDevices()`, `appendCsv()`, `saveUBPMJson()`. |
| [sharedDriver.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/sharedDriver.py) | 142+ | **Shared device driver base class.** Mengelola: ring buffer EEPROM reading, unread records counter, time synchronization, dan binary-to-integer bit extraction. Semua device driver di `deviceSpecific/` mewarisi class ini. |
| [omblepy_bridge.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/omblepy_bridge.py) | 281+ | Alternatif handler yang menggunakan ESP32 sebagai BLE bridge via serial port (COM). Data BLE di-relay melalui serial dan di-encode/decode dengan base64. |
| [websocket.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/websocket.py) | 82 | WebSocket endpoint `ws://host:8000/ws/bp-data` untuk komunikasi BLE real-time (pairing & data reading via WebSocket alih-alih REST). |

#### Firmware

| File | Baris | Fungsi |
|------|-------|--------|
| [MAX30102_BPM_SPO2.ino](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/MAX30102_BPM_SPO2.ino) | 234 | Firmware Arduino untuk ESP32-S3. Membaca data SpO2 dan BPM dari sensor MAX30102 via I2C. Menggunakan algoritma SparkFun untuk kalkulasi SpO2 dan real-time BPM averaging. |

---

## 5. Skema Database (ERD)

### 5.1 Entity Relationship Diagram

```mermaid
erDiagram
    USERS ||--o{ PROFILES : "has many"
    USERS ||--o{ MEASUREMENTS : "has many"
    USERS ||--o{ SPO2_MEASUREMENTS : "has many"
    PROFILES ||--o{ MEASUREMENTS : "has many"
    PROFILES ||--o{ SPO2_MEASUREMENTS : "has many"

    USERS {
        INTEGER id PK "Auto Increment"
        TEXT name "Nama lengkap"
        TEXT email UK "Email unik untuk login"
        TEXT phone UK "Nomor telepon unik"
        TEXT password "Hash bcrypt"
    }

    PROFILES {
        INTEGER id PK "Auto Increment"
        INTEGER id_user FK "→ users.id"
        TEXT name "Nama profil (Ayah/Ibu/Anak)"
        INTEGER age "Umur"
        TEXT gender "Laki-laki / Perempuan"
        FLOAT tb "Tinggi badan (cm)"
        FLOAT bb "Berat badan (kg)"
        TEXT image_path "Path file foto profil"
    }

    MEASUREMENTS {
        INTEGER id PK "Auto Increment"
        INTEGER id_user FK "→ users.id"
        INTEGER id_profile FK "→ profiles.id"
        INTEGER sys "Tekanan Sistolik (mmHg)"
        INTEGER dia "Tekanan Diastolik (mmHg)"
        INTEGER bpm "Detak Jantung per Menit"
        BOOLEAN ihb "Irregular Heartbeat (0/1)"
        BOOLEAN mov "Movement Detected (0/1)"
        DATETIME datetime "Waktu pengukuran"
    }

    SPO2_MEASUREMENTS {
        INTEGER id PK "Auto Increment"
        INTEGER id_user FK "→ users.id"
        INTEGER id_profile FK "→ profiles.id"
        FLOAT spo2 "Saturasi Oksigen (%)"
        FLOAT bpm "Detak Jantung (BPM)"
        FLOAT temperature "Suhu Tubuh (°C)"
        FLOAT blood_sugar "Prediksi Gula Darah (mg/dL) — nullable"
        DATETIME datetime "Waktu pengukuran"
    }
```

### 5.2 Detail Tabel

#### Tabel `users`
| Kolom | Tipe | Constraint | Keterangan |
|-------|------|-----------|------------|
| `id` | INTEGER | PRIMARY KEY, AUTO INCREMENT | ID unik user |
| `name` | TEXT | NOT NULL | Nama lengkap |
| `email` | TEXT | UNIQUE, NOT NULL, INDEXED | Email untuk login |
| `phone` | TEXT | UNIQUE, NOT NULL, INDEXED | Nomor telepon untuk login alternatif |
| `password` | TEXT | NOT NULL | Password ter-hash (bcrypt) |

#### Tabel `profiles`
| Kolom | Tipe | Constraint | Keterangan |
|-------|------|-----------|------------|
| `id` | INTEGER | PRIMARY KEY, AUTO INCREMENT | ID unik profil |
| `id_user` | INTEGER | FOREIGN KEY → `users.id`, NOT NULL, INDEXED | Pemilik profil |
| `name` | TEXT | NOT NULL | Nama profil (misal: Ayah, Ibu) |
| `age` | INTEGER | NOT NULL | Umur |
| `gender` | TEXT | NOT NULL | Jenis kelamin |
| `tb` | FLOAT | NOT NULL | Tinggi badan (cm) |
| `bb` | FLOAT | NOT NULL | Berat badan (kg) |
| `image_path` | TEXT | NULLABLE | Path absolut file foto profil |

#### Tabel `measurements`
| Kolom | Tipe | Constraint | Keterangan |
|-------|------|-----------|------------|
| `id` | INTEGER | PRIMARY KEY, AUTO INCREMENT | ID unik record |
| `id_user` | INTEGER | FOREIGN KEY → `users.id`, NOT NULL | Pemilik data |
| `id_profile` | INTEGER | FOREIGN KEY → `profiles.id`, NOT NULL | Profil terkait |
| `sys` | INTEGER | NOT NULL | Tekanan Sistolik (mmHg) |
| `dia` | INTEGER | NOT NULL | Tekanan Diastolik (mmHg) |
| `bpm` | INTEGER | NOT NULL | Detak jantung per menit |
| `ihb` | BOOLEAN | DEFAULT FALSE | Irregular Heartbeat detected |
| `mov` | BOOLEAN | DEFAULT FALSE | Movement detected |
| `datetime` | DATETIME | DEFAULT UTC NOW, INDEXED | Waktu pengukuran |

**Composite Indexes:**
- `ix_meas_user_profile` — `(id_user, id_profile)`
- `ix_meas_profile_user_dt` — `(id_profile, id_user, datetime)` — optimal untuk query pagination per profil

#### Tabel `spo2_measurements`
| Kolom | Tipe | Constraint | Keterangan |
|-------|------|-----------|------------|
| `id` | INTEGER | PRIMARY KEY, AUTO INCREMENT | ID unik record |
| `id_user` | INTEGER | FOREIGN KEY → `users.id`, NOT NULL | Pemilik data |
| `id_profile` | INTEGER | FOREIGN KEY → `profiles.id`, NOT NULL | Profil terkait |
| `spo2` | FLOAT | NOT NULL | Saturasi oksigen (%) |
| `bpm` | FLOAT | NOT NULL | Detak jantung (BPM) |
| `temperature` | FLOAT | NOT NULL | Suhu tubuh (°C) |
| `blood_sugar` | FLOAT | NULLABLE | Prediksi gula darah dari ML (mg/dL) |
| `datetime` | DATETIME | DEFAULT UTC NOW, INDEXED | Waktu pengukuran |

**Composite Indexes:**
- `ix_spo2_user_profile` — `(id_user, id_profile)`
- `ix_spo2_profile_user_dt` — `(id_profile, id_user, datetime)` — optimal untuk query pagination per profil

---

## 6. Modul BLE Omron (omblepy)

### 6.1 Arsitektur Protokol BLE

Perangkat Omron HEM-7155T menggunakan protokol BLE GATT kustom (bukan standar *Blood Pressure Profile*) yang berkomunikasi melalui **service dan characteristic UUID spesifik**:

```
Parent Service UUID: ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b
```

#### Channel UUID Mapping

| Channel | Direction | UUID | Fungsi |
|---------|-----------|------|--------|
| TX Ch0 | Server → Device | `db5b55e0-aee7-11e1-965e-0002a5d5c51b` | Kirim command |
| TX Ch1 | Server → Device | `e0b8a060-aee7-11e1-92f4-0002a5d5c51b` | Kirim command (lanjutan) |
| TX Ch2 | Server → Device | `0ae12b00-aee8-11e1-a192-0002a5d5c51b` | Kirim command (lanjutan) |
| TX Ch3 | Server → Device | `10e1ba60-aee8-11e1-89e5-0002a5d5c51b` | Kirim command (lanjutan) |
| RX Ch0 | Device → Server | `49123040-aee8-11e1-a74d-0002a5d5c51b` | Terima response |
| RX Ch1 | Device → Server | `4d0bf320-aee8-11e1-a0d9-0002a5d5c51b` | Terima response (lanjutan) |
| RX Ch2 | Device → Server | `5128ce60-aee8-11e1-b84b-0002a5d5c51b` | Terima response (lanjutan) |
| RX Ch3 | Device → Server | `560f1420-aee8-11e1-8184-0002a5d5c51b` | Terima response (lanjutan) |
| Unlock | Bidirectional | `b305b680-aee7-11e1-a730-0002a5d5c51b` | Pairing & unlock key |

### 6.2 Format Paket Data BLE

```
┌──────────┬────────────┬──────────────┬──────────┬──────────┬─────────┬──────┐
│ Byte 0   │ Byte 1-2   │ Byte 3-4     │ Byte 5   │ Byte 6-N │ Byte N+1│Byte N+2│
│ PktSize  │ PktType    │ EEPROM Addr  │ DataLen  │ Data     │ 0x00   │ CRC  │
└──────────┴────────────┴──────────────┴──────────┴──────────┴─────────┴──────┘
```

- **PktSize**: Total ukuran paket (termasuk header 6 byte + CRC 2 byte)
- **PktType**: Tipe paket command/response
- **EEPROM Addr**: Alamat EEPROM yang dibaca/ditulis
- **DataLen**: Jumlah byte data aktual
- **CRC**: XOR checksum seluruh paket

#### Tipe Paket (Packet Types)

| Hex Code | Arah | Keterangan |
|----------|------|-----------|
| `0x0800` | TX | Start Data Readout |
| `0x8000` | RX | ACK Start Readout |
| `0x0100` | TX | Read EEPROM Block |
| `0x8100` | RX | EEPROM Read Response |
| `0x01C0` | TX | Write EEPROM Block |
| `0x81C0` | RX | EEPROM Write Response |
| `0x0F00` | TX | End Transmission |
| `0x8F00` | RX | ACK End Transmission |

### 6.3 Alur Komunikasi BLE

```mermaid
sequenceDiagram
    participant S as Server (omblepy)
    participant D as Omron HEM-7155T

    Note over S, D: 1. PAIRING (hanya sekali)
    S->>D: Write Unlock UUID: 0x02 + 0x00*16 (enter key programming)
    D-->>S: Response: 0x8200 (OK, siap program key)
    S->>D: Write Unlock UUID: 0x00 + KEY_16_BYTES
    D-->>S: Response: 0x8000 (key tersimpan)

    Note over S, D: 2. UNLOCK (setiap koneksi)
    S->>D: Write Unlock UUID: 0x01 + KEY_16_BYTES
    D-->>S: Response: 0x8100 (unlocked)

    Note over S, D: 3. START TRANSMISSION
    S->>D: TX: 0x0800000000100018
    D-->>S: RX: PktType=0x8000 (ACK)

    Note over S, D: 4. READ EEPROM (loop)
    loop Baca per block 16 bytes
        S->>D: TX: ReadBlock(addr, size=16)
        D-->>S: RX: PktType=0x8100 + data
    end

    Note over S, D: 5. END TRANSMISSION
    S->>D: TX: 0x080f000000000007
    D-->>S: RX: PktType=0x8F00 (ACK)
```

---

## 7. Device Driver (deviceSpecific)

Setiap file di folder `deviceSpecific/` mendefinisikan class `deviceSpecificDriver` yang mewarisi shared driver dari `sharedDriver.py`. Driver ini berisi konfigurasi spesifik per model perangkat Omron:

### 7.1 Konfigurasi HEM-7155T

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| `deviceEndianess` | `"big"` | Byte order untuk parsing data |
| `deviceUseLockUnlock` | `True` | Memerlukan unlock key sebelum baca data |
| `numberOfUserSlots` | `2` | Mendukung 2 user |
| `recordsPerUser` | `60` | Max 60 record per user |
| `bytesPerRecord` | `0x10` (16) | Ukuran 1 record di EEPROM |
| `eepromStartAddress` | `0x0098` | Alamat awal data di EEPROM |

### 7.2 Format Binary Record (HEM-7155T)

Setiap record 16 bytes di-parse menjadi:

| Offset (bit) | Panjang (bit) | Field | Keterangan |
|--------------|---------------|-------|------------|
| 0-7 | 8 | `sys` (high byte) | Tekanan Sistolik (+ 25 offset) |
| 8-15 | 8 | `dia` | Tekanan Diastolik |
| 16-23 | 8 | `bpm` | Detak jantung |
| 24 | 1 | `mov` | Movement detected flag |
| 25 | 1 | `ihb` | Irregular heartbeat flag |
| 32-37 | 6 | `month` | Bulan pengukuran |
| 38-42 | 5 | `day` | Tanggal |
| 43-47 | 5 | `hour` | Jam |
| 48-53 | 6 | `minute` | Menit |
| 54-59 | 6 | `second` | Detik |
| 60-67 | 8 | `year` | Tahun (+ 2000 offset) |

---

## 8. REST API Endpoints

### 8.1 Ringkasan Endpoint

| # | Method | Endpoint | Auth | Fungsi |
|---|--------|----------|------|--------|
| 1 | `GET` | `/` | ❌ | Health check server |
| 2 | `GET` | `/ui` | ❌ | Serve halaman frontend (HTML) |
| 3 | `GET` | `/scan` | ❌ | Scan perangkat BLE terdekat |
| 4 | `POST` | `/connect-and-read` | ❌ | Connect, pair/read data Omron |
| 5 | `POST` | `/latest-bp-records` | ❌ | Connect & read hanya record terbaru |
| 6 | `POST` | `/api/auth/register` | ❌ | Registrasi user baru |
| 7 | `POST` | `/api/auth/login` | ❌ | Login, mendapat JWT token |
| 8 | `POST` | `/api/profiles` | 🔒 | Buat profil baru (+ upload foto) |
| 9 | `GET` | `/api/profiles/{id_user}` | 🔒 | List semua profil milik user |
| 10 | `DELETE` | `/api/profiles/{id_profile}` | 🔒 | Hapus profil |
| 11 | `POST` | `/api/measurements` | 🔒 | Simpan data pengukuran tensi |
| 12 | `GET` | `/api/measurements/{id_profile}` | 🔒 | List riwayat tensi (desc, paginated) |
| 13 | `GET` | `/api/measurements/{id_profile}/latest` | 🔒 | Pengukuran tensi terbaru |
| 14 | `POST` | `/api/measurements/spo2` | 🔒 | Simpan data SpO2 + prediksi gula darah |
| 15 | `GET` | `/api/measurements/{id_profile}/spo2` | 🔒 | List riwayat SpO2 (desc, paginated) |
| 16 | `GET` | `/api/measurements/{id_profile}/spo2/latest` | 🔒 | Pengukuran SpO2 terbaru |

> 🔒 = Memerlukan JWT token di header `Authorization: Bearer <token>`

### 8.2 Detail Endpoint

---

#### `POST /api/auth/register`

Mendaftarkan user baru. Password di-hash menggunakan bcrypt secara **async** (offload ke thread pool).

**Request Body** (`application/json`):
```json
{
    "name": "Ardi Pradiva",
    "email": "ardi@example.com",
    "phone": "081234567890",
    "password": "password123"
}
```

**Response 200**:
```json
{ "message": "Registrasi berhasil.", "id_user": 1 }
```

**Response 400** (email/phone duplikat):
```json
{ "detail": "Email sudah terdaftar." }
```

---

#### `POST /api/auth/login`

Login dan mendapatkan JWT token. Mendukung login via **email atau nomor HP**.

**Request Body** (`application/json`):
```json
{ "email": "ardi@example.com", "password": "password123" }
```

atau:

```json
{ "phone": "081234567890", "password": "password123" }
```

**Response 200**:
```json
{
    "id_user": 1,
    "name": "Ardi Pradiva",
    "email": "ardi@example.com",
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

> JWT payload: `{ "sub": "1", "exp": <7 hari dari sekarang> }`  
> Algoritma: HS256  
> Secret: dari file `.env`

---

#### `POST /api/profiles`

Buat profil baru. Mendukung upload foto via `multipart/form-data`. File ditulis secara **async** menggunakan `aiofiles`.

**Request Body** (`multipart/form-data`):

| Key | Type | Required | Keterangan |
|-----|------|----------|------------|
| `id_user` | Text | ✅ | ID user pemilik |
| `name` | Text | ✅ | Nama profil |
| `age` | Text | ✅ | Umur |
| `gender` | Text | ✅ | Jenis kelamin |
| `tb` | Text | ✅ | Tinggi badan (cm) |
| `bb` | Text | ✅ | Berat badan (kg) |
| `image` | File | ❌ | Foto profil (jpg/png) |

**Response 200**:
```json
{
    "id": 1, "id_user": 1, "name": "Ayah",
    "age": 45, "gender": "Laki-laki",
    "tb": 170.5, "bb": 75.0,
    "image_url": "/uploads/profile_abc123.jpg"
}
```

---

#### `POST /api/measurements`

Simpan data pengukuran tekanan darah dari Flutter/client.

**Request Body** (`application/json`):
```json
{
    "id_user": 1, "id_profile": 1,
    "sys": 120, "dia": 80, "bpm": 72,
    "ihb": 0, "mov": 0,
    "datetime": "2026-06-03T15:00:00"
}
```

---

#### `POST /api/measurements/spo2`

Simpan data SpO2. **Mengintegrasikan prediksi gula darah via ML API** menggunakan singleton `httpx.AsyncClient` dengan connection pooling.

**Request Body** (`application/json`):
```json
{
    "id_user": 1, "id_profile": 1,
    "spo2": 98.5, "bpm": 75.0,
    "temperature": 36.5,
    "datetime": "2026-06-03T15:00:00"
}
```

**Proses Internal**:
1. Validasi profil milik user (cached, TTL 120s)
2. Ambil data Omron terakhir dari DB (wajib ada)
3. Kirim ke ML API: `POST http://127.0.0.1:8001/predict` dengan payload `{bpm, spo2, sys, dia}`
4. Simpan `blood_sugar` = `prediction.glucose_mg_dl` dari response ML

**Response 200**:
```json
{
    "id": 1, "id_user": 1, "id_profile": 1,
    "spo2": 98.5, "bpm": 75.0,
    "temperature": 36.5,
    "blood_sugar": 105.2,
    "datetime": "2026-06-03T15:00:00"
}
```

---

#### `GET /api/measurements/{id_profile}` & `GET /api/measurements/{id_profile}/spo2`

List riwayat pengukuran dengan **pagination**.

**Query Parameters**:

| Parameter | Type | Default | Range | Keterangan |
|-----------|------|---------|-------|------------|
| `skip` | int | 0 | ≥0 | Offset (jumlah record dilewati) |
| `limit` | int | 50 | 1-200 | Maks record per halaman |

---

#### `POST /connect-and-read`

Hubungkan ke perangkat Omron via BLE dan baca data.

**Request Body** (`application/json`):
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
| `mac_address` | string | MAC address perangkat BLE |
| `device_name` | string | Nama driver (`hem-7155t`, `hem-7322t`, dll) |
| `pairing` | bool | `true` = mode pairing, `false` = baca data |
| `new_records_only` | bool | `true` = hanya record yang belum dibaca |
| `sync_time` | bool | `true` = sinkronkan jam perangkat |
| `user_index` | int | `0` = User 1, `1` = User 2 (slot alat) |

---

## 9. Integrasi Machine Learning (Prediksi Gula Darah)

### 9.1 Alur Integrasi

```mermaid
flowchart LR
    A["POST /api/measurements/spo2<br/>Data: spo2, bpm, temp"] 
    --> B["Ambil data Omron terakhir<br/>dari DB: sys, dia"]
    --> C["Gabung payload:<br/>{bpm, spo2, sys, dia}"]
    --> D["POST ke ML API<br/>http://127.0.0.1:8001/predict"]
    --> E["Response:<br/>{glucose_mg_dl: 105.2}"]
    --> F["Simpan ke DB<br/>blood_sugar = 105.2"]
```

### 9.2 Kontrak ML API

**URL**: Dikonfigurasi via environment variable `ML_API_URL` (default: `http://127.0.0.1:8001/predict`)

**Request ke ML API** (`POST`):
```json
{
    "bpm": 75.0,
    "spo2": 98.5,
    "sys": 120,
    "dia": 80
}
```

**Expected Response dari ML API** (`200 OK`):
```json
{
    "prediction": {
        "glucose_mg_dl": 105.2
    }
}
```

> [!NOTE]
> Jika ML API tidak tersedia atau error, data SpO2 tetap disimpan ke database tetapi field `blood_sugar` akan bernilai `null`. Error hanya di-log ke console, tidak men-gagalkan request.

### 9.3 Implementasi HTTP Client (Optimasi)

Pada branch `optimasi`, ML API call menggunakan **singleton `httpx.AsyncClient`** dengan connection pooling:

```python
_ml_client = httpx.AsyncClient(
    timeout=httpx.Timeout(5.0, connect=2.0),
    limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
)
```

Keuntungan:
- **Connection reuse** — tidak perlu TCP handshake per request
- **Keep-alive** — 20 koneksi persisten ke ML API
- **Async** — tidak memblokir event loop FastAPI

---

## 10. Firmware ESP32 + MAX30102

### 10.1 Gambaran Umum

File [MAX30102_BPM_SPO2.ino](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/MAX30102_BPM_SPO2.ino) adalah firmware Arduino untuk ESP32-S3 yang membaca data dari sensor MAX30102.

### 10.2 Wiring

```
MAX30102  →  ESP32-S3
─────────────────────
VIN       →  3V3
GND       →  GND
SDA       →  GPIO 8
SCL       →  GPIO 9
```

### 10.3 Konfigurasi Sensor

| Parameter | Nilai | Keterangan |
|-----------|-------|------------|
| `ledBrightness` | 60 | Intensitas LED (0-255). Cukup terang, hemat daya |
| `sampleAverage` | 4 | Rata-rata sampel: 1, 2, 4, 8, 16, 32 |
| `ledMode` | 2 | Mode LED: 1=Red only (BPM), **2=Red+IR (BPM+SpO2)** |
| `sampleRate` | 100 | Sample rate (Hz) |
| `pulseWidth` | 411 | Lebar pulsa (µs). Lebih lebar = lebih akurat |
| `adcRange` | 4096 | Range ADC |
| `BUFFER_LENGTH` | 100 | Jumlah sampel untuk algoritma SpO2 |
| `FINGER_THRESHOLD` | 50000 | Ambang batas IR untuk deteksi jari |

### 10.4 Algoritma Pembacaan

```mermaid
flowchart TD
    A["Setup: Init I2C & MAX30102"] --> B["collectInitialSamples()<br/>100 sampel awal"]
    B --> C["Loop Utama"]
    C --> D["Geser 75 sampel lama<br/>ke awal buffer"]
    D --> E["Kumpulkan 25 sampel baru"]
    E --> F{"IR > FINGER_THRESHOLD?"}
    F -->|"Ya"| G["checkForBeat(IR)<br/>Hitung real-time BPM"]
    F -->|"Tidak"| H["Jari tidak terdeteksi"]
    G --> I["Update moving average BPM<br/>(window 4 sampel)"]
    I --> J["Serial output:<br/>red, ir, HR, SPO2"]
    H --> J
    J --> K["maxim_heart_rate_and_oxygen_saturation()<br/>Kalkulasi SpO2 dari buffer"]
    K --> C
```

### 10.5 Output Serial

Format output serial (115200 baud):

```
red=123456, ir=654321, HR=72, HRvalid=1, SPO2=98, SPO2Valid=1
```

| Field | Keterangan |
|-------|------------|
| `red` | Raw value LED merah |
| `ir` | Raw value LED inframerah |
| `HR` | Heart Rate rata-rata (BPM) |
| `HRvalid` | Flag validitas HR (0/1) |
| `SPO2` | Saturasi oksigen (%) |
| `SPO2Valid` | Flag validitas SpO2 (0/1) |

### 10.6 Cara Flash Firmware

1. Install library **SparkFun MAX3010x Pulse and Proximity Sensor Library** via Arduino Library Manager
2. Pilih board **ESP32S3 Dev Module** di Arduino IDE
3. Upload file `MAX30102_BPM_SPO2.ino`
4. Buka Serial Monitor (115200 baud)
5. Letakkan jari di atas sensor MAX30102
6. Tunggu beberapa detik sampai pembacaan stabil

---

## 11. Optimasi Performa (Branch Optimasi)

### 11.1 In-Memory TTL Cache

File [cache.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/cache.py) mendefinisikan 6 cache instance:

| Cache | Max Size | TTL | Fungsi |
|-------|----------|-----|--------|
| `user_cache` | 500 | 300s (5min) | Cache user by email/phone (login) |
| `user_by_id_cache` | 500 | 300s (5min) | Cache user by ID (JWT verification) |
| `profile_cache` | 1000 | 60s (1min) | Cache profile list per user |
| `profile_owner_cache` | 2000 | 120s (2min) | Cache profile ownership check |
| `latest_measurement_cache` | 2000 | 15s | Cache latest measurement per profile |
| `measurements_cache` | 2000 | 10s | Cache measurement list (paginated) |

Setiap cache dilindungi oleh `threading.Lock` untuk thread-safety.

### 11.2 Database PRAGMA Tuning

File [database.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/database.py) menerapkan optimasi SQLite:

| PRAGMA | Nilai | Efek |
|--------|-------|------|
| `journal_mode` | WAL | Concurrent read/write |
| `synchronous` | NORMAL | Balance safety vs speed |
| `cache_size` | -64000 (64MB) | Cache in-memory lebih besar |
| `busy_timeout` | 10000 (10s) | Retry saat lock |
| `temp_store` | MEMORY | Temp tables di RAM |
| `mmap_size` | 268435456 (256MB) | Memory-mapped I/O |
| `read_uncommitted` | 1 | Kurangi lock contention reads |
| `wal_autocheckpoint` | 1000 | Checkpoint setiap 1000 pages |

### 11.3 Async Bcrypt

Bcrypt hashing dan verification di-offload ke dedicated thread pool:

```python
_bcrypt_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=32,
    thread_name_prefix="bcrypt",
)
```

Mencegah blocking event loop FastAPI saat hashing password (operasi CPU-bound).

### 11.4 GZip Compression

```python
app.add_middleware(GZipMiddleware, minimum_size=500)
```

Mengompresi response JSON ≥500 bytes — mengurangi payload 60-80% untuk list measurement.

### 11.5 Stress Test (k6)

File [k6_stress_test.js](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/k6_stress_test.js) mendefinisikan skenario:

| Stage | Durasi | Target VU | Keterangan |
|-------|--------|-----------|------------|
| Ramp-up | 1 menit | 50 | Pemanasan |
| Sustained load | 3 menit | 200 | Beban puncak |
| Ramp-down | 1 menit | 0 | Pendinginan |

**Threshold**:
- `http_req_duration p(95) < 500ms`
- `http_req_failed rate < 5%`
- `login_duration p(95) < 300ms`

---

## 12. WebSocket

File [websocket.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/websocket.py) menyediakan endpoint WebSocket untuk komunikasi BLE real-time:

**Endpoint**: `ws://<host>:8000/ws/bp-data`

**Alur WebSocket**:
1. Client membuka koneksi WebSocket
2. Client mengirim JSON payload (mac_address, pairing flag, dll)
3. Server melakukan scan → connect → pairing/read
4. Server mengirim hasil via WebSocket
5. Koneksi tetap terbuka untuk komunikasi lanjutan

> [!WARNING]
> File `websocket.py` saat ini merupakan **kode standalone** yang belum di-import ke `main.py`. Endpoint ini perlu diintegrasikan jika ingin digunakan.

---

## 13. Utility Scripts

### 13.1 `plotCsv.py` — Visualisasi Tekanan Darah

File: [plotCsv.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/plotCsv.py)

Membuat grafik bar chart tekanan darah dari file CSV menggunakan matplotlib.

```bash
python plotCsv.py user1.csv                    # default window 7 hari
python plotCsv.py user1.csv -w 30             # window 30 hari
python plotCsv.py user1.csv -w 30 -b 7        # bin per 7 hari (rata-rata mingguan)
```

### 13.2 `secretkey-generate.py` — Generate Secret Key

File: [secretkey-generate.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/secretkey-generate.py)

```bash
python secretkey-generate.py
# Output: a3f8b2c1... silahkan paste di file .env sebagai SECRET_KEY
```

### 13.3 `migrate_db.py` — Migrasi Database (blood_sugar)

File: [migrate_db.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/migrate_db.py)

Menambahkan kolom `blood_sugar` ke tabel `spo2_measurements` (untuk database yang sudah ada sebelum fitur ML ditambahkan).

```bash
python migrate_db.py
```

### 13.4 `migrate_indexes.py` — Migrasi Index Database

File: [migrate_indexes.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/migrate_indexes.py)

Membuat 9 index pada database SQLite yang sudah ada untuk meningkatkan performa query:

```bash
python migrate_indexes.py
```

Index yang dibuat:
- `ix_users_email`, `ix_users_phone`
- `ix_profiles_id_user`
- `ix_meas_user_profile`, `ix_meas_datetime`, `ix_meas_profile_user_dt`
- `ix_spo2_user_profile`, `ix_spo2_datetime`, `ix_spo2_profile_user_dt`

Juga mengaktifkan WAL mode dan menjalankan `ANALYZE` untuk update query planner.

### 13.5 `debug_test.py` — Test Endpoint

File: [debug_test.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/debug_test.py)

Script untuk menguji endpoint secara sequential: register → login → create profile → save measurement → dll.

```bash
python debug_test.py
```

### 13.6 `k6_stress_test.js` — Stress Test

File: [k6_stress_test.js](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/k6_stress_test.js)

Stress test menggunakan k6 (load testing tool). Simulasi 50→200 virtual users.

```bash
k6 run k6_stress_test.js
# Atau dengan custom base URL:
k6 run -e BASE_URL=http://192.168.1.12:8000 k6_stress_test.js
```

---

## 14. Instalasi & Deployment

### 14.1 Langkah Instalasi

```bash
# 1. Clone repository (branch optimasi)
git clone -b optimasi https://github.com/TA-Remote-Patient-Monitoring/Tensimeter-and-MAX30102 "tensimeter and max30102"
cd "tensimeter and max30102"

# 2. (Opsional) Buat virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 3. Install dependencies
pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt

# 4. Buat file .env
copy .env.example .env
# Edit .env, isi SECRET_KEY:
python secretkey-generate.py
# Paste hasilnya ke .env

# 5. (Opsional) Migrasi index untuk performa
python migrate_indexes.py

# 6. Jalankan server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 7. Buka Swagger UI
# http://localhost:8000/docs
```

### 14.2 Konfigurasi CORS

CORS sudah dikonfigurasi di [main.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/main.py) untuk origin berikut:

```python
allow_origins=[
    "http://localhost:3000",
    "http://localhost:8081",
    "http://127.0.0.1:3000",
    "http://192.168.1.16:3000",
    "http://10.20.31.178:8000"
]
```

> [!TIP]
> Jika Flutter/app berjalan di IP berbeda, tambahkan origin-nya ke list `allow_origins` di `main.py`.

### 14.3 Auto-Migration pada Startup

Saat server pertama kali dijalankan, [main.py](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/main.py) melakukan:

1. `Base.metadata.create_all(bind=engine)` — Buat semua tabel yang belum ada
2. `ensure_sqlite_columns()` — Cek dan tambahkan kolom baru (`phone`, `age`, `gender`, `tb`, `bb`, `image_path`) jika belum ada di database lama

### 14.4 Flash Firmware ESP32

```bash
# 1. Buka Arduino IDE
# 2. File → Open → MAX30102_BPM_SPO2.ino
# 3. Tools → Board → ESP32S3 Dev Module
# 4. Tools → Port → (pilih port COM ESP32)
# 5. Sketch → Upload
# 6. Tools → Serial Monitor → 115200 baud
```

---

## 15. Konfigurasi Environment

File `.env` (lihat [.env.example](file:///c:/KULIAH/SKRIPSI/tensimeter%20and%20max30102/.env.example)):

```env
SECRET_KEY=replace-this-with-a-long-random-secret
ML_API_URL=http://127.0.0.1:8001/predict
```

| Variable | Required | Default | Keterangan |
|----------|----------|---------|------------|
| `SECRET_KEY` | ✅ Ya | *(none)* | Secret key untuk enkripsi JWT. Minimal 32 karakter hex. Server **gagal start** jika tidak diset. |
| `ML_API_URL` | ❌ Tidak | `http://127.0.0.1:8001/predict` | URL endpoint ML API untuk prediksi gula darah. |
| `LOG_LEVEL` | ❌ Tidak | `WARNING` | Level logging: DEBUG, INFO, WARNING, ERROR. |
| `BCRYPT_ROUNDS` | ❌ Tidak | `4` | Jumlah rounds bcrypt. Dev: 4 (~6ms), Production: 10 (~100ms). |

---

## 16. Alur Penggunaan End-to-End

```mermaid
flowchart TD
    START([Mulai]) --> REG["1️⃣ Register User<br/>POST /api/auth/register"]
    REG --> LOGIN["2️⃣ Login<br/>POST /api/auth/login<br/>→ Dapat JWT token & id_user"]
    LOGIN --> PROFILE["3️⃣ Buat Profil<br/>POST /api/profiles<br/>(Ayah / Ibu / Anak)"]
    PROFILE --> CHOICE{Pilih Pengukuran}
    
    CHOICE -->|"Tekanan Darah"| BP_START["4a. User ukur tensi<br/>di alat Omron"]
    BP_START --> SCAN["5a. Scan BLE<br/>GET /scan"]
    SCAN --> PAIR{"Sudah<br/>pairing?"}
    PAIR -->|"Belum"| DO_PAIR["POST /connect-and-read<br/>pairing=true"]
    DO_PAIR --> READ
    PAIR -->|"Sudah"| READ["POST /connect-and-read<br/>pairing=false"]
    READ --> SAVE_BP["POST /api/measurements<br/>Simpan data ke DB"]
    SAVE_BP --> DASHBOARD
    
    CHOICE -->|"SpO2 & Suhu"| SPO2_START["4b. User tempel jari<br/>di sensor MAX30102"]
    SPO2_START --> ESP_SEND["5b. ESP32 kirim data<br/>POST /api/measurements/spo2"]
    ESP_SEND --> ML_PRED["6b. Backend panggil ML API<br/>Prediksi gula darah"]
    ML_PRED --> SAVE_SPO2["Simpan ke DB<br/>(termasuk blood_sugar)"]
    SAVE_SPO2 --> DASHBOARD
    
    DASHBOARD["📊 Dashboard<br/>GET .../latest<br/>GET .../spo2/latest"]
    DASHBOARD --> HISTORY["📋 Riwayat<br/>GET /api/measurements/{id}<br/>GET .../spo2"]
    HISTORY --> END([Selesai])
```

---

## 17. Troubleshooting

| # | Masalah | Penyebab | Solusi |
|---|---------|----------|--------|
| 1 | `ModuleNotFoundError` | Dependency belum terinstall | `pip install --trusted-host pypi.org --trusted-host files.pythonhosted.org -r requirements.txt` |
| 2 | `RuntimeError: SECRET_KEY belum diset` | File `.env` belum dibuat/diisi | Jalankan `python secretkey-generate.py` lalu paste ke `.env` |
| 3 | `Tolong hidupkan bluetooth` | Bluetooth adapter mati/tidak ada | Nyalakan Bluetooth di Settings Windows |
| 4 | `Device not found during scan` | Omron tidak dalam mode transfer | Tekan tombol Bluetooth/transfer di alat Omron |
| 5 | `entered pairing key does not match` | Belum pairing atau pairing key berubah | Lakukan pairing ulang dengan `pairing=true` |
| 6 | `Perangkat BLE tidak menampilkan service Omron` | MAC address salah (misal pakai MAC BLESmart) | Gunakan MAC address yang benar dari hasil `/scan` |
| 7 | `Failed to connect to BLE device` | Jarak terlalu jauh atau interferensi | Dekatkan alat ke komputer (< 3 meter) |
| 8 | `Harus mengukur tekanan darah terlebih dahulu` | Belum ada data Omron untuk profil ini | Lakukan pengukuran tekanan darah Omron terlebih dahulu |
| 9 | `ML API Error` atau `Gagal menghubungi ML API` | ML service belum berjalan | Jalankan ML API di port 8001 atau pastikan `ML_API_URL` benar |
| 10 | Database error setelah update kode | Skema tabel berubah | Jalankan `python migrate_db.py` dan `python migrate_indexes.py` atau hapus `omron.db` lalu restart |
| 11 | `MAX30102 tidak terdeteksi` | Wiring I2C salah | Periksa koneksi: VIN→3V3, GND→GND, SDA→GPIO8, SCL→GPIO9 |
| 12 | SpO2 selalu 0 atau invalid | Jari tidak menempel dengan benar | Letakkan jari datar di atas sensor, tunggu 5-10 detik sampai stabil |
| 13 | `DetachedInstanceError` di auth | Cache menyimpan ORM object dari session lain | Sudah di-fix dengan `CachedUser` (plain object). Update ke branch `optimasi`. |

---

## 18. Catatan Keamanan

> [!CAUTION]
> Berikut adalah catatan penting terkait keamanan sistem yang perlu diperhatikan untuk deployment production:

| # | Aspek | Status Saat Ini | Rekomendasi |
|---|-------|----------------|-------------|
| 1 | **Password Hashing** | ✅ bcrypt via passlib (async) | Sudah aman |
| 2 | **JWT Token** | ✅ HS256 dengan SECRET_KEY | Gunakan RS256 untuk production |
| 3 | **Token Expiry** | ✅ 7 hari | Pertimbangkan refresh token |
| 4 | **Endpoint Protection** | ✅ JWT `Depends(get_current_user)` pada router | Endpoint BLE (`/scan`, `/connect-and-read`) masih publik |
| 5 | **CORS** | ⚠️ Hardcoded origins | Pindahkan ke `.env` untuk fleksibilitas |
| 6 | **File Upload** | ✅ UUID-based filename + async write | Tambahkan validasi tipe file & size limit |
| 7 | **SQL Injection** | ✅ Aman via SQLAlchemy ORM | Tidak ada raw SQL (kecuali migrate scripts) |
| 8 | **BLE Pairing Key** | ⚠️ Hardcoded `deadbeaf12341234...` | Pertimbangkan key per-device |
| 9 | **HTTPS** | ❌ Tidak ada | Gunakan reverse proxy (nginx) + SSL cert |
| 10 | **Rate Limiting** | ❌ Tidak ada | Tambahkan `slowapi` atau middleware custom |
| 11 | **Caching** | ✅ Thread-safe TTL cache | Cache poisoning minimal (data milik sendiri) |
| 12 | **bcrypt rounds** | ⚠️ Default 4 (dev mode) | Set `BCRYPT_ROUNDS=10` di production |

---

> **Dokumentasi ini di-generate berdasarkan analisis source code aktual** dari seluruh file di folder `tensimeter and max30102/` (branch `optimasi`).  
> Terakhir diperbarui: 5 Juli 2026.
