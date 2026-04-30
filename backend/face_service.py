from deepface import DeepFace
import base64
import os
import uuid

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MODEL_NAME = "Facenet"
DETECTOR = "opencv"
LIVENESS_CHECK = os.getenv("LIVENESS_CHECK", "false").lower() == "true"


def get_embedding(image_path: str, enforce: bool = True) -> list | None:
    try:
        result = DeepFace.represent(
            img_path=image_path,
            model_name=MODEL_NAME,
            enforce_detection=enforce,
            detector_backend=DETECTOR,
        )
        return result[0]["embedding"]
    except Exception as e:
        print(f"[face_service] embedding failed (enforce={enforce}): {e}")
        return None


def is_live_face(image_path: str) -> bool:
    if not LIVENESS_CHECK:
        return True
    try:
        faces = DeepFace.extract_faces(
            img_path=image_path,
            enforce_detection=False,
            anti_spoofing=True,
        )
        if not faces:
            return True
        result = bool(faces[0].get("is_real", True))
        score = faces[0].get("antispoof_score", None)
        print(f"[liveness] is_real={result} score={score}")
        return result
    except Exception as e:
        print(f"[liveness] check error (fail open): {e}")
        return True


def save_base64_image(b64_str: str) -> str:
    if "," in b64_str:
        b64_str = b64_str.split(",")[1]
    data = base64.b64decode(b64_str)
    path = os.path.join(UPLOAD_DIR, f"tmp_{uuid.uuid4().hex}.jpg")
    with open(path, "wb") as f:
        f.write(data)
    return path


def save_upload_bytes(file_bytes: bytes, original_name: str) -> tuple[str, str]:
    ext = os.path.splitext(original_name)[1] or ".jpg"
    filename = f"{uuid.uuid4().hex}{ext}"
    path = os.path.join(UPLOAD_DIR, filename)
    with open(path, "wb") as f:
        f.write(file_bytes)
    return path, filename
