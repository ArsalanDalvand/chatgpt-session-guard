import argparse
import json
import os
import sys
from .client import ChatGPTClient
from .guard import ChatGPTGuard

def load_config(config_path: str) -> dict:
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def main():
    parser = argparse.ArgumentParser(
        description="ChatGPT Session Guard: Automated session monitoring and eviction."
    )
    parser.add_argument("--pin", action="store_true", help="Pin currently active sessions to allowed baseline.")
    parser.add_argument("--list", action="store_true", help="List active sessions and audit authorization status.")
    parser.add_argument("--watch", action="store_true", help="Run the continuous monitoring and eviction daemon.")
    parser.add_argument("--dry-run", action="store_true", help="Audit or run without revoking any sessions.")
    parser.add_argument("--interval", type=int, default=15, help="Polling interval in seconds (default: 15).")
    parser.add_argument("--config", default="config.json", help="Path to config.json (default: config.json).")
    parser.add_argument("--allowed-file", default="allowed_sessions.json", help="Path to allowed_sessions.json.")
    parser.add_argument("--token", help="Direct Bearer access token (or env CHATGPT_ACCESS_TOKEN).")
    parser.add_argument("--cookie", help="Cookie string (or env CHATGPT_COOKIE).")
    parser.add_argument("--firefox-profile", help="Path to Firefox cookies.sqlite (optional).")
    parser.add_argument("--allow-ident", action="append", help="Allow specific device model/name/ID (repeatable).")
    parser.add_argument("--keep-codex", action="store_true", help="Preserve oldest Codex session.")

    args = parser.parse_args()
    cfg = load_config(args.config)

    # Resolution priority: CLI args > Config file > Environment variables
    token = args.token or cfg.get("access_token") or os.getenv("CHATGPT_ACCESS_TOKEN")
    cookie = args.cookie or cfg.get("cookie_string") or os.getenv("CHATGPT_COOKIE")
    ff_profile = args.firefox_profile or cfg.get("firefox_profile_path") or os.getenv("FIREFOX_PROFILE_PATH")
    allowed_file = args.allowed_file or cfg.get("allowed_file", "allowed_sessions.json")
    interval = args.interval or cfg.get("interval", 15)
    keep_codex = args.keep_codex or cfg.get("keep_oldest_codex", False)

    allowed_idents = set(cfg.get("allowed_identifiers", []))
    if args.allow_ident:
        allowed_idents.update(args.allow_ident)

    client = ChatGPTClient(
        access_token=token,
        cookie_string=cookie,
        firefox_profile_path=ff_profile,
    )

    guard = ChatGPTGuard(
        client=client,
        allowed_file=allowed_file,
        allowed_identifiers=allowed_idents,
        keep_oldest_codex=keep_codex,
    )

    if args.pin:
        print("[PIN] Querying current sessions...")
        pinned = guard.pin_current_sessions()
        print(f"[PIN SUCCESS] {len(pinned)} session(s) pinned to '{allowed_file}'.")
        for sid, info in pinned.items():
            print(f"  + {info.get('device_model')} ({info.get('last_city')}) -> {sid}")
        return

    if args.list:
        print("[AUDIT] Checking active sessions...")
        allowed, unauthorized = guard.audit()
        print(f"\n--- ALLOWED ({len(allowed)}) ---")
        for d in allowed:
            print(f"  ✓ {d.get('device_model')} | {d.get('last_signed_in_city')} | Reason: {d.get('guard_reason')} | ID: {d.get('session_id')}")
        print(f"\n--- UNAUTHORIZED ({len(unauthorized)}) ---")
        for d in unauthorized:
            print(f"  ✗ {d.get('device_model')} | {d.get('last_signed_in_city')} | ID: {d.get('session_id')}")
        return

    if args.watch:
        guard.run_forever(interval=interval, dry_run=args.dry_run)
        return

    # Default if no action flag: run single audit & prompt
    allowed, unauthorized = guard.audit()
    print(f"Active sessions: {len(allowed) + len(unauthorized)} total | {len(allowed)} allowed | {len(unauthorized)} unauthorized.")
    if unauthorized:
        print("Run with --watch to automatically evict unauthorized devices, or --pin to trust current sessions.")

if __name__ == "__main__":
    main()
