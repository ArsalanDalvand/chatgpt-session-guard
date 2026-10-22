import os
import shutil
import sqlite3
import time
from typing import Dict, List, Optional
from curl_cffi import requests

class ChatGPTClient:
    """ChatGPT Internal API Client with TLS impersonation."""

    def __init__(
        self,
        access_token: Optional[str] = None,
        cookie_string: Optional[str] = None,
        firefox_profile_path: Optional[str] = None,
        impersonate: str = "chrome124",
    ):
        self.access_token = access_token
        self.cookie_string = cookie_string
        self.firefox_profile_path = firefox_profile_path
        self.impersonate = impersonate
        self.session = requests.Session(impersonate=impersonate)
        self.account_id = ""
        self.last_auth_time = 0.0

    def _load_firefox_cookies(self) -> Dict[str, str]:
        path = self.firefox_profile_path
        if not path:
            default_base = os.path.expanduser("~/.mozilla/firefox")
            if os.path.exists(default_base):
                for entry in os.listdir(default_base):
                    if entry.endswith(".default-release") or entry.endswith(".default"):
                        cand = os.path.join(default_base, entry, "cookies.sqlite")
                        if os.path.exists(cand):
                            path = cand
                            break
        if not path or not os.path.exists(path):
            return {}

        tmp_db = f"/tmp/moz_cookies_{os.getpid()}_{int(time.time())}.sqlite"
        try:
            shutil.copyfile(path, tmp_db)
            conn = sqlite3.connect(tmp_db)
            rows = conn.cursor().execute(
                "SELECT name, value FROM moz_cookies WHERE host LIKE '%chatgpt.com%'"
            ).fetchall()
            conn.close()
            return dict(rows)
        finally:
            if os.path.exists(tmp_db):
                os.remove(tmp_db)

    def _parse_cookie_string(self, raw: str) -> Dict[str, str]:
        cookies = {}
        for part in raw.split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                cookies[k.strip()] = v.strip()
        return cookies

    def authenticate(self) -> bool:
        """Authenticate via access_token, cookie string, or Firefox DB."""
        # 1. Load cookies if available
        if self.cookie_string:
            self.session.cookies.update(self._parse_cookie_string(self.cookie_string))
        elif not self.access_token:
            ff_cookies = self._load_firefox_cookies()
            if ff_cookies:
                self.session.cookies.update(ff_cookies)

        # 2. If access_token missing, fetch via NextAuth session endpoint
        if not self.access_token:
            resp = self.session.get("https://chatgpt.com/api/auth/session")
            if resp.status_code == 200:
                data = resp.json()
                self.access_token = data.get("accessToken")
            else:
                return False

        if not self.access_token:
            return False

        self.session.headers["Authorization"] = f"Bearer {self.access_token}"

        # 3. Ensure ChatGPT-Account-ID is resolved
        if not self.account_id:
            wham = self.session.get("https://chatgpt.com/backend-api/wham/accounts/check")
            if wham.status_code == 200:
                accounts = wham.json().get("accounts", [])
                if accounts:
                    self.account_id = accounts[0]["id"]
                    self.session.headers["ChatGPT-Account-ID"] = self.account_id

        self.last_auth_time = time.time()
        return True

    def list_sessions(self) -> List[Dict]:
        """Fetch all active sessions/devices."""
        if not self.access_token or time.time() - self.last_auth_time > 2700:
            if not self.authenticate():
                raise PermissionError("Failed to authenticate with ChatGPT API.")

        resp = self.session.get("https://chatgpt.com/backend-api/accounts/sessions")
        if resp.status_code == 401:
            if not self.authenticate():
                raise PermissionError("Access token expired and refresh failed.")
            resp = self.session.get("https://chatgpt.com/backend-api/accounts/sessions")

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to fetch sessions: HTTP {resp.status_code} - {resp.text}")

        return resp.json().get("devices", [])

    def revoke_session(self, session_id: str) -> bool:
        """Revoke a specific session by its ID."""
        resp = self.session.post(
            "https://chatgpt.com/backend-api/accounts/sessions/revoke",
            json={"session_id": session_id},
        )
        return resp.status_code in (200, 204)
