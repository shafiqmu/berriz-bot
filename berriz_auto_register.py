#!/usr/bin/env python3
"""Berriz auto-registration bot.

Registers accounts on berriz.in using:
- mail.tm disposable inboxes (public API, no signup needed)
- camofox-browser raw HTTP API (JS evaluation + React-aware input setting)

Usage:
    python3 berriz_auto_register.py --count 1
    python3 berriz_auto_register.py --count 5 --password 'MyPass123!'

Accounts are saved to accounts.json next to this script.
"""
import argparse
import json
import os
import random
import re
import string
import sys
import time
from datetime import datetime

import requests

# ---------- config ----------
CAMOFOX = os.environ.get('CAMOFOX_URL', 'http://localhost:9377')
API_KEY = os.environ.get('CAMOFOX_API_KEY', '')
MAILTM = 'https://api.mail.tm'
MAILTM_PASSWORD = 'MailtmPass123!'
SIGNUP_URL = 'https://accounts.berriz.in/en/signup/?postRedirectUri=https%3A%2F%2Fberriz.in%2Fen'
VOTE_URL = 'https://berriz.in/en/vote/mma2026/'
ACCOUNTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'accounts.json')

H = {'Content-Type': 'application/json'}
if API_KEY:
    H['Authorization'] = f'Bearer {API_KEY}'


def log(msg):
    print(f'[{datetime.now().strftime("%H:%M:%S")}] {msg}', flush=True)


# ---------- camofox helpers ----------

class Camofox:
    def __init__(self, user_id):
        self.user = user_id
        self.tab = None
        self.h = dict(H)

    def _post(self, path, body, timeout=120):
        r = requests.post(f'{CAMOFOX}{path}', json=body, headers=self.h, timeout=timeout)
        return r

    def open(self, url):
        r = self._post('/tabs', {'userId': self.user, 'listItemId': 'berriz', 'url': url})
        data = r.json()
        if 'tabId' not in data:
            raise RuntimeError(f'tab creation failed: {data}')
        self.tab = data['tabId']
        return data

    def navigate(self, url):
        return self._post(f'/tabs/{self.tab}/navigate', {'userId': self.user, 'url': url}).json()

    def evaluate(self, expr, timeout=120):
        r = self._post(f'/tabs/{self.tab}/evaluate', {'userId': self.user, 'expression': expr}, timeout)
        data = r.json()
        if not data.get('ok'):
            raise RuntimeError(f'evaluate failed: {data}')
        return data.get('result')

    def eval_json(self, expr, timeout=120):
        return json.loads(self.evaluate(expr, timeout))

    def close(self):
        try:
            requests.delete(f'{CAMOFOX}/sessions/{self.user}', timeout=30)
        except Exception:
            pass


# ---------- React-aware page actions ----------

def set_input(c, selector, value):
    expr = (
        "(() => { const el = document.querySelector(%s); if (!el) return 'NOT_FOUND';"
        " const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;"
        " setter.call(el, %s);"
        " el.dispatchEvent(new Event('input', {bubbles: true}));"
        " el.dispatchEvent(new Event('change', {bubbles: true}));"
        " return 'SET:' + el.value.length; })()" % (json.dumps(selector), json.dumps(value))
    )
    return c.evaluate(expr)


def click_button(c, text, exact=True):
    expr = (
        "(() => { const btns = [...document.querySelectorAll('button, a, [role=\"button\"]')];"
        " const b = btns.find(x => %s);"
        " if (!b) return 'NOT_FOUND'; if (b.disabled) return 'DISABLED';"
        " b.click(); return 'CLICKED'; })()"
        % (f"x.innerText.trim() === {json.dumps(text)}" if exact else f"x.innerText.includes({json.dumps(text)})")
    )
    return c.evaluate(expr)


def click_selector(c, selector):
    expr = (
        "(() => { const el = document.querySelector(%s); if (!el) return 'NOT_FOUND';"
        " el.click(); return 'CLICKED'; })()" % json.dumps(selector)
    )
    return c.evaluate(expr)


def page_state(c):
    return c.eval_json(
        "JSON.stringify({url: location.href, h1: (document.querySelector('h1')||{}).innerText || ''})"
    )


def handle_under16_modal(c):
    """If the 'Are you under 16?' modal is up, answer No (adult account)."""
    modal = c.evaluate(
        "(() => { const dlg = [...document.querySelectorAll('[class*=\"modal\"]')]"
        ".find(d => (d.innerText||'').includes('under 16'));"
        " return dlg ? 'UP' : 'GONE'; })()"
    )
    if modal == 'UP':
        click_button(c, 'No')
        time.sleep(1)
        return True
    return False


# ---------- mail.tm ----------

def mailtm_create_inbox():
    dom = requests.get(f'{MAILTM}/domains', timeout=30).json()
    domain = dom['hydra:member'][0]['domain']
    local = ''.join(random.choices(string.ascii_lowercase + string.digits, k=10))
    addr = f'{local}@{domain}'
    r = requests.post(f'{MAILTM}/accounts', json={'address': addr, 'password': MAILTM_PASSWORD}, timeout=30)
    if r.status_code not in (200, 201):
        raise RuntimeError(f'mail.tm account creation failed: {r.status_code} {r.text[:200]}')
    return addr


def mailtm_wait_otp(addr, timeout_s=150):
    token = requests.post(f'{MAILTM}/token', json={'address': addr, 'password': MAILTM_PASSWORD}, timeout=30).json().get('token')
    headers = {'Authorization': f'Bearer {token}'}
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msgs = requests.get(f'{MAILTM}/messages', headers=headers, timeout=30).json()
        for m in msgs.get('hydra:member', []):
            if 'berriz' not in (m.get('from', {}).get('address') or '').lower():
                continue
            full = requests.get(f'{MAILTM}/messages/{m["id"]}', headers=headers, timeout=30).json()
            html = ' '.join(full.get('html', []))
            code = extract_otp(html)
            if code:
                return code
        time.sleep(3)
    return None


def extract_otp(html):
    m = re.search(r'color:#FF1991[^>]*>\s*(\d{4,8})\s*<', html)
    if m:
        return m.group(1)
    for m in re.finditer(r'>\s*(\d{6})\s*<', html):
        return m.group(1)
    return None


# ---------- main flow ----------

def register_one(idx, password):
    """Register a single Berriz account. Returns account dict or raises."""
    user_id = f'berriz_bot_{int(time.time())}_{idx}'
    c = Camofox(user_id)
    log(f'[{idx}] session {user_id} — creating tab')
    c.open(SIGNUP_URL)
    time.sleep(3)

    state = page_state(c)
    assert 'signup' in state['url'], f'unexpected page: {state}'
    log(f'[{idx}] at signup page')

    # 1) email
    addr = mailtm_create_inbox()
    log(f'[{idx}] inbox: {addr}')
    set_input(c, 'input[name=email]', addr)
    time.sleep(0.5)
    r = click_button(c, 'Continue')
    if r != 'CLICKED':
        raise RuntimeError(f'email continue failed: {r}')
    time.sleep(3)

    state = page_state(c)
    assert '/signup/email' in state['url'], f'no OTP page: {state}'
    log(f'[{idx}] waiting for OTP...')

    # 2) OTP
    code = mailtm_wait_otp(addr)
    if not code:
        raise RuntimeError('OTP not received in time')
    log(f'[{idx}] OTP: {code}')
    set_input(c, 'input[name=otpCode]', code)
    time.sleep(0.8)
    r = click_button(c, 'Continue')
    if r != 'CLICKED':
        raise RuntimeError(f'otp continue failed: {r}')
    time.sleep(3.5)

    state = page_state(c)
    assert '/signup/password' in state['url'], f'no password page: {state}'
    log(f'[{idx}] password page')

    # 3) password
    set_input(c, 'input[name=newPassword]', password)
    set_input(c, 'input[name=newPasswordConfirm]', password)
    time.sleep(0.8)
    r = click_button(c, 'Continue')
    if r != 'CLICKED':
        raise RuntimeError(f'password continue failed: {r}')
    time.sleep(3.5)

    state = page_state(c)
    assert 'terms-of-service' in state['url'], f'no terms page: {state}'
    log(f'[{idx}] terms page')

    # 4) terms: master + age checkboxes (age triggers under-16 modal)
    click_selector(c, 'input[name=allTermsAccepted]')
    time.sleep(0.8)
    # age: click, handle modal, retry until checked
    for attempt in range(5):
        age_checked = c.evaluate("document.querySelector('input[name=\"hasAgreedToAgeLimit\"]')?.checked === true")
        if age_checked:
            break
        click_selector(c, 'input[name=hasAgreedToAgeLimit]')
        time.sleep(1)
        handle_under16_modal(c)
        time.sleep(0.8)

    verify = c.eval_json(
        "JSON.stringify({age: document.querySelector('input[name=\"hasAgreedToAgeLimit\"]')?.checked,"
        " contDisabled: [...document.querySelectorAll('button')].find(b => b.innerText.trim() === 'Continue')?.disabled})"
    )
    if not verify.get('age') or verify.get('contDisabled') is not False:
        raise RuntimeError(f'terms checkboxes failed: {verify}')
    log(f'[{idx}] terms accepted — submitting')

    r = click_button(c, 'Continue')
    if r != 'CLICKED':
        raise RuntimeError(f'terms continue failed: {r}')
    time.sleep(6)

    state = page_state(c)
    if '/signup/complete' not in state['url']:
        raise RuntimeError(f'signup did not complete: {state}')
    log(f'[{idx}] SUCCESS: {state["h1"]}')

    # dismiss "declined promotional notifications" modal
    click_button(c, 'OK')
    time.sleep(1)

    # 5) vote for TWS on MMA2026
    vote_for_tws(c)

    account = {
        'email': addr,
        'password': password,
        'mailtm_password': MAILTM_PASSWORD,
        'camofox_user': user_id,
        'created_at': datetime.now().isoformat(),
    }
    return c, account


def save_account(account):
    data = []
    if os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE) as f:
            try:
                data = json.load(f)
            except Exception:
                data = []
    data.append(account)
    with open(ACCOUNTS_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def vote_for_tws(c):
    """Navigate to MMA2026 voting page and vote for TWS."""
    log('voting for TWS on MMA2026...')
    c.navigate(VOTE_URL)
    time.sleep(3)

    # Find TWS button and click
    result = c.evaluate("""(() => {
        const btn = [...document.querySelectorAll('button')].find(b => b.innerText.includes('TWS'));
        if (!btn) return 'TWS_NOT_FOUND';
        btn.click();
        return 'CLICKED';
    })()""")
    if result != 'CLICKED':
        raise RuntimeError(f'failed to click TWS: {result}')

    time.sleep(2)

    # Verify vote registered
    pressed = c.evaluate("""(() => {
        const btn = [...document.querySelectorAll('button')].find(b => b.innerText.includes('TWS'));
        return btn ? btn.getAttribute('aria-pressed') : 'NOT_FOUND';
    })()""")
    if pressed != 'true':
        raise RuntimeError(f'TWS vote not registered: aria-pressed={pressed}')

    log('✅ TWS vote confirmed (aria-pressed=true)')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--count', type=int, default=1, help='how many accounts to register')
    ap.add_argument('--password', default=None, help='password for all accounts (default: random strong)')
    ap.add_argument('--keep-session', action='store_true', help='do not close camofox sessions (keep logged-in browser state)')
    args = ap.parse_args()

    password = args.password or f'Berriz!{random.randint(1000, 9999)}xYz'
    done, failed = 0, 0
    for i in range(1, args.count + 1):
        log(f'=== account {i}/{args.count} ===')
        pw = password if args.password else f'Berriz!{random.randint(100000, 999999)}xYz'
        try:
            c, account = register_one(i, pw)
            save_account(account)
            done += 1
            log(f'[{i}] saved to {ACCOUNTS_FILE}')
            if not args.keep_session:
                c.close()
                log(f'[{i}] session closed (state persisted to ~/.camofox/profiles)')
        except Exception as e:
            failed += 1
            log(f'[{i}] FAILED: {e}')
        if i < args.count:
            time.sleep(4)

    log(f'=== done: {done} ok, {failed} failed ===')
    return 0 if failed == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
