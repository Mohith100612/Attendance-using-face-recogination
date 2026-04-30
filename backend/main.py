import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from database import engine, Base
from routes import register, attendance, events, import_sheet
import ws_manager
import os

Base.metadata.create_all(bind=engine)

# Add new profile columns to existing databases without losing data
with engine.connect() as conn:
    for col in ["email VARCHAR(255)", "phone VARCHAR(50)", "linkedin VARCHAR(255)", "occupation VARCHAR(255)"]:
        conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col}"))
    conn.execute(text("ALTER TABLE attendance ADD COLUMN IF NOT EXISTS event_id INTEGER REFERENCES events(id)"))
    # DB-level duplicate guard: one person per event; NULL event_id falls back to app-level date check
    conn.execute(text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_attendance_user_event
        ON attendance (user_id, event_id)
        WHERE event_id IS NOT NULL
    """))
    conn.commit()

app = FastAPI(title="Face Attendance System")


@app.on_event("startup")
async def startup():
    ws_manager.set_loop(asyncio.get_running_loop())

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
app.include_router(events.router)
app.include_router(import_sheet.router)


@app.websocket("/ws/display")
async def display_ws(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


@app.get("/health")
def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
