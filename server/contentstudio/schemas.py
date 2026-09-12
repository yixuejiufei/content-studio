from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Platform = Literal["douyin", "xiaohongshu", "bilibili", "video_account"]
AssetKind = Literal["audio", "screen", "image", "generated_card"]
AssetStatus = Literal["ready", "missing", "uploaded"]
TaskStatus = Literal["prepare_assets", "ready_for_assembly", "rough_cut_ready"]
RenderProfile = Literal["preview_720p", "publish_1080p", "vertical_1080p"]
RenderJobStatus = Literal["queued", "rendering", "completed", "failed", "cancelled"]


class ContentAssetSlot(BaseModel):
    id: str = Field(min_length=1, max_length=96)
    label: str = Field(min_length=1, max_length=160)
    kind: AssetKind
    required: bool = True
    instruction: str = Field(min_length=1, max_length=1000)
    target_seconds: float = Field(default=0, ge=0, le=600)
    status: AssetStatus = "missing"
    file_name: str | None = None
    stored_path: str | None = None
    mime_type: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)


class ContentBeat(BaseModel):
    id: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=120)
    voiceover: str = Field(min_length=1, max_length=2000)
    visual_goal: str = Field(min_length=1, max_length=1000)
    start_seconds: float = Field(ge=0, le=3600)
    end_seconds: float = Field(gt=0, le=3600)
    asset: ContentAssetSlot


class RoughCutItem(BaseModel):
    beat_id: str
    start_seconds: float = Field(ge=0)
    end_seconds: float = Field(gt=0)
    voiceover: str
    visual_asset_slot_id: str
    visual_file_name: str | None = None
    edit_note: str


class ContentRoughCut(BaseModel):
    generated_at: float
    status: Literal["draft"] = "draft"
    items: list[RoughCutItem]
    edit_plan: dict[str, Any]


class ContentVideoExport(BaseModel):
    generated_at: float
    status: Literal["ready"] = "ready"
    file_name: str
    stored_path: str
    subtitle_file_name: str
    duration_seconds: float = Field(gt=0)
    size_bytes: int = Field(ge=0)
    profile: RenderProfile = "publish_1080p"


class RenderJob(BaseModel):
    job_id: str = Field(min_length=1, max_length=96)
    task_id: str = Field(min_length=1, max_length=96)
    profile: RenderProfile = "publish_1080p"
    status: RenderJobStatus = "queued"
    progress_percent: int = Field(default=0, ge=0, le=100)
    cancel_requested: bool = False
    error: str | None = None
    output: ContentVideoExport | None = None
    created_at: float
    started_at: float | None = None
    completed_at: float | None = None


class CreateRenderJobRequest(BaseModel):
    profile: RenderProfile = "publish_1080p"


class ContentTask(BaseModel):
    task_id: str = Field(min_length=1, max_length=96)
    title: str = Field(min_length=1, max_length=160)
    audience: str = Field(min_length=1, max_length=240)
    platform: Platform = "douyin"
    target_seconds: int = Field(default=90, ge=15, le=900)
    status: TaskStatus = "prepare_assets"
    voiceover_asset: ContentAssetSlot
    beats: list[ContentBeat] = Field(min_length=1, max_length=32)
    rough_cut: ContentRoughCut | None = None
    video_export: ContentVideoExport | None = None
    created_at: float
    updated_at: float


class CreateContentTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    audience: str = Field(min_length=3, max_length=240)
    platform: Platform = "douyin"
    target_seconds: int = Field(default=90, ge=15, le=900)


class UpdateContentTaskRequest(BaseModel):
    title: str = Field(min_length=3, max_length=160)
    audience: str = Field(min_length=3, max_length=240)
    platform: Platform
    target_seconds: int = Field(ge=15, le=900)
    voiceover_asset: ContentAssetSlot
    beats: list[ContentBeat] = Field(min_length=1, max_length=32)
