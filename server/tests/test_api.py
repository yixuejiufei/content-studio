from fastapi.testclient import TestClient
import subprocess
import time
from pathlib import Path

import imageio_ffmpeg

from contentstudio.main import app


def test_content_task_requires_assets_then_generates_an_inspectable_rough_cut() -> None:
    client = TestClient(app)
    response = client.post("/api/v1/content/tasks", json={"title": "为了弄懂 Agent，我决定把每一步展示出来", "audience": "想看懂 Agent 的普通学习者", "platform": "douyin", "target_seconds": 90})
    assert response.status_code == 201, response.text
    task = response.json()
    assert task["status"] == "prepare_assets"
    assert client.post(f"/api/v1/content/tasks/{task['task_id']}/rough-cut").status_code == 409
    for asset in [task["voiceover_asset"], *[beat["asset"] for beat in task["beats"]]]:
        if asset["required"]:
            upload = client.post(f"/api/v1/content/tasks/{task['task_id']}/assets/{asset['id']}", content=b"demo media", headers={"content-type": "audio/wav" if asset["kind"] == "audio" else "video/mp4", "x-file-name": f"{asset['id']}.bin"})
            assert upload.status_code == 200, upload.text
            task = upload.json()
    assert task["status"] == "ready_for_assembly"
    result = client.post(f"/api/v1/content/tasks/{task['task_id']}/rough-cut")
    assert result.status_code == 200, result.text
    assert result.json()["rough_cut"]["edit_plan"]["format"] == "contentstudio-edit-plan"


def test_short_task_timeline_scales_to_requested_duration() -> None:
    response = TestClient(app).post("/api/v1/content/tasks", json={"title": "15 秒预告", "audience": "测试观众", "target_seconds": 15})
    assert response.status_code == 201
    beats = response.json()["beats"]
    assert beats[-1]["end_seconds"] == 15
    assert all(beat["end_seconds"] > beat["start_seconds"] for beat in beats)


def test_export_generates_a_downloadable_mp4(tmp_path: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    screen = tmp_path / "screen.mp4"
    voice = tmp_path / "voice.wav"
    subprocess.run([ffmpeg, "-hide_banner", "-y", "-f", "lavfi", "-i", "color=c=blue:s=320x180:r=10", "-t", "1", "-c:v", "libx264", str(screen)], check=True, capture_output=True)
    subprocess.run([ffmpeg, "-hide_banner", "-y", "-f", "lavfi", "-i", "sine=frequency=440:sample_rate=48000", "-t", "1", str(voice)], check=True, capture_output=True)
    client = TestClient(app)
    created = client.post("/api/v1/content/tasks", json={"title": "可导出的短片", "audience": "测试观众", "target_seconds": 15})
    task = created.json()
    for asset in [task["voiceover_asset"], *[beat["asset"] for beat in task["beats"]]]:
        if not asset["required"]:
            continue
        source = voice if asset["kind"] == "audio" else screen
        upload = client.post(f"/api/v1/content/tasks/{task['task_id']}/assets/{asset['id']}", content=source.read_bytes(), headers={"content-type": "audio/wav" if asset["kind"] == "audio" else "video/mp4", "x-file-name": source.name})
        assert upload.status_code == 200, upload.text
    created_job = client.post(f"/api/v1/content/tasks/{task['task_id']}/render-jobs", json={"profile": "preview_720p"})
    assert created_job.status_code == 202, created_job.text
    job = created_job.json()
    assert job["status"] in {"queued", "rendering"}
    for _ in range(60):
        job = client.get(f"/api/v1/content/render-jobs/{job['job_id']}").json()
        if job["status"] not in {"queued", "rendering"}:
            break
        time.sleep(0.1)
    assert job["status"] == "completed", job.get("error")
    assert job["progress_percent"] == 100
    assert job["output"]["file_name"].endswith(".mp4")
    downloaded = client.get(f"/api/v1/content/render-jobs/{job['job_id']}/download")
    assert downloaded.status_code == 200
    assert downloaded.content[4:8] == b"ftyp"
