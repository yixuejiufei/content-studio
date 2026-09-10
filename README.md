# Content Studio

面向 Build in Public 创作者的本地内容生产工作间。它把一条视频从想法变成一份可检查的生产清单：

```text
选题与受众 → 台词/分镜 → 待录素材 → 上传素材 → 可审阅的粗剪方案
```

第一版只专注三个动作：创建内容任务、准备并上传素材、生成粗剪方案。它不渲染 MP4，也不取代剪映或 Premiere；输出的 `contentstudio-edit-plan` 是给创作者审阅、再交给剪辑工具执行的明确计划。

## 运行

后端（Python 3.11+）：

```powershell
cd server
python -m pip install -e ".[dev]"
uvicorn contentstudio.main:app --reload --port 8010
```

前端（Node 20+）：

```powershell
cd apps/web
npm install
npm run dev
```

前端开发服务器为 `/api` 代理到 `http://127.0.0.1:8010`。数据默认保存在 `server/content-studio.db`，素材默认保存在 `server/content-media`；可通过 `CONTENT_STUDIO_DB_PATH` 和 `CONTENT_STUDIO_MEDIA_DIR` 改写。

## 当前边界

- 本地、离线的创作规划工具；不需要线上大模型。
- 创建时生成可编辑的起步台词和画面任务，适合「为了弄懂 Agent，我决定把 Agent 的每一步都展示出来」这一系列。
- 用户需要提供旁白、录屏或图片；生成的粗剪方案只在必需素材齐全后出现。
- 后续再接入本地小模型、字幕、音频波形与实际渲染，但不混入这一版的工作流验证。

## 致谢

粗剪方案采用“可审阅的编辑操作”这一产品思路，受 [Timeline Studio](https://github.com/MartinDelophy/ai-video-editor) 启发；本项目没有复制其源代码，也不宣称项目格式兼容。详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
