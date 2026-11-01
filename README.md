# Berriz Auto-Register Bot

Bot pendaftaran akun otomatis untuk [Berriz](https://berriz.in) (Kakao Entertainment). Bisa membuat akun berapapun yang diinginkan secara otomatis, lengkap dengan verifikasi email OTP.

Fitur utama:
- **Fully automated**: email → OTP → password → terms → vote TWS (MMA2026) (~45 detik/akun)
- **API server**: kontrol dari HP via Termux atau perangkat lain
- **Disposable email**: pakai mail.tm API, tanpa perlu daftar email sendiri
- **Headless browser**: lewat camofox-browser, bypass captcha dan anti-bot

## Hasil Testing

| Akun | Status |
|------|--------|
| `7h6kmy2zys@fldubai.com` | ✅ Login verified |
| `opt1yxrrcw@fldubai.com` | ✅ Login verified |
| `186gcow9s1@fldubai.com` | ✅ Via API |

## Struktur Project

```
berriz-bot/
├── berriz_auto_register.py   # Core bot logic
├── berriz_api.py             # FastAPI server (VPS)
├── berriz_termux.py          # Client untuk Termux
├── berriz-api.service        # Systemd unit untuk auto-start
├── TERMUX_SETUP.md           # Panduan setup Termux
└── accounts.json             # Akun yang terdaftar (di-ignore git)
```

## Cara Pakai

### Opsi 1: API Server (recommended untuk Termux)

#### Di VPS

```bash
# 1. Clone repo
git clone https://github.com/shafiqmu/berriz-bot.git
cd berriz-bot

# 2. Setup venv
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn pydantic requests

# 3. Set API key camofox
export CAMOFOX_API_KEY="<key dari camofox env>"

# 4. Start server
python3 berriz_api.py
# atau: uvicorn berriz_api:app --host 0.0.0.0 --port 8000
```

API tersedia di `http://<VPS_IP>:8000`.

#### Endpoints

| Method | Path | Fungsi |
|--------|------|--------|
| GET | `/health` | Cek status API |
| GET | `/accounts` | Lihat semua akun |
| POST | `/register` | Daftar akun baru + vote TWS |
| POST | `/vote` | Vote TWS untuk akun yang sudah login |

#### Contoh Request

```bash
# Daftar 1 akun
curl -X POST http://<VPS_IP>:8000/register \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'

# Daftar 3 akun dengan password tetap
curl -X POST http://<VPS_IP>:8000/register \
  -H "Content-Type: application/json" \
  -d '{"count": 3, "password": "MyPass123!"}'
```

Response:
```json
{
  "ok": true,
  "registered": 1,
  "accounts": [
    {
      "email": "abc123@fldubai.com",
      "password": "Berriz!699903xYz",
      "mailtm_password": "MailtmPass123!",
      "created_at": "2026-11-02T02:15:32.170913"
    }
  ]
}
```

#### POST /vote

Vote TWS untuk akun yang sudah login. Butuh `camofox_user` dari `accounts.json`.

```bash
curl -X POST http://<VPS_IP>:8000/vote \
  -H "Content-Type: application/json" \
  -d '{"camofox_user": "berriz_bot_1234567890_1"}'
```

#### Auto-start dengan Systemd

```bash
# Install service
sudo cp berriz-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now berriz-api.service

# Cek status
sudo systemctl status berriz-api.service
sudo journalctl -u berriz-api.service -f
```

---

### Opsi 2: Direct CLI (langsung di VPS)

```bash
# Daftar 1 akun
python3 berriz_auto_register.py --count 1

# Daftar 5 akun
python3 berriz_auto_register.py --count 5

# Pakai password tetap
python3 berriz_auto_register.py --count 3 --password "MyPass123!"

# Jangan tutup session setelah selesai
python3 berriz_auto_register.py --count 1 --keep-session
```

---

### Opsi 3: Dari Termux (HP Android)

```bash
# 1. Install Python + requests
pkg update && pkg install python python-pip -y
pip install requests

# 2. Download client (alamat VPS sudah built-in)
wget https://raw.githubusercontent.com/shafiqmu/berriz-bot/master/berriz_termux.py

# 3. Daftar akun
python3 berriz_termux.py --count 1

# Lihat akun yang sudah ada
python3 berriz_termux.py --list

# Vote TWS untuk semua akun sekaligus
python3 berriz_termux.py --vote-all
```

Output:
```
Mengirim 1 akun ke http://129.226.216.84:8000 ...

✅ 1 akun berhasil:
  cqv6f0nxhn@fldubai.com  |  Berriz!938759xYz
```

## Cara Kerja

```
┌─────────┐     HTTP      ┌──────────┐    raw API     ┌──────────┐
│ Termux  │ ────────────► │ FastAPI  │ ─────────────► │ camofox  │
│ (HP)    │               │ (VPS)    │               │ (VPS)    │
│         │ ◄──────────── │          │ ◄───────────── │          │
│         │   JSON resp   │          │   JS evaluate │          │
└─────────┘               └──────────┘               └──────────┘
                                                         │
                                                 mail.tm API (email)
```

1. **mail.tm** — buat inbox disposable, dapat OTP dari Berriz
2. **camofox-browser** — buka browser headless, isi form step-by-step:
   - Masukkan email
   - Masukkan OTP
   - Set password
   - Accept terms (termasuk age consent modal)
3. **Akun siap** — login confirmed, simpan ke `accounts.json`

## Troubleshooting

### camofox error 500 saat buka session lama

Ini bug di Playwright storage restore. Fix sudah diaplikasikan di repo ini (`coreBundle.js` patch). Jika upgrade camofox dan bug kembali, lihat catatan di skill `camofox-browser-ops`.

### mail.tm domain berubah

Domain mail.tm rotates secara berkala. Bot otomatis ambil domain terbaru dari `/domains`. Jika gagal, cek manually:
```bash
curl -s https://api.mail.tm/domains | python3 -m json.tool
```

### Port 8000 bentrok

```bash
sudo fuser -k 8000/tcp
sudo systemctl restart berriz-api.service
```

## License

MIT
