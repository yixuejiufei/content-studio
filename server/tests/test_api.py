from fastapi.testclient import TestClient

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
