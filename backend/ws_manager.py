import asyncio
from fastapi import WebSocket

_connections: list[WebSocket] = []
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop):
    global _loop
    _loop = loop


async def connect(ws: WebSocket):
    await ws.accept()
    _connections.append(ws)


def disconnect(ws: WebSocket):
    if ws in _connections:
        _connections.remove(ws)


async def _broadcast(data: dict):
    dead = []
    for ws in _connections:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        disconnect(ws)


def broadcast(data: dict):
    """Push data to all connected display screens from a sync route handler."""
    if _loop and _loop.is_running():
        asyncio.run_coroutine_threadsafe(_broadcast(data), _loop)
