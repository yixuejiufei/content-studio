export type Platform = 'douyin' | 'xiaohongshu' | 'bilibili' | 'video_account';
export type RenderProfile = 'preview_720p' | 'publish_1080p' | 'vertical_1080p';
type AssetKind = 'audio' | 'screen' | 'image' | 'generated_card';
type AssetStatus = 'ready' | 'missing' | 'uploaded';
export interface Asset { id: string; label: string; kind: AssetKind; required: boolean; instruction: string; target_seconds: number; status: AssetStatus; file_name?: string | null; }
export interface Beat { id: string; title: string; voiceover: string; visual_goal: string; start_seconds: number; end_seconds: number; asset: Asset; }
export interface VideoExport { file_name: string; subtitle_file_name: string; duration_seconds: number; size_bytes: number; subtitle_source: 'script' | 'local_whisper'; }
export interface SubtitleSegment { id: string; start_seconds: number; end_seconds: number; text: string; }
export interface SubtitleAlignment { source: 'script' | 'local_whisper'; language: string; model_name?: string | null; segments: SubtitleSegment[]; generated_at: number; }
export interface RenderDirective { id: string; type: 'card.show' | 'transition.fade' | 'focus.zoom' | 'highlight.rect' | 'audio.duck' | 'privacy.mask'; enabled: boolean; beat_id?: string | null; start_seconds: number; end_seconds: number; text?: string | null; color: string; x: number; y: number; width: number; height: number; fade_seconds: number; volume: number; mask_mode?: 'blur' | 'pixelate' | 'solid'; }
export interface RenderJob { job_id: string; task_id: string; profile: RenderProfile; status: 'queued' | 'rendering' | 'completed' | 'failed' | 'cancelled'; progress_percent: number; cancel_requested: boolean; error?: string | null; output?: VideoExport | null; }
export interface Task { task_id: string; title: string; audience: string; platform: Platform; target_seconds: number; status: 'prepare_assets' | 'ready_for_assembly' | 'rough_cut_ready'; voiceover_asset: Asset; music_asset?: Asset | null; subtitle_alignment?: SubtitleAlignment | null; beats: Beat[]; render_directives: RenderDirective[]; rough_cut?: { edit_plan: Record<string, unknown> } | null; video_export?: VideoExport | null; }
const base = '/api/v1';
async function request<T>(path: string, options?: RequestInit): Promise<T> { const res = await fetch(base + path, options); if (!res.ok) { const body = await res.json().catch(() => ({})) as { detail?: string }; throw new Error(body.detail || '请求失败'); } return res.json() as Promise<T>; }
export const listTasks = () => request<Task[]>('/content/tasks');
export const createTask = (input: Pick<Task, 'title' | 'audience' | 'platform' | 'target_seconds'>) => request<Task>('/content/tasks', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(input) });
export const saveTask = (task: Task) => request<Task>('/content/tasks/' + encodeURIComponent(task.task_id), { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ title: task.title, audience: task.audience, platform: task.platform, target_seconds: task.target_seconds, voiceover_asset: task.voiceover_asset, music_asset: task.music_asset, subtitle_alignment: task.subtitle_alignment, beats: task.beats, render_directives: task.render_directives }) });
export const alignSubtitles = (taskId: string, language = 'zh') => request<Task>('/content/tasks/' + encodeURIComponent(taskId) + '/subtitle-alignment', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({language})});
export async function upload(taskId: string, assetId: string, file: File): Promise<Task> { const res = await fetch(`${base}/content/tasks/${encodeURIComponent(taskId)}/assets/${encodeURIComponent(assetId)}`, {method: 'POST', body: file, headers: {'Content-Type': file.type || 'application/octet-stream', 'X-File-Name': file.name}}); if (!res.ok) { const body = await res.json().catch(() => ({})) as {detail?: string}; throw new Error(body.detail || '上传失败'); } return res.json() as Promise<Task>; }
export const roughCut = (taskId: string) => request<Task>('/content/tasks/' + encodeURIComponent(taskId) + '/rough-cut', {method: 'POST'});
export const exportRoughCut = (taskId: string) => request<Task>('/content/tasks/' + encodeURIComponent(taskId) + '/export', {method: 'POST'});
export const exportDownloadUrl = (taskId: string) => `${base}/content/tasks/${encodeURIComponent(taskId)}/export`;
export const assetDownloadUrl = (taskId: string, assetId: string) => `${base}/content/tasks/${encodeURIComponent(taskId)}/assets/${encodeURIComponent(assetId)}`;
export const createRenderJob = (taskId: string, profile: RenderProfile) => request<RenderJob>('/content/tasks/' + encodeURIComponent(taskId) + '/render-jobs', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({profile})});
export const getRenderJob = (jobId: string) => request<RenderJob>('/content/render-jobs/' + encodeURIComponent(jobId));
export const cancelRenderJob = (jobId: string) => request<RenderJob>('/content/render-jobs/' + encodeURIComponent(jobId) + '/cancel', {method: 'POST'});
export const renderDownloadUrl = (jobId: string) => `${base}/content/render-jobs/${encodeURIComponent(jobId)}/download`;
export const renderPreviewUrl = (jobId: string) => `${base}/content/render-jobs/${encodeURIComponent(jobId)}/preview`;
