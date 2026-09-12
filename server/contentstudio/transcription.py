"""Optional, fully local voiceover transcription with faster-whisper."""

from __future__ import annotations

import os
import time
from pathlib import Path

from .schemas import SubtitleAlignment, SubtitleSegment


class LocalTranscriptionUnavailable(RuntimeError):
    """Raised when the creator has not prepared an offline speech model."""


def _model_path() -> Path:
    configured = os.getenv("CONTENT_STUDIO_WHISPER_MODEL_PATH")
    if not configured:
        raise LocalTranscriptionUnavailable(
            "未设置本地语音模型。请设置 CONTENT_STUDIO_WHISPER_MODEL_PATH，"
            "指向已下载的 faster-whisper 模型目录。"
        )
    path = Path(configured).expanduser().resolve()
    if not path.is_dir():
        raise LocalTranscriptionUnavailable("本地语音模型目录不存在：" + str(path))
    return path


def align_voiceover(audio_path: Path, language: str = "zh") -> SubtitleAlignment:
    """Transcribe one local voiceover without model downloads or GPU use."""
    if not audio_path.is_file():
        raise ValueError("旁白音频文件不存在")
    model_path = _model_path()
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise LocalTranscriptionUnavailable(
            "未安装本地转写组件。请安装 Content Studio 的 local-transcription 可选依赖。"
        ) from exc

    model = WhisperModel(str(model_path), device="cpu", compute_type="int8")
    result, _info = model.transcribe(str(audio_path), language=language, beam_size=1, vad_filter=True)
    segments: list[SubtitleSegment] = []
    for index, segment in enumerate(result, start=1):
        text = segment.text.strip()
        start, end = max(0.0, float(segment.start)), float(segment.end)
        if text and end > start:
            segments.append(SubtitleSegment(id=f"subtitle-{index:04d}", start_seconds=start, end_seconds=end, text=text))
    if not segments:
        raise ValueError("没有识别到可用语音；请确认上传的是包含旁白的人声音频。")
    return SubtitleAlignment(source="local_whisper", language=language, model_name=model_path.name, segments=segments, generated_at=time.time())
