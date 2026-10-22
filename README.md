# ChatGPT Session Guard 🛡️

A lightweight, browserless watchdog built with `curl_cffi` to monitor active ChatGPT account sessions and immediately evict unauthorized devices.

No Selenium, no Puppeteer, and no GUI browser required. Uses TLS fingerprint impersonation (`impersonate="chrome124"`) to communicate directly with ChatGPT's internal backend endpoints.

---

## Features

- **Browserless & Headless:** Runs anywhere (Desktop or Linux VPS/Server).
- **Session Pinning (`--pin`):** Snapshot your trusted devices into `allowed_sessions.json`.
- **Instant Eviction (`--watch`):** Automatically detects and revokes any new login not present in your baseline.
- **Multiple Auth Methods:**
  - Auto-reads local Firefox session cookies (`cookies.sqlite`).
  - Accepts raw cookie header strings (`CHATGPT_COOKIE`).
  - Accepts Bearer Access Tokens directly (`CHATGPT_ACCESS_TOKEN`).
- **Granular Controls:** Whitelist by `session_id`, `device_model`, or keep the supervisor session alive.

---

## Authentication Setup

To run on a server, get your token using either method below:

### Method 1: Get `CHATGPT_ACCESS_TOKEN` (Fastest)
1. Open [chatgpt.com](https://chatgpt.com) in browser and log in.
2. Open a new tab and go to: `https://chatgpt.com/api/auth/session`
3. Copy the string inside `"accessToken": "..."`.
4. Run:
   ```bash
   export CHATGPT_ACCESS_TOKEN="ey..."
   ```

*Or run this in browser DevTools Console (F12) to copy directly to clipboard:*
```javascript
fetch('/api/auth/session').then(r=>r.json()).then(d=>copy(d.accessToken))
```

### Method 2: Get `CHATGPT_COOKIE`
1. Open [chatgpt.com](https://chatgpt.com) and press `F12`.
2. Go to **Storage** (Firefox) or **Application** (Chrome) -> **Cookies** -> `https://chatgpt.com`.
3. Copy the value of `__Secure-next-auth.session-token`.
4. Run:
   ```bash
   export CHATGPT_COOKIE="__Secure-next-auth.session-token=your_cookie_value"
   ```

---

## Installation

```bash
git clone https://github.com/<your-username>/chatgpt-session-guard.git
cd chatgpt-session-guard
pip install -e .
# or
pip install curl-cffi
```

---

## Quick Start

### 1. Pin Trusted Devices
Run this while logged in to your approved devices:

```bash
python -m chatgpt_guard --pin
```
This saves an inventory of your current sessions into `allowed_sessions.json`.

### 2. Inspect Active Sessions
```bash
python -m chatgpt_guard --list
```
Displays all devices, highlighting which are authorized and which will be evicted.

### 3. Start Continuous Watchdog
```bash
python -m chatgpt_guard --watch --interval 10
```
Runs a loop checking every 10 seconds. Any unpinned device that signs in will be kicked off immediately.

---

## Running on a Server / VPS (No Browser)

On a remote headless server, provide authentication via environment variables or `config.json`:

### Option A: Environment Variables
```bash
export CHATGPT_COOKIE="__Secure-next-auth.session-token=your_token_here; ..."
# or
export CHATGPT_ACCESS_TOKEN="ey..."

python -m chatgpt_guard --watch
```

### Option B: `config.json`
Copy `config.example.json` to `config.json`:
```json
{
  "cookie_string": "__Secure-next-auth.session-token=...",
  "interval": 15,
  "allowed_file": "allowed_sessions.json",
  "allowed_identifiers": ["SM-A715F", "Computer"]
}
```

---

## Running as a Linux Systemd Service

Create `/etc/systemd/system/chatgpt-guard.service`:

```ini
[Unit]
Description=ChatGPT Session Guard Watchdog
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/chatgpt-session-guard
Environment="CHATGPT_COOKIE=your_cookie_here"
ExecStart=/path/to/venv/bin/python -m chatgpt_guard --watch --interval 15
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now chatgpt-guard
```

---

## License
MIT
