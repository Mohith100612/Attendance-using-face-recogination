from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from database import engine, Base
from routes import register, attendance
import os

Base.metadata.create_all(bind=engine)

# Add new profile columns to existing databases without losing data
with engine.connect() as conn:
    for col in ["email VARCHAR(255)", "phone VARCHAR(50)", "linkedin VARCHAR(255)", "occupation VARCHAR(255)"]:
        conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col}"))
    conn.commit()

app = FastAPI(title="Face Attendance System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

upload_dir = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(upload_dir, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=upload_dir), name="uploads")

app.include_router(register.router)
app.include_router(attendance.router)


@app.get("/health")
def health():
    return {"status": "ok"}
