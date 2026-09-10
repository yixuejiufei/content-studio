from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .planner import attach_asset, build_rough_cut, draft_content_task, refresh_task_status
from .schemas import ContentTask, CreateContentTaskRequest, UpdateContentTaskRequest
from .storage import SQLiteStore

app = FastAPI(title="Content Studio")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"], allow_methods=["*"], allow_headers=["*"])
store = SQLiteStore()
media_root = Path(os.getenv("CONTENT_STUDIO_MEDIA_DIR", str(Path(__file__).resolve().parent.parent / "content-media")))
media_root.mkdir(parents=True, exist_ok=True)


def require_task(task_id: str) -> ContentTask:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="content task not found")
    return task


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "content-studio"}


@app.get("/api/v1/content/tasks")
def list_tasks() -> list[ContentTask]:
    return store.list()


@app.post("/api/v1/content/tasks", status_code=201)
def create_task(request: CreateContentTaskRequest) -> ContentTask:
    task = draft_content_task(request.title.strip(), request.audience.strip(), request.platform, request.target_seconds)
    store.save(task)
    return task


@app.get("/api/v1/content/tasks/{task_id}")
def get_task(task_id: str) -> ContentTask:
    return require_task(task_id)


@app.put("/api/v1/content/tasks/{task_id}")
def update_task(task_id: str, request: UpdateContentTaskRequest) -> ContentTask:
    current = require_task(task_id)
    task = ContentTask(task_id=task_id, title=request.title.strip(), audience=request.audience.strip(), platform=request.platform, target_seconds=request.target_seconds, status=current.status, voiceover_asset=request.voiceover_asset, beats=request.beats, created_at=current.created_at, updated_at=current.updated_at)
    refresh_task_status(task)
    store.save(task)
    return task


@app.post("/api/v1/content/tasks/{task_id}/assets/{slot_id}")
async def upload_asset(task_id: str, slot_id: str, request: Request) -> ContentTask:
    task = require_task(task_id)
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="asset upload was empty")
    if len(payload) > 512 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="asset must be no larger than 512 MB")
    name = re.sub(r"[^A-Za-z0-9._() -]", "_", Path(request.headers.get("x-file-name", "asset.bin")).name)[:180] or "asset.bin"
    folder = media_root / task_id
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{slot_id}-{uuid.uuid4().hex[:8]}-{name}"
    destination.write_bytes(payload)
    try:
        attach_asset(task, slot_id, name, destination, request.headers.get("content-type", "application/octet-stream"), len(payload))
    except KeyError:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="content asset slot not found") from None
    task.rough_cut = None
    store.save(task)
    return task


@app.get("/api/v1/content/tasks/{task_id}/assets/{slot_id}")
def get_asset(task_id: str, slot_id: str) -> FileResponse:
    task = require_task(task_id)
    slot = next((item for item in [task.voiceover_asset, *(beat.asset for beat in task.beats)] if item.id == slot_id), None)
    if slot is None or not slot.stored_path:
        raise HTTPException(status_code=404, detail="content asset not found")
    path = Path(slot.stored_path).resolve()
    if media_root.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="content asset file not found")
    return FileResponse(path, media_type=slot.mime_type, filename=slot.file_name)


@app.post("/api/v1/content/tasks/{task_id}/rough-cut")
def create_rough_cut(task_id: str) -> ContentTask:
    task = require_task(task_id)
    try:
        task.rough_cut = build_rough_cut(task)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    refresh_task_status(task)
    store.save(task)
    return task
