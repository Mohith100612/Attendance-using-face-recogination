"""
Stress test for the Face Attendance API.

Run:
    pip install locust
    locust -f locustfile.py --host http://localhost:8000

Then open http://localhost:8089 and set number of users + spawn rate.

Endpoints tested:
  POST /api/attendance/detect  (weight 5 — heaviest, runs DeepFace)
  GET  /api/attendance/logs    (weight 2)
  GET  /api/events             (weight 1)
"""

import base64
import io
import threading

from locust import HttpUser, between, task

# ---------------------------------------------------------------------------
# Generate a small valid JPEG once at module load time (120×120 grey square).
# DeepFace will return "no_face" for it — that's fine; we're testing throughput
# and error handling, not recognition accuracy.
# ---------------------------------------------------------------------------
try:
    from PIL import Image
    _buf = io.BytesIO()
    Image.new("RGB", (120, 120), (110, 110, 110)).save(_buf, format="JPEG", quality=50)
    _TEST_IMAGE = "data:image/jpeg;base64," + base64.b64encode(_buf.getvalue()).decode()
except Exception:
    # Minimal 1×1 white JPEG fallback if Pillow is unavailable
    _TEST_IMAGE = (
        "data:image/jpeg;base64,"
        "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDB"
        "kSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAAR"
        "CAABAAEDASIAAhEBAxEB/8QAFAABAAAAAAAAAAAAAAAAAAAACf/EABQQAQAAAAAA"
        "AAAAAAAAAAAAAAD/xAAUAQEAAAAAAAAAAAAAAAAAAAAA/8QAFBEBAAAAAAAAAAAAA"
        "AAAAAAAP/aAAwDAQACEQMRAD8AJQAB/9k="
    )

_event_id_lock = threading.Lock()
_shared_event_id = None


class AttendanceUser(HttpUser):
    wait_time = between(0.5, 2.0)

    def on_start(self):
        """Each simulated user grabs (or creates) the shared load-test event."""
        global _shared_event_id
        with _event_id_lock:
            if _shared_event_id is None:
                r = self.client.get("/api/events", name="/api/events [setup]")
                if r.status_code == 200 and r.json():
                    _shared_event_id = r.json()[0]["id"]
                else:
                    r2 = self.client.post(
                        "/api/events",
                        json={"name": "Load Test Event"},
                        name="/api/events [setup]",
                    )
                    if r2.status_code == 200:
                        _shared_event_id = r2.json()["id"]
        self.event_id = _shared_event_id

    @task(5)
    def detect_face(self):
        self.client.post(
            "/api/attendance/detect",
            json={"image": _TEST_IMAGE, "event_id": self.event_id},
        )

    @task(2)
    def get_logs(self):
        params = {"event_id": self.event_id} if self.event_id else {}
        self.client.get("/api/attendance/logs", params=params)

    @task(1)
    def list_events(self):
        self.client.get("/api/events")
