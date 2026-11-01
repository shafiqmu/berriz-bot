#!/usr/bin/env python3
"""Berriz bot API server — lightweight FastAPI wrapper.

Run on VPS:
    uvicorn berriz_api:app --host 0.0.0.0 --port 8080

Termux just calls:
    curl -X POST http://VPS_IP:8080/register -H "Content-Type: application/json" -d '{"count": 1}'
"""
import json
import os
import sys
import time
import random
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# ── import bot logic ──────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))
from berriz_auto_register import (
    CAMOFOX, API_KEY, ACCOUNTS_FILE,
    register_one, save_account, log,
)

# ── config ────────────────────────────────────────────────────────
DEFAULT_PORT = 8080
app = FastAPI(title="Berriz Auto-Register API", version="1.0.0")


# ── schemas ───────────────────────────────────────────────────────
class RegisterRequest(BaseModel):
    count: int = Field(default=1, ge=1, le=10, description="Accounts to register (1-10)")
    password: str | None = Field(default=None, description="Fixed password (default: random)")
    keep_session: bool = Field(default=False, description="Keep camofox sessions alive")


class AccountResponse(BaseModel):
    email: str
    password: str
    mailtm_password: str
    camofox_user: str
    created_at: str


# ── routes ────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.get("/accounts", response_model=list[AccountResponse])
def list_accounts():
    if not Path(ACCOUNTS_FILE).exists():
        return []
    with open(ACCOUNTS_FILE) as f:
        return json.load(f)


@app.post("/register", response_model=dict)
def register(req: RegisterRequest):
    results = []
    failed = []

    for i in range(1, req.count + 1):
        pw = req.password or f'Berriz!{random.randint(100000, 999999)}xYz'
        log(f'API: account {i}/{req.count}')
        try:
            c, account = register_one(i, pw)
            save_account(account)
            results.append(account)
            if not req.keep_session:
                c.close()
        except Exception as e:
            failed.append({"index": i, "error": str(e)})
            log(f'API: FAILED {i}: {e}')
        if i < req.count:
            time.sleep(4)

    payload = {
        "ok": len(failed) == 0,
        "registered": len(results),
        "failed": len(failed),
        "accounts": results,
        "errors": failed,
    }
    status = 200 if payload["ok"] else 422
    return JSONResponse(content=payload, status_code=status)


# ── entrypoint ────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("BERRIZ_API_PORT", DEFAULT_PORT))
    print(f"Starting Berriz API on :{port}")
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
