"""Local FFmpeg rendering for Content Studio's first automatic rough cut."""

from __future__ import annotations

import subprocess
import time
import uuid
import os
from collections.abc import Callable
from threading import Event
from pathlib import Path

from .planner import all_slots
from .schemas import ContentTask, ContentVideoExport, RenderDirective, RenderProfile

PROFILE_DIMENSIONS: dict[RenderProfile, tuple[int, int, int]] = {
    "preview_720p": (1280, 720, 30),
    "publish_1080p": (1920, 1080, 30),
    "vertical_1080p": (1080, 1920, 30),
}


class RenderCancelled(Exception):
    """Raised when a creator cancels an active FFmpeg render."""


def _settings(profile: RenderProfile) -> tuple[int, int, int]:
    default_width, default_height, default_rate = PROFILE_DIMENSIONS[profile]
    # The overrides make the renderer fast enough for integration tests without
    # changing the creator-facing production presets.
    return (
        int(os.getenv("CONTENT_STUDIO_RENDER_WIDTH", str(default_width))),
        int(os.getenv("CONTENT_STUDIO_RENDER_HEIGHT", str(default_height))),
        int(os.getenv("CONTENT_STUDIO_RENDER_FRAME_RATE", str(default_rate))),
    )


def _srt_time(seconds: float) -> str:
    milliseconds = round(seconds * 1000)
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    whole_seconds, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{whole_seconds:02},{milliseconds:03}"


def _write_subtitles(task: ContentTask, output_path: Path) -> None:
    lines: list[str] = []
    for index, beat in enumerate(task.beats, start=1):
        text = beat.voiceover.replace("\r", " ").replace("\n", " ").strip()
        lines.extend([str(index), f"{_srt_time(beat.start_seconds)} --> {_srt_time(beat.end_seconds)}", text, ""])
    output_path.write_text("\n".join(lines), encoding="utf-8")


def _filter_path(path: Path) -> str:
    """Escape an absolute Windows path for FFmpeg's subtitles filter."""
    return path.resolve().as_posix().replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def _drawtext_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:").replace("%", "\\%").replace("\n", "\\n")


def _color_for_ffmpeg(hex_color: str) -> str:
    return "0x" + hex_color.removeprefix("#")


def _enabled_directives(task: ContentTask, directive_type: str) -> list[RenderDirective]:
    return [directive for directive in task.render_directives if directive.enabled and directive.type == directive_type]


def render_rough_cut(
    task: ContentTask,
    media_root: Path,
    profile: RenderProfile = "publish_1080p",
    on_progress: Callable[[int], None] | None = None,
    cancel_event: Event | None = None,
) -> ContentVideoExport:
    missing = [slot.label for slot in all_slots(task) if slot.required and slot.status not in {"ready", "uploaded"}]
    if missing:
        raise ValueError("仍缺少必需素材：" + "、".join(missing))
    if not task.voiceover_asset.stored_path:
        raise ValueError("仍缺少完整旁白音频")

    try:
        import imageio_ffmpeg
    except ImportError as exc:  # pragma: no cover - documented setup failure
        raise RuntimeError("未找到本地 FFmpeg 运行时；请安装 imageio-ffmpeg") from exc

    width, height, frame_rate = _settings(profile)
    task_directory = media_root / task.task_id
    task_directory.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex[:8]
    output = task_directory / f"rough-cut-{token}.mp4"
    subtitles = task_directory / f"rough-cut-{token}.srt"
    _write_subtitles(task, subtitles)

    command = [imageio_ffmpeg.get_ffmpeg_exe(), "-hide_banner", "-y"]
    visual_filters: list[str] = []
    fades = {directive.beat_id: directive for directive in _enabled_directives(task, "transition.fade") if directive.beat_id}
    for index, beat in enumerate(task.beats):
        duration = round(beat.end_seconds - beat.start_seconds, 3)
        if beat.asset.stored_path:
            source = Path(beat.asset.stored_path).resolve()
            if not source.is_file():
                raise ValueError(f"素材文件不存在：{beat.asset.label}")
            command.extend(["-stream_loop", "-1", "-i", str(source)])
        else:
            # The optional opening text card deliberately needs no uploaded file.
            command.extend(["-f", "lavfi", "-i", f"color=c=0x101827:s={width}x{height}:r={frame_rate}"])
        fade = fades.get(beat.id)
        fade_filter = ""
        if fade:
            fade_duration = min(fade.fade_seconds, max(0.05, duration / 2))
            fade_filter = f",fade=t=in:st=0:d={fade_duration},fade=t=out:st={max(0, duration - fade_duration):.3f}:d={fade_duration}"
        visual_filters.append(
            f"[{index}:v]trim=duration={duration},setpts=PTS-STARTPTS,"
            f"fps={frame_rate},scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=0x101827{fade_filter}[v{index}]"
        )

    voiceover_index = len(task.beats)
    command.extend(["-i", str(Path(task.voiceover_asset.stored_path).resolve())])
    concat_inputs = "".join(f"[v{index}]" for index in range(len(task.beats)))
    subtitle_style = "FontName=Microsoft YaHei,FontSize=30,PrimaryColour=&H00FFFFFF,OutlineColour=&H90000000,BorderStyle=1,Outline=2,Alignment=2,MarginV=60"
    filters = visual_filters + [
        f"{concat_inputs}concat=n={len(task.beats)}:v=1:a=0[visual]",
        f"[visual]subtitles=filename='{_filter_path(subtitles)}':force_style='{subtitle_style}'[captioned]",
        f"[{voiceover_index}:a]aresample=48000,apad=pad_dur={task.target_seconds}[audio]",
    ]
    current_label = "captioned"
    effect_index = 0
    font_path = "C\\:/Windows/Fonts/msyh.ttc"
    for directive in _enabled_directives(task, "card.show"):
        if directive.end_seconds <= directive.start_seconds or not directive.text:
            continue
        next_label = f"effect{effect_index}"
        filters.append(
            f"[{current_label}]drawtext=fontfile='{font_path}':text='{_drawtext_escape(directive.text)}':"
            f"fontcolor=white:fontsize={max(36, round(height * 0.055))}:box=1:boxcolor=0x101827@0.88:boxborderw=40:"
            f"x=(w-text_w)/2:y=(h-text_h)/2:enable='between(t,{directive.start_seconds},{directive.end_seconds})'[{next_label}]"
        )
        current_label = next_label
        effect_index += 1
    for directive in _enabled_directives(task, "highlight.rect"):
        if directive.end_seconds <= directive.start_seconds:
            continue
        next_label = f"effect{effect_index}"
        filters.append(
            f"[{current_label}]drawbox=x=iw*{directive.x}:y=ih*{directive.y}:w=iw*{directive.width}:h=ih*{directive.height}:"
            f"color={_color_for_ffmpeg(directive.color)}@0.95:t=5:enable='between(t,{directive.start_seconds},{directive.end_seconds})'[{next_label}]"
        )
        current_label = next_label
        effect_index += 1
    filters = ";".join(filters)
    command.extend([
        "-filter_complex", filters,
        "-map", f"[{current_label}]", "-map", "[audio]", "-t", str(task.target_seconds),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
        "-progress", "pipe:1", "-nostats", "-loglevel", "error", str(output),
    ])
    if on_progress:
        on_progress(5)
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace")
    stderr = ""
    try:
        assert process.stdout is not None
        while process.poll() is None:
            if cancel_event and cancel_event.is_set():
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                raise RenderCancelled()
            line = process.stdout.readline().strip()
            if not line:
                continue
            if line.startswith("out_time_us="):
                try:
                    seconds = int(line.split("=", 1)[1]) / 1_000_000
                    if on_progress:
                        on_progress(min(95, max(5, int(seconds / task.target_seconds * 95))))
                except ValueError:
                    pass
        stderr = process.stderr.read() if process.stderr else ""
    finally:
        if process.poll() is None:
            process.kill()
        if process.stdout:
            process.stdout.close()
        if process.stderr:
            process.stderr.close()
    if cancel_event and cancel_event.is_set():
        output.unlink(missing_ok=True)
        raise RenderCancelled()
    if process.returncode != 0 or not output.is_file():
        output.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg 导出失败：" + stderr[-1200:])
    if on_progress:
        on_progress(100)
    return ContentVideoExport(
        generated_at=time.time(), file_name=output.name, stored_path=str(output),
        subtitle_file_name=subtitles.name, duration_seconds=float(task.target_seconds), size_bytes=output.stat().st_size, profile=profile,
    )
