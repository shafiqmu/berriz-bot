# Berriz Bot — Termux Setup

API server sudah running di VPS (`129.226.216.84:8000`).

## Di Termux (1x setup)

```bash
# 1. Install Python + requests
pkg update && pkg install python python-pip -y
pip install requests

# 2. Download client script
# (kirim file berriz_termux.py ke Termux via scp/termux-setup-storage/copy-paste)

# 3. Set VPS IP (ganti dengan IP VPS kamu)
export BERRIZ_API="http://129.226.216.84:8000"
```

## Pakai

```bash
# Daftar 1 akun
python3 berriz_termux.py

# Daftar 5 akun
python3 berriz_termux.py --count 5

# Pakai password tetap
python3 berriz_termux.py --count 3 --password "MyPass123!"

# Lihat akun yang sudah ada
python3 berriz_termux.py --list
```

## Di VPS (admin)

```bash
# Cek status API
sudo systemctl status berriz-api.service

# Lihat log
sudo journalctl -u berriz-api.service -f

# Restart
sudo systemctl restart berriz-api.service

# Stop
sudo systemctl stop berriz-api.service
```

API akan auto-start saat boot VPS.
