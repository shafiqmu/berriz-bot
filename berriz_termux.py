#!/data/data/com.termux/files/usr/bin/python3
"""Berriz bot — Termux client.

Kirim request ke API server di VPS, tidak butuh camofox/mail.tm di Termux.
Cukup butuh: requests (pip install requests)
"""
import argparse
import json
import os
import sys

try:
    import requests
except ImportError:
    sys.exit("Butuh requests: pip install requests")


API_URL = os.environ.get("BERRIZ_API", "http://129.226.216.84:8000")


def register(count=1, password=None):
    payload = {"count": count}
    if password:
        payload["password"] = password

    print(f"Mengirim {count} akun ke {API_URL} ...")
    r = requests.post(
        f"{API_URL}/register",
        json=payload,
        timeout=300,  # ~34s per akun + buffer
    )
    r.raise_for_status()
    data = r.json()

    if data["ok"]:
        print(f"\n✅ {data['registered']} akun berhasil:")
        for acc in data["accounts"]:
            print(f"  {acc['email']}  |  {acc['password']}")
    else:
        print(f"\n⚠️  {data['registered']} ok, {data['failed']} gagal:")
        for err in data["errors"]:
            print(f"  #{err['index']}: {err['error']}")

    return data


def list_accounts():
    r = requests.get(f"{API_URL}/accounts", timeout=30)
    r.raise_for_status()
    accounts = r.json()
    if not accounts:
        print("Belum ada akun.")
        return
    print(f"\n{len(accounts)} akun terdaftar:")
    for i, a in enumerate(accounts, 1):
        print(f"  {i}. {a['email']}  |  {a['password']}  |  {a['created_at'][:10]}")


def vote_all():
    print(f"Mengambil daftar akun dari {API_URL} ...")
    r = requests.get(f"{API_URL}/accounts", timeout=30)
    r.raise_for_status()
    accounts = r.json()
    if not accounts:
        print("Belum ada akun.")
        return

    print(f"Found {len(accounts)} akun. Mulai voting TWS...")
    ok, fail = 0, 0
    for a in accounts:
        user = a.get('camofox_user')
        if not user:
            print(f"  skip {a['email']} (no camofox_user)")
            continue
        try:
            r = requests.post(f"{API_URL}/vote", json={"camofox_user": user}, timeout=180)
            r.raise_for_status()
            print(f"  ✅ {a['email']} voted")
            ok += 1
        except Exception as e:
            print(f"  ❌ {a['email']} failed: {e}")
            fail += 1
    print(f"\nSelesai: {ok} ok, {fail} gagal")


def main():
    ap = argparse.ArgumentParser(description="Berriz bot client (Termux)")
    ap.add_argument("--count", type=int, default=1, help="Jumlah akun (default: 1)")
    ap.add_argument("--password", default=None, help="Password tetap (default: random)")
    ap.add_argument("--list", action="store_true", help="Lihat akun yang sudah ada")
    ap.add_argument("--vote-all", action="store_true", help="Vote TWS untuk semua akun")
    ap.add_argument("--api", default=API_URL, help="API server URL")
    args = ap.parse_args()

    if args.list:
        list_accounts()
    elif args.vote_all:
        vote_all()
    else:
        register(args.count, args.password)


if __name__ == "__main__":
    main()
