import json
import os
import time
from typing import Dict, List, Optional, Set, Tuple
from .client import ChatGPTClient

class ChatGPTGuard:
    """Manages session verification, pinning, and automated eviction."""

    def __init__(
        self,
        client: ChatGPTClient,
        allowed_file: str = "allowed_sessions.json",
        allowed_identifiers: Optional[Set[str]] = None,
        keep_current_device: bool = True,
        keep_oldest_codex: bool = False,
    ):
        self.client = client
        self.allowed_file = allowed_file
        self.allowed_identifiers = allowed_identifiers or set()
        self.keep_current_device = keep_current_device
        self.keep_oldest_codex = keep_oldest_codex

    def load_pinned_sessions(self) -> Dict[str, Dict]:
        if not os.path.exists(self.allowed_file):
            return {}
        with open(self.allowed_file, "r", encoding="utf-8") as f:
            return json.load(f)

    def pin_current_sessions(self) -> Dict[str, Dict]:
        """Save all currently active sessions as authorized baseline."""
        devices = self.client.list_sessions()
        pinned = {}
        for dev in devices:
            sid = dev.get("session_id")
            if not sid:
                continue
            apps = [a.get("client_name") for a in dev.get("app_sessions", []) if a.get("client_name")]
            pinned[sid] = {
                "session_id": sid,
                "device_model": dev.get("device_model"),
                "display_name": dev.get("display_name"),
                "platform": dev.get("platform"),
                "apps": apps,
                "created_at": dev.get("session_created_at_seconds"),
                "last_city": dev.get("last_signed_in_city"),
                "pinned_at": int(time.time()),
            }

        with open(self.allowed_file, "w", encoding="utf-8") as f:
            json.dump(pinned, f, indent=2, ensure_ascii=False)

        return pinned

    def is_device_allowed(
        self,
        dev: Dict,
        pinned_sessions: Dict[str, Dict],
        oldest_codex_id: Optional[str] = None,
    ) -> Tuple[bool, str]:
        # 1. Current supervisor session
        if self.keep_current_device and dev.get("is_current_device"):
            return True, "Current Session"

        sid = dev.get("session_id", "").strip()

        # 2. Pinned session ID
        if sid and sid in pinned_sessions:
            return True, "Pinned Session ID"

        # 3. Oldest Codex session rule
        if self.keep_oldest_codex and oldest_codex_id and sid == oldest_codex_id:
            return True, "Oldest Codex Session"

        # 4. Explicit model/name/identifier whitelist
        model = (dev.get("device_model") or "").strip()
        name = (dev.get("display_name") or "").strip()
        desc = (dev.get("human_readable_description") or "").strip()
        hid = (dev.get("hashed_device_id") or "").strip()

        for ident in self.allowed_identifiers:
            if ident in (model, name, hid, sid) or ident in desc:
                return True, f"Matched Identifier: {ident}"

        return False, "Unauthorized Session"

    def audit(self) -> Tuple[List[Dict], List[Dict]]:
        """Scan active sessions and classify into (allowed, unauthorized)."""
        devices = self.client.list_sessions()
        pinned = self.load_pinned_sessions()

        oldest_codex_id = None
        if self.keep_oldest_codex:
            codex_candidates = [
                d for d in devices
                if not d.get("is_current_device") and (
                    "Codex" in d.get("device_model", "")
                    or any("Codex" in a.get("client_name", "") for a in d.get("app_sessions", []))
                )
            ]
            codex_candidates.sort(key=lambda x: x.get("last_signed_in_timestamp_second", 0))
            if codex_candidates:
                oldest_codex_id = codex_candidates[0].get("session_id")

        allowed, unauthorized = [], []
        for dev in devices:
            is_ok, reason = self.is_device_allowed(dev, pinned, oldest_codex_id)
            dev_info = {**dev, "guard_reason": reason}
            if is_ok:
                allowed.append(dev_info)
            else:
                unauthorized.append(dev_info)

        return allowed, unauthorized

    def enforce_once(self, dry_run: bool = False) -> List[Dict]:
        """Revoke any session not present in the allowed rules."""
        _, unauthorized = self.audit()
        revoked = []
        for dev in unauthorized:
            sid = dev.get("session_id")
            if not sid:
                continue
            name = dev.get("device_model") or dev.get("display_name") or sid
            if dry_run:
                print(f"[DRY-RUN] Would revoke: {name} ({sid})")
                revoked.append(dev)
            else:
                success = self.client.revoke_session(sid)
                if success:
                    print(f"[REVOKED] {name} ({sid}) successfully evicted.")
                    revoked.append(dev)
                else:
                    print(f"[FAILED] Could not revoke {name} ({sid}).")
        return revoked

    def run_forever(self, interval: int = 15, dry_run: bool = False) -> None:
        """Continuous watchdog polling loop."""
        print(f"[GUARD ACTIVE] Polling every {interval}s (Dry-run: {dry_run}).")
        while True:
            try:
                self.enforce_once(dry_run=dry_run)
            except Exception as e:
                print(f"[ERROR] Watchdog iteration failed: {e}")
            time.sleep(interval)
