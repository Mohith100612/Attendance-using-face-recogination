from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel
from database import get_db
from models import Attendance
from face_service import get_embedding, save_base64_image, is_live_face
from typing import Optional
import os

router = APIRouter(prefix="/api/attendance", tags=["attendance"])

CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.40"))
MATCH_THRESHOLD = float(os.getenv("MATCH_THRESHOLD", "0.55"))


class DetectRequest(BaseModel):
    image: str          # base64 data URL
    event_id: Optional[int] = None


@router.post("/detect")
def detect_face(request: DetectRequest, db: Session = Depends(get_db)):
    # Validate event if provided
    if request.event_id is not None:
        event = db.execute(
            text("SELECT id FROM events WHERE id = :eid"),
            {"eid": request.event_id},
        ).fetchone()
        if not event:
            return {"status": "invalid_event"}

    temp_path = save_base64_image(request.image)

    try:
        # Liveness check (no-op when LIVENESS_CHECK=false)
        if not is_live_face(temp_path):
            return {"status": "spoof_detected"}

        # enforce=False so a slightly off-angle webcam frame still gets an embedding
        embedding = get_embedding(temp_path, enforce=False)
        if embedding is None:
            print("[detect] DeepFace could not extract embedding")
            return {"status": "no_face"}

        # Build the vector literal directly — avoids SQLAlchemy confusing
        # ':emb::vector' (named param + PG cast) as a malformed parameter name.
        # Safe: embedding_str is a list of floats from DeepFace, not user input.
        embedding_str = "[" + ",".join(map(str, embedding)) + "]"

        row = db.execute(
            text(f"""
                SELECT id, name, image_url,
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

        # Duplicate check: per event if event_id given, otherwise per calendar day
        if request.event_id is not None:
            already_attended = db.execute(
                text("SELECT id FROM attendance WHERE user_id = :uid AND event_id = :eid"),
                {"uid": row.id, "eid": request.event_id},
            ).fetchone()
        else:
            already_attended = db.execute(
                text("SELECT id FROM attendance WHERE user_id = :uid AND event_id IS NULL AND DATE(timestamp) = CURRENT_DATE"),
                {"uid": row.id},
            ).fetchone()

        if not already_attended:
            try:
                db.add(Attendance(user_id=row.id, event_id=request.event_id, status="present"))
                db.commit()
            except IntegrityError:
                # Race condition: another request inserted first — treat as already attended
                db.rollback()
                already_attended = True

        return {
            "status": "matched",
            "user": {
                "id": row.id,
                "name": row.name,
                "image_url": row.image_url,
                "already_attended": already_attended is not None,
            },
            "distance": round(row.distance, 4),
        }
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)


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
