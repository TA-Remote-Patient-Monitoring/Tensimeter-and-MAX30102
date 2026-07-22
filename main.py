from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from bleak import BleakClient, BleakScanner
from omblepy import bluetoothTxRxHandler, scanBLEDevices, appendCsv, saveUBPMJson
import importlib.util
import logging
import os
import datetime
import sqlite3
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
import pusher

pusher_client = pusher.Pusher(
  app_id=os.getenv("PUSHER_APP_ID", "local"),
  key=os.getenv("PUSHER_KEY", "local"),
  secret=os.getenv("PUSHER_SECRET", "local"),
  cluster=os.getenv("PUSHER_CLUSTER", "mt1"),
  ssl=True
)


# ── TAMBAHAN BARU ──────────────────────────────────────────
from database import engine, Base
import models
from routers import auth, profiles, measurements, dashboard, notes, doctor

Base.metadata.create_all(bind=engine)  # buat tabel otomatis saat start


def ensure_sqlite_columns() -> None:
    db_path = os.path.join(os.path.dirname(__file__), "omron.db")
    if not os.path.exists(db_path):
        return

    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(users)")
        user_columns = {row[1] for row in cursor.fetchall()}
        if "phone" not in user_columns:
            cursor.execute("ALTER TABLE users ADD COLUMN phone TEXT")

        cursor.execute("PRAGMA table_info(profiles)")
        profile_columns = {row[1] for row in cursor.fetchall()}
        if "age" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN age INTEGER")
        if "gender" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN gender TEXT")
        if "tb" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN tb FLOAT")
        if "bb" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN bb FLOAT")
        if "image_path" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN image_path TEXT")
        if "uuid" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN uuid TEXT")
        if "first_name" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN first_name TEXT")
        if "last_name" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN last_name TEXT")
        if "phone_number" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN phone_number TEXT")
        if "date_of_birth" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN date_of_birth TEXT")
        if "address" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN address TEXT")
        if "created_at" not in profile_columns:
            cursor.execute("ALTER TABLE profiles ADD COLUMN created_at DATETIME")

        cursor.execute("PRAGMA table_info(measurements)")
        measurement_columns = {row[1] for row in cursor.fetchall()}
        if "status" not in measurement_columns:
            cursor.execute("ALTER TABLE measurements ADD COLUMN status TEXT")
        if "device" not in measurement_columns:
            cursor.execute("ALTER TABLE measurements ADD COLUMN device TEXT")

        conn.commit()
    finally:
        conn.close()


ensure_sqlite_columns()
# ───────────────────────────────────────────────────────────

LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.WARNING),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

json_path      = os.path.join('ubpm.json')
logger         = logging.getLogger("omblepy")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.WARNING))
bleClient      = None
deviceSpecific = None
ble_client     = None

app = FastAPI()

# ── GZip Compression ───────────────────────────────────────
# Kompresi response JSON besar (measurement lists) — mengurangi payload 60-80%
app.add_middleware(GZipMiddleware, minimum_size=500)

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:8081",
        "http://127.0.0.1:3000",
        "http://192.168.1.16:3000",
        "http://10.20.31.178:8000",
        "http://localhost:3001"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ── Daftarkan router baru ──────────────────────────────────
app.include_router(auth.router,         prefix="/api/auth",         tags=["Auth"])
app.include_router(profiles.router,     prefix="/api/profiles",     tags=["Profiles"])
app.include_router(measurements.router, prefix="/api/measurements", tags=["Measurements"])
app.include_router(dashboard.router,    prefix="/api",              tags=["Dashboard"])
app.include_router(notes.router,        prefix="/api",              tags=["Notes"])
app.include_router(doctor.router,       prefix="/api",              tags=["Doctor"])

from fastapi import Form
@app.post("/api/broadcasting/auth")
@app.post("/broadcasting/auth")
def pusher_auth(socket_id: str = Form(...), channel_name: str = Form(...)):
    # Simply authorize everything for now (Laravel equivalent of Public/Private channel bypass)
    auth = pusher_client.authenticate(channel=channel_name, socket_id=socket_id)
    return auth
# ───────────────────────────────────────────────────────────


# ── Model input (tidak diubah) ─────────────────────────────
class BLEDevice(BaseModel):
    mac_address: str
    device_name: str

class ReadRecordsInput(BaseModel):
    mac_address      : str
    new_records_only : bool = False
    sync_time        : bool = False
    device_name      : str

class ConnectAndReadInput(BaseModel):
    mac_address      : str
    device_name      : str
    new_records_only : bool
    sync_time        : bool
    pairing          : bool
    user_index       : int = 0  # 0 = user 1, 1 = user 2

RX_CHANNEL_UUIDS = [
    "49123040-aee8-11e1-a74d-0002a5d5c51b",
    "4d0bf320-aee8-11e1-a0d9-0002a5d5c51b",
    "5128ce60-aee8-11e1-b84b-0002a5d5c51b",
    "560f1420-aee8-11e1-8184-0002a5d5c51b",
]

PARENT_SERVICE_UUID = "ecbe3980-c9a2-11e1-b1bd-0002a5d5c51b"


def load_device_driver(device_name: str):
    normalized_name = device_name.strip().strip("'").strip('"').lower()
    device_specific_dir = os.path.join(os.path.dirname(__file__), "deviceSpecific")

    candidate_names = []
    for candidate in [normalized_name, normalized_name.replace("_", "-"), normalized_name.replace("-", "_")]:
        if candidate not in candidate_names:
            candidate_names.append(candidate)

    for candidate_name in candidate_names:
        module_path = os.path.join(device_specific_dir, f"{candidate_name}.py")
        if not os.path.exists(module_path):
            continue

        module_spec = importlib.util.spec_from_file_location(
            f"deviceSpecific.{candidate_name.replace('-', '_')}",
            module_path,
        )
        if module_spec is None or module_spec.loader is None:
            continue

        module = importlib.util.module_from_spec(module_spec)
        module_spec.loader.exec_module(module)
        return module.deviceSpecificDriver()

    raise HTTPException(
        status_code=400,
        detail=f"Device driver tidak ditemukan untuk {device_name}",
    )


def validate_omron_services(client: BleakClient, device_name: str) -> None:
    services = getattr(client, "services", None)
    service_uuids = [] if services is None else [service.uuid for service in services]

    if PARENT_SERVICE_UUID not in service_uuids:
        logger.info(f"Looking for uuid {PARENT_SERVICE_UUID} on {device_name}.")
        for service_uuid in service_uuids:
            logger.info(f"Service uuid : {service_uuid}.")
        raise HTTPException(
            status_code=400,
            detail=(
                "Perangkat BLE yang tersambung tidak menampilkan service Omron yang diperlukan. "
                "Pastikan MAC yang dipakai benar-benar milik HEM-7155T, bukan nama iklan BLESmart."
            ),
        )


def log_omron_characteristics(client: BleakClient) -> None:
    services = getattr(client, "services", None)
    if not services:
        logger.debug("No GATT services available to inspect.")
        return

    for service in services:
        if service.uuid == PARENT_SERVICE_UUID:
            logger.debug("Omron parent service characteristics:")
            for characteristic in service.characteristics:
                logger.debug(
                    "  char uuid=%s handle=%s props=%s",
                    characteristic.uuid,
                    getattr(characteristic, "handle", "n/a"),
                    getattr(characteristic, "properties", []),
                )


# ── Route lama (tidak diubah sama sekali) ──────────────────
@app.get("/")
def read_root():
    return {"message": "Omron BLE Python Backend is running"}


@app.get("/ui")
def read_ui():
    ui_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    return FileResponse(ui_path)


@app.post("/connect-and-read")
async def connect_and_read(data: ConnectAndReadInput):
    """
    Menghubungkan ke perangkat Omron, membaca data, dan menyimpannya ke CSV/JSON.
    - pairing: Jika True, hanya melakukan pairing.
    - new_records_only: Jika True, hanya membaca catatan baru.
    - sync_time: Jika True, menyinkronkan waktu perangkat.
    """
    try:
        devices = await BleakScanner.discover()
        selected_device = next(
            (dev for dev in devices if dev.address == data.mac_address), None
        )
        if not selected_device:
            raise HTTPException(status_code=404, detail="Device not found during scan.")

        client = BleakClient(selected_device.address)
        print("Device: ", selected_device.address, selected_device.name)

        try:
            await client.connect()
            if not client.is_connected:
                raise HTTPException(status_code=500, detail="Failed to connect to the BLE device.")

            await asyncio.sleep(1.0)  # beri waktu Windows siapkan GATT setelah connect

            services = getattr(client, "services", None) or []
            logger.debug(
                "Connected services for %s: %s",
                selected_device.address,
                [service.uuid for service in services],
            )
            log_omron_characteristics(client)

            validate_omron_services(client, selected_device.name or data.device_name)

            bluetoothTxRxObj = bluetoothTxRxHandler(client)
            dev_driver       = load_device_driver(data.device_name)

            if data.pairing:
                if dev_driver.deviceUseLockUnlock:
                    await bluetoothTxRxObj.writeNewUnlockKey()
                await bluetoothTxRxObj.startTransmission()
                await bluetoothTxRxObj.endTransmission()
                return {"message": "Pairing sucessful."}
            else:
                # unlock dengan pairing key sebelum readout
                await bluetoothTxRxObj.unlockWithUnlockKey()
                await bluetoothTxRxObj.startTransmission()
                records = await dev_driver.getRecords(
                    btobj            = bluetoothTxRxObj,
                    useUnreadCounter = data.new_records_only,
                    syncTime         = data.sync_time,
                )
                await bluetoothTxRxObj.endTransmission()
                appendCsv(records)
                saveUBPMJson(records)
                return {
                    "message"     : "Data read successfully.",
                    "mac_address" : selected_device.address,
                    "device_name" : selected_device.name,
                    "records"     : records
                }
        finally:
            if client.is_connected:
                await client.disconnect()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


@app.get("/scan")
async def scanBLEDevices():
    """Scan perangkat BLE tanpa input interaktif."""
    from bleak import BleakScanner
    try:
        print("[BLE] Starting BLE scan (timeout=10s)...")
        devices = await BleakScanner.discover(timeout=10)
        print(f"[BLE] Scan complete. Found {len(devices)} raw devices.")
        result = []
        for idx, dev in enumerate(devices):
            name = dev.name or "Unknown"
            print(f"[BLE]   Device {idx}: name={name}, mac={dev.address}, rssi={dev.rssi}")
            result.append({"id": idx, "mac": dev.address, "name": name, "rssi": dev.rssi})
        return {"devices": result, "message": "Perangkat BLE berhasil dipindai"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[SCAN] ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Tolong hidupkan bluetooth: {str(e)}")


@app.post("/latest-bp-records")
async def connect_and_read_latest(data: ConnectAndReadInput):
    """
    Menghubungkan ke perangkat Omron dan hanya membaca data pengukuran terbaru.
    - pairing: Jika True, hanya melakukan pairing.
    - sync_time: Jika True, menyinkronkan waktu perangkat.
    """
    try:
        devices = await BleakScanner.discover()
        selected_device = next(
            (dev for dev in devices if dev.address == data.mac_address), None
        )
        if not selected_device:
            raise HTTPException(status_code=404, detail="Device not found during scan.")

        client = BleakClient(selected_device.address)
        print("Device: ", selected_device.address, selected_device.name)

        try:
            await client.connect()
            if not client.is_connected:
                raise HTTPException(status_code=500, detail="Failed to connect to the BLE device.")

            await asyncio.sleep(1.0)  # beri waktu Windows siapkan GATT setelah connect

            services = getattr(client, "services", None) or []
            logger.debug(
                "Connected services for %s: %s",
                selected_device.address,
                [service.uuid for service in services],
            )
            log_omron_characteristics(client)

            validate_omron_services(client, selected_device.name or data.device_name)

            bluetoothTxRxObj = bluetoothTxRxHandler(client)
            dev_driver       = load_device_driver(data.device_name)

            if data.pairing:
                if dev_driver.deviceUseLockUnlock:
                    await bluetoothTxRxObj.writeNewUnlockKey()
                await bluetoothTxRxObj.startTransmission()
                await bluetoothTxRxObj.endTransmission()
                return {"message": "Pairing successful."}
            else:
                # unlock dengan pairing key sebelum readout
                await bluetoothTxRxObj.unlockWithUnlockKey()
                await bluetoothTxRxObj.startTransmission()
                records = await dev_driver.getRecords(
                    btobj            = bluetoothTxRxObj,
                    useUnreadCounter = data.new_records_only,
                    syncTime         = data.sync_time,
                )
                await bluetoothTxRxObj.endTransmission()

                if not records:
                    raise HTTPException(status_code=404, detail="No records found.")

                user_idx = max(0, min(data.user_index, len(records) - 1))
                latest_record             = records[user_idx][-1] if records[user_idx] else None
                if not latest_record:
                    raise HTTPException(status_code=404, detail="No records found for this user.")
                latest_record['datetime'] = datetime.datetime.now()
                return {
                    "message"       : "Newest record read with success.",
                    "mac_address"   : selected_device.address,
                    "device_name"   : selected_device.name,
                    "latest_record" : latest_record
                }
        finally:
            if client.is_connected:
                await client.disconnect()

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")