from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from database import get_db
from models import Attendance
from face_service import get_embedding_from_array, b64_to_array, is_live_face
from typing import Optional
from datetime import datetime
import ws_manager
import os

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.50"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.70"))


class DetectRequest(BaseModel):
    image: str          # base64 data URL
    event_id: Optional[int] = None


@router.post("/detect")
def detect_face(request: DetectRequest, db: Session = Depends(get_db)):
    # Validate event if provided
    event_name = None
    if request.event_id is not None:
        event = db.execute(
            text("SELECT id, name FROM events WHERE id = :eid"),
            {"eid": request.event_id},
        ).fetchone()
        if not event:
            return {"status": "invalid_event"}
        event_name = event.name

    # Decode base64 directly to numpy array — no disk write
    img_array = b64_to_array(request.image)
    if img_array is None:
        return {"status": "no_face"}

    try:
        if not is_live_face(img_array):
            return {"status": "spoof_detected"}

        # Image is already a cropped face from the frontend, so skip detector
        embedding = get_embedding_from_array(img_array)
        if embedding is None:
            print("[detect] DeepFace could not extract embedding")
            return {"status": "no_face"}

        # Build the vector literal directly — avoids SQLAlchemy confusing
        # ':emb::vector' (named param + PG cast) as a malformed parameter name.
        # Safe: embedding_str is a list of floats from DeepFace, not user input.
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        row = db.execute(
            text(f"""
                SELECT id, name, email, phone, linkedin, occupation, image_url,
                       embedding <=> '{embedding_str}'::vector AS distance
                FROM users
                ORDER BY embedding <=> '{embedding_str}'::vector
                LIMIT 1
            """)
        ).fetchone()

        if row is None:
            return {"status": "no_users_registered"}

        print(f"[detect] best match: '{row.name}' distance={row.distance:.4f} confidence={CONFIDENCE_THRESHOLD} match={MATCH_THRESHOLD}")

        if row.distance > MATCH_THRESHOLD:
            return {"status": "not_registered", "distance": round(row.distance, 4)}

        if row.distance > CONFIDENCE_THRESHOLD:
            return {"status": "low_confidence", "distance": round(row.distance, 4)}

        # Event-specific enrollment check
        already_attended = False
        if request.event_id is not None:
            record = db.execute(
                text("SELECT id, status FROM attendance WHERE user_id = :uid AND event_id = :eid"),
                {"uid": row.id, "eid": request.event_id},
            ).fetchone()

            if record is None:
                # Face recognised but not enrolled for this event
                ws_manager.broadcast({
                    "type": "not_enrolled",
                    "user": {"name": row.name, "image_url": row.image_url},
                    "event_name": event_name,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                return {
                    "status": "not_registered_for_event",
                    "user": {"name": row.name},
                    "distance": round(row.distance, 4),
                }

            if record.status == "present":
                already_attended = True
            else:
                # status = "enrolled" → first face scan, mark as present
                db.execute(
                    text("UPDATE attendance SET status='present', timestamp=NOW() WHERE id=:aid"),
                    {"aid": record.id},
                )
                db.commit()
        else:
            # No event selected — fall back to per-day duplicate check
            existing = db.execute(
                text("SELECT id FROM attendance WHERE user_id = :uid AND event_id IS NULL AND DATE(timestamp) = CURRENT_DATE"),
                {"uid": row.id},
            ).fetchone()

            if existing:
                already_attended = True
            else:
                try:
                    db.add(Attendance(user_id=row.id, event_id=None, status="present"))
                    db.commit()
                except IntegrityError:
                    db.rollback()
                    already_attended = True

        ws_manager.broadcast({
            "type": "match",
            "user": {
                "name": row.name,
                "email": row.email,
                "phone": row.phone,
                "linkedin": row.linkedin,
                "occupation": row.occupation,
                "image_url": row.image_url,
                "already_attended": already_attended,
            },
            "event_name": event_name,
            "timestamp": datetime.utcnow().isoformat(),
        })

        return {
            "status": "matched",
            "user": {
                "id": row.id,
                "name": row.name,
                "image_url": row.image_url,
                "already_attended": already_attended,
            },
            "distance": round(row.distance, 4),
        }
    except Exception as e:
        print(f"[detect] unexpected error: {e}")
        return {"status": "error"}


@router.get("/logs")
def attendance_logs(event_id: Optional[int] = None, db: Session = Depends(get_db)):
    if event_id is not None:
        rows = db.execute(
            text("""
                SELECT a.id, u.name, u.image_url, a.status, a.timestamp, a.event_id, e.name AS event_name
                FROM attendance a
                JOIN users u ON u.id = a.user_id
                LEFT JOIN events e ON e.id = a.event_id
                WHERE a.event_id = :eid
                ORDER BY a.timestamp DESC
                LIMIT 200
            """),
            {"eid": event_id},
        ).fetchall()
    else:
        rows = db.execute(
            text("""
                SELECT a.id, u.name, u.image_url, a.status, a.timestamp, a.event_id, e.name AS event_name
                FROM attendance a
                JOIN users u ON u.id = a.user_id
                LEFT JOIN events e ON e.id = a.event_id
                ORDER BY a.timestamp DESC
                LIMIT 200
            """)
        ).fetchall()

    return [
        {
            "id": r.id,
            "name": r.name,
            "image_url": r.image_url,
            "status": r.status,
            "timestamp": r.timestamp,
            "event_id": r.event_id,
            "event_name": r.event_name,
        }
        for r in rows
    ]
