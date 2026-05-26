## Flowbeat BE Python

Backend Python untuk koneksi BLE Omron HEM-7155T dan pembacaan data tekanan darah melalui FastAPI.

### Koneksi / Pairing Device

1. Tekan lama tombol Bluetooth pada device sampai muncul huruf `P`.
2. Jalankan perintah berikut di terminal:

```powershell
python ./omblepy.py -p -d hem-7155t
```

3. Selama skrip berjalan, perhatikan layar tensimeter Omron Anda. Proses pemasangan berhasil jika layar monitor menunjukkan ikon berputar atau indikator lain yang menandakan pairing sedang berlangsung.

### Menjalankan API FastAPI

Jalankan backend dengan IPv4 lokal dan mode debug:

```powershell
python -m uvicorn main:app --reload --host [Alamat IPv4] --port 8000
```

Contoh:

```powershell
python -m uvicorn main:app --reload --host 192.168.1.5 --port 8000
```

### Endpoint yang Bisa Dicoba

#### `POST /latest-bp-records`

Gunakan endpoint ini untuk membaca data BP terbaru dari device.

Contoh body JSON:

```json
{
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "HEM-7155T",
  "new_records_only": false,
  "sync_time": false,
  "pairing": false,
  "user_index": 1
}
```

#### `POST /connect-and-read`

Endpoint ini membaca seluruh data yang tersedia dari device.

Contoh body JSON:

```json
{
  "mac_address": "00:5F:BF:1B:AF:01",
  "device_name": "HEM-7155T",
  "new_records_only": false,
  "sync_time": false,
  "pairing": false,
  "user_index": 0
}
```

#### `GET /scan`

Memindai device BLE yang terdeteksi di sekitar laptop.

#### `GET /`

Health check sederhana untuk memastikan backend aktif.

### Catatan

- Endpoint backend saat ini membaca parameter `mac_address`, `device_name`, `new_records_only`, `sync_time`, `pairing` dan `user_index`.
- Untuk mengganti Switch pada alat omron antara 1 dan 2 bisa diubah juga untuk `user_index`, `user_index: 0` adalah untuk switch user 1 dan `user_index: 1` adalah untuk user 2 pada alat Omron 
