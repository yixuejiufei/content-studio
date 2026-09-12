"""Deterministic, creator-editable planning for the first Content Studio MVP."""

from __future__ import annotations

import time
import uuid
from pathlib import Path

from .schemas import ContentAssetSlot, ContentBeat, ContentRoughCut, ContentTask, RenderDirective, RoughCutItem


def _slot(slot_id: str, label: str, kind: str, instruction: str, seconds: float, *, required: bool = True) -> ContentAssetSlot:
    return ContentAssetSlot(
        id=slot_id, label=label, kind=kind, instruction=instruction, target_seconds=seconds,
        required=required, status="missing" if required else "ready",
    )


def _beat(
    beat_id: str, title: str, voiceover: str, visual_goal: str,
    start_seconds: float, end_seconds: float, asset: ContentAssetSlot,
) -> ContentBeat:
    return ContentBeat(
        id=beat_id, title=title, voiceover=voiceover, visual_goal=visual_goal,
        start_seconds=start_seconds, end_seconds=end_seconds, asset=asset,
    )


def draft_content_task(title: str, audience: str, platform: str, target_seconds: int) -> ContentTask:
    """Return a starter script and a concrete list of creator-supplied assets."""
    now = time.time()
    at = lambda part: round(target_seconds * part / 90, 1)
    beats = [
        _beat("hook", "黑箱提问", "AI 给出答案时，你知道它刚刚做了什么吗？它可能查了资料，也可能直接猜了。", "用普通聊天回答和黑箱提问建立问题，不展示复杂产品功能。", 0, at(10), _slot("hook-blackbox", "黑箱开场文字卡", "generated_card", "黑底文字卡：它给了答案，但它做了什么？", at(10), required=False)),
        _beat("promise", "公开构建的承诺", f"所以为了弄懂 Agent，我决定把它每一步可验证的工作都展示出来。这是《{title}》的第一条记录。", "展示应用总览与 Build Log 编号，画面干净，避免鼠标寻找按钮。", at(10), at(18), _slot("promise-app", "应用启动与任务输入", "screen", "录制应用总览，并输入演示任务；保留标题和画布。", at(8))),
        _beat("context", "它看到了什么", "第一步不是回答。它先拿到任务、规则，以及它现在能调用的工具。", "只突出 Context 节点；其余节点压暗或在后期裁切掉。", at(18), at(34), _slot("context-screen", "Context 高亮录屏", "screen", "录制 Context 节点，必须看见用户任务、系统规则或工具定义。", at(16))),
        _beat("decision", "它选择了什么", "接下来模型要做选择：直接说答案，还是调用工具。这里，它选择了计算器，并传入参数。", "突出 LLM Think、call_tool、calculator 和表达式参数。", at(34), at(48), _slot("decision-screen", "LLM 决策录屏", "screen", "录制 LLM Think 与 call_tool；必须清楚显示 calculator 和参数。", at(14))),
        _beat("observation", "结果如何改变下一轮", "工具返回结果后，不会直接替它回答。结果会作为 Observation 写回下一轮上下文。", "展示工具返回值及 Observation 回到 Context 的边。", at(48), at(62), _slot("observation-screen", "工具与 Observation 录屏", "screen", "录制 calculator 返回结果，以及 Observation 回写 Context 的可视化。", at(14))),
        _beat("close", "最终输出与下一集", "我不只想展示成功。它算错、卡住、循环太多次，也应该被看见。接下来，我会继续公开构建这个让普通人看懂 Agent 的本地工具。", "展示完整轨迹、时间线或回放控制，最后落在可见的完整流程。", at(62), float(target_seconds), _slot("close-screen", "完整轨迹与回放录屏", "screen", "录制最终答案、事件时间线或回放按钮，并以完整流程图收尾。", at(28))),
    ]
    directives = [
        RenderDirective(id="card-intro", type="card.show", start_seconds=0, end_seconds=min(3, beats[0].end_seconds), text=title),
        *(RenderDirective(id=f"fade-{beat.id}", type="transition.fade", beat_id=beat.id, fade_seconds=0.25) for beat in beats),
        RenderDirective(id="focus-decision", type="focus.zoom", beat_id="decision", start_seconds=beats[3].start_seconds, end_seconds=min(beats[3].start_seconds + 5, beats[3].end_seconds), x=0.24, y=0.2, width=0.52, height=0.4),
        RenderDirective(id="highlight-decision", type="highlight.rect", beat_id="decision", start_seconds=beats[3].start_seconds, end_seconds=min(beats[3].start_seconds + 5, beats[3].end_seconds), text="工具选择与参数", x=0.3, y=0.25, width=0.42, height=0.28),
    ]
    return ContentTask(task_id=f"content-{uuid.uuid4().hex[:10]}", title=title, audience=audience, platform=platform, target_seconds=target_seconds, voiceover_asset=_slot("voiceover", "完整旁白音频", "audio", "录制完整旁白，可分段录制。保留 0.5 秒前后空白；不要混入背景音乐。", target_seconds), beats=beats, render_directives=directives, created_at=now, updated_at=now)


def all_slots(task: ContentTask) -> list[ContentAssetSlot]:
    return [task.voiceover_asset, *(beat.asset for beat in task.beats)]


def refresh_task_status(task: ContentTask) -> ContentTask:
    complete = all(not item.required or item.status in {"ready", "uploaded"} for item in all_slots(task))
    task.status = "rough_cut_ready" if task.rough_cut else "ready_for_assembly" if complete else "prepare_assets"
    task.updated_at = time.time()
    return task


def attach_asset(task: ContentTask, slot_id: str, file_name: str, stored_path: Path, mime_type: str, size_bytes: int) -> ContentTask:
    slot = next((item for item in all_slots(task) if item.id == slot_id), None)
    if slot is None:
        raise KeyError(slot_id)
    slot.status, slot.file_name, slot.stored_path, slot.mime_type, slot.size_bytes = "uploaded", file_name, str(stored_path), mime_type, size_bytes
    return refresh_task_status(task)


def build_rough_cut(task: ContentTask) -> ContentRoughCut:
    missing = [item.label for item in all_slots(task) if item.required and item.status not in {"ready", "uploaded"}]
    if missing:
        raise ValueError("仍缺少必需素材：" + "、".join(missing))
    items = [RoughCutItem(beat_id=beat.id, start_seconds=beat.start_seconds, end_seconds=beat.end_seconds, voiceover=beat.voiceover, visual_asset_slot_id=beat.asset.id, visual_file_name=beat.asset.file_name, edit_note=beat.visual_goal) for beat in task.beats]
    operations = [operation for index, item in enumerate(items, 1) for operation in (
        {"id": f"visual-{index:02d}", "type": "visual.place", "slotId": item.visual_asset_slot_id, "start": item.start_seconds, "end": item.end_seconds, "note": item.edit_note},
        {"id": f"caption-{index:02d}", "type": "caption.add", "start": item.start_seconds, "end": item.end_seconds, "text": item.voiceover},
    )]
    return ContentRoughCut(generated_at=time.time(), items=items, edit_plan={"schemaVersion": 1, "format": "contentstudio-edit-plan", "sourceTask": task.task_id, "voiceoverSlotId": task.voiceover_asset.id, "operations": operations, "reviewChecklist": ["核对旁白与镜头是否对应", "核对敏感信息是否已遮挡", "核对字幕断句与节奏"]})
