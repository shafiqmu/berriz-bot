# Berriz Bot — Termux Setup

API server sudah running di VPS (`129.226.216.84:8000`).

## Di Termux (1x setup)

```bash
# 1. Install Python + requests
pkg update && pkg install python python-pip -y
pip install requests

# 2. Download client
wget https://raw.githubusercontent.com/shafiqmu/berriz-bot/master/berriz_termux.py
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

# Vote TWS untuk semua akun sekaligus
python3 berriz_termux.py --vote-all
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
