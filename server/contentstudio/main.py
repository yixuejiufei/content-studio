from __future__ import annotations

import os
import re
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .planner import attach_asset, build_rough_cut, draft_content_task, refresh_task_status
from .renderer import RenderCancelled, render_rough_cut
from .schemas import ContentTask, CreateContentTaskRequest, CreateRenderJobRequest, RenderJob, UpdateContentTaskRequest
from .storage import SQLiteStore

app = FastAPI(title="Content Studio")
app.add_middleware(CORSMiddleware, allow_origins=["http://127.0.0.1:5174", "http://localhost:5174"], allow_methods=["*"], allow_headers=["*"])
store = SQLiteStore()
media_root = Path(os.getenv("CONTENT_STUDIO_MEDIA_DIR", str(Path(__file__).resolve().parent.parent / "content-media")))
media_root.mkdir(parents=True, exist_ok=True)
render_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="content-render")
render_cancellations: dict[str, threading.Event] = {}
render_lock = threading.RLock()


def require_task(task_id: str) -> ContentTask:
    task = store.get(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="content task not found")
    return task


def require_render_job(job_id: str) -> RenderJob:
    job = store.get_render_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="render job not found")
    return job


def _run_render_job(job_id: str, cancellation: threading.Event) -> None:
    job = store.get_render_job(job_id)
    if job is None:
        return
    if cancellation.is_set():
        job.status, job.cancel_requested, job.completed_at = "cancelled", True, time.time()
        store.save_render_job(job)
        return
    job.status, job.started_at, job.progress_percent = "rendering", time.time(), 2
    store.save_render_job(job)

    def update_progress(progress: int) -> None:
        latest = store.get_render_job(job_id)
        if latest is None or latest.status != "rendering":
            return
        latest.progress_percent = max(latest.progress_percent, progress)
        store.save_render_job(latest)

    try:
        task = require_task(job.task_id)
        task.rough_cut = task.rough_cut or build_rough_cut(task)
        output = render_rough_cut(task, media_root, profile=job.profile, on_progress=update_progress, cancel_event=cancellation)
        task.video_export = output
        store.save(task)
        latest = require_render_job(job_id)
        latest.status, latest.progress_percent, latest.output, latest.completed_at = "completed", 100, output, time.time()
        store.save_render_job(latest)
    except RenderCancelled:
        latest = require_render_job(job_id)
        latest.status, latest.cancel_requested, latest.completed_at = "cancelled", True, time.time()
        store.save_render_job(latest)
    except Exception as exc:  # The UI receives a concise failure without losing an older export.
        latest = require_render_job(job_id)
        latest.status, latest.error, latest.completed_at = "failed", str(exc)[-1600:], time.time()
        store.save_render_job(latest)
    finally:
        with render_lock:
            render_cancellations.pop(job_id, None)


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
    task = ContentTask(task_id=task_id, title=request.title.strip(), audience=request.audience.strip(), platform=request.platform, target_seconds=request.target_seconds, status=current.status, voiceover_asset=request.voiceover_asset, music_asset=request.music_asset, beats=request.beats, render_directives=request.render_directives, created_at=current.created_at, updated_at=current.updated_at)
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
    task.video_export = None
    store.save(task)
    return task


@app.get("/api/v1/content/tasks/{task_id}/assets/{slot_id}")
def get_asset(task_id: str, slot_id: str) -> FileResponse:
    task = require_task(task_id)
    slots = [task.voiceover_asset]
    if task.music_asset:
        slots.append(task.music_asset)
    slots.extend(beat.asset for beat in task.beats)
    slot = next((item for item in slots if item.id == slot_id), None)
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


@app.post("/api/v1/content/tasks/{task_id}/export")
def export_rough_cut(task_id: str) -> ContentTask:
    task = require_task(task_id)
    try:
        task.rough_cut = task.rough_cut or build_rough_cut(task)
        task.video_export = render_rough_cut(task, media_root)
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    refresh_task_status(task)
    store.save(task)
    return task


@app.post("/api/v1/content/tasks/{task_id}/render-jobs", status_code=202)
def create_render_job(task_id: str, request: CreateRenderJobRequest) -> RenderJob:
    task = require_task(task_id)
    try:
        task.rough_cut = task.rough_cut or build_rough_cut(task)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    store.save(task)
    job = RenderJob(job_id=f"render-{uuid.uuid4().hex[:12]}", task_id=task_id, profile=request.profile, created_at=time.time())
    cancellation = threading.Event()
    with render_lock:
        render_cancellations[job.job_id] = cancellation
    store.save_render_job(job)
    render_executor.submit(_run_render_job, job.job_id, cancellation)
    return job


@app.get("/api/v1/content/tasks/{task_id}/render-jobs")
def list_render_jobs(task_id: str) -> list[RenderJob]:
    require_task(task_id)
    return store.list_render_jobs(task_id)


@app.get("/api/v1/content/render-jobs/{job_id}")
def get_render_job(job_id: str) -> RenderJob:
    return require_render_job(job_id)


@app.post("/api/v1/content/render-jobs/{job_id}/cancel")
def cancel_render_job(job_id: str) -> RenderJob:
    job = require_render_job(job_id)
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    job.cancel_requested = True
    store.save_render_job(job)
    with render_lock:
        cancellation = render_cancellations.get(job_id)
    if cancellation:
        cancellation.set()
    return job


@app.get("/api/v1/content/render-jobs/{job_id}/download")
def download_render_job(job_id: str) -> FileResponse:
    job = require_render_job(job_id)
    if job.status != "completed" or job.output is None:
        raise HTTPException(status_code=409, detail="视频尚未导出完成")
    path = Path(job.output.stored_path).resolve()
    if media_root.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    return FileResponse(path, media_type="video/mp4", filename=job.output.file_name)


@app.get("/api/v1/content/tasks/{task_id}/export")
def download_export(task_id: str) -> FileResponse:
    task = require_task(task_id)
    if task.video_export is None:
        raise HTTPException(status_code=404, detail="尚未生成视频导出")
    path = Path(task.video_export.stored_path).resolve()
    if media_root.resolve() not in path.parents or not path.is_file():
        raise HTTPException(status_code=404, detail="视频导出文件不存在")
    return FileResponse(path, media_type="video/mp4", filename=task.video_export.file_name)
