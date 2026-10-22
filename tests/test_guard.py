import os
import tempfile
from chatgpt_guard.guard import ChatGPTGuard

class DummyClient:
    def __init__(self):
        self.revoked = []

    def list_sessions(self):
        return [
            {
                "session_id": "sess_current",
                "is_current_device": True,
                "device_model": "Computer",
                "last_signed_in_city": "Tehran",
            },
            {
                "session_id": "sess_phone",
                "is_current_device": False,
                "device_model": "SM-A715F",
                "last_signed_in_city": "Tehran",
            },
            {
                "session_id": "sess_intruder",
                "is_current_device": False,
                "device_model": "Unknown Windows PC",
                "last_signed_in_city": "Unknown City",
            },
        ]

    def revoke_session(self, session_id: str) -> bool:
        self.revoked.append(session_id)
        return True

def test_guard_logic():
    with tempfile.TemporaryDirectory() as tmpdir:
        allowed_file = os.path.join(tmpdir, "allowed.json")
        client = DummyClient()
        guard = ChatGPTGuard(
            client=client,
            allowed_file=allowed_file,
            allowed_identifiers={"SM-A715F"},
            keep_current_device=True,
        )

        allowed, unauthorized = guard.audit()
        assert len(allowed) == 2, f"Expected 2 allowed sessions, got {len(allowed)}"
        assert len(unauthorized) == 1, f"Expected 1 unauthorized session, got {len(unauthorized)}"
        assert unauthorized[0]["session_id"] == "sess_intruder"

        revoked = guard.enforce_once(dry_run=False)
        assert len(revoked) == 1
        assert client.revoked == ["sess_intruder"]

        # Test Pinning
        guard.pin_current_sessions()
        assert os.path.exists(allowed_file)

        # After pinning, all existing sessions become allowed
        allowed_after, unauthorized_after = guard.audit()
        assert len(unauthorized_after) == 0, "All sessions should be authorized after pinning"
        print("All guard tests passed successfully.")

if __name__ == "__main__":
    test_guard_logic()
