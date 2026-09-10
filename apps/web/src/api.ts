export type Platform = 'douyin' | 'xiaohongshu' | 'bilibili' | 'video_account';
type AssetKind = 'audio' | 'screen' | 'image' | 'generated_card';
type AssetStatus = 'ready' | 'missing' | 'uploaded';
export interface Asset { id: string; label: string; kind: AssetKind; required: boolean; instruction: string; target_seconds: number; status: AssetStatus; file_name?: string | null; }
export interface Beat { id: string; title: string; voiceover: string; visual_goal: string; start_seconds: number; end_seconds: number; asset: Asset; }
export interface Task { task_id: string; title: string; audience: string; platform: Platform; target_seconds: number; status: 'prepare_assets' | 'ready_for_assembly' | 'rough_cut_ready'; voiceover_asset: Asset; beats: Beat[]; rough_cut?: { edit_plan: Record<string, unknown> } | null; }
const base = '/api/v1';
async function request<T>(path: string, options?: RequestInit): Promise<T> { const res = await fetch(base + path, options); if (!res.ok) { const body = await res.json().catch(() => ({})) as { detail?: string }; throw new Error(body.detail || '请求失败'); } return res.json() as Promise<T>; }
export const listTasks = () => request<Task[]>('/content/tasks');
export const createTask = (input: Pick<Task, 'title' | 'audience' | 'platform' | 'target_seconds'>) => request<Task>('/content/tasks', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(input) });
export const saveTask = (task: Task) => request<Task>('/content/tasks/' + encodeURIComponent(task.task_id), { method: 'PUT', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({ title: task.title, audience: task.audience, platform: task.platform, target_seconds: task.target_seconds, voiceover_asset: task.voiceover_asset, beats: task.beats }) });
export async function upload(taskId: string, assetId: string, file: File): Promise<Task> { const res = await fetch(`${base}/content/tasks/${encodeURIComponent(taskId)}/assets/${encodeURIComponent(assetId)}`, {method: 'POST', body: file, headers: {'Content-Type': file.type || 'application/octet-stream', 'X-File-Name': file.name}}); if (!res.ok) { const body = await res.json().catch(() => ({})) as {detail?: string}; throw new Error(body.detail || '上传失败'); } return res.json() as Promise<Task>; }
export const roughCut = (taskId: string) => request<Task>('/content/tasks/' + encodeURIComponent(taskId) + '/rough-cut', {method: 'POST'});
