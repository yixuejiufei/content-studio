# Content Studio

面向 Build in Public 创作者的本地内容生产工作间。它把一条视频从想法变成一份可检查的生产清单：

```text
选题与受众 → 台词/分镜 → 待录素材 → 上传素材 → 粗剪计划 → 本地渲染任务 → MP4
```

第一版现已专注四个动作：创建内容任务、准备并上传素材、生成粗剪方案、自动导出基础 MP4。导出器会按分镜拼接画面、使用完整旁白作为主音轨、叠加基础字幕，并可混入创作者上传且有使用权的背景音乐；启用“BGM 压低”后，人声出现时会自动降低音乐音量。它仍不取代剪映或 Premiere，适合先生成可观看的初剪、再精修。

渲染以可轮询的本地任务运行，支持取消、失败保留上一版成片，以及三种预设：预览 720p、发布 1080p、竖屏 1080×1920。

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
- 用户需要提供完整旁白与各段录屏；必需素材齐全后可生成 1080p H.264/AAC MP4 和同名 SRT 字幕文件。
- 已支持文字卡、淡入淡出、局部放大、高亮框与旁白压低 BGM；目前不处理智能镜头选取、敏感信息遮挡和字幕逐词高亮。这些能力将在 [下一阶段计划](docs/NEXT_STAGE_PLAN.md) 中按可编辑、可追溯的渲染指令逐步实现。

## 致谢

粗剪方案采用“可审阅的编辑操作”这一产品思路，受 [Timeline Studio](https://github.com/MartinDelophy/ai-video-editor) 启发；本项目没有复制其源代码，也不宣称项目格式兼容。详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
