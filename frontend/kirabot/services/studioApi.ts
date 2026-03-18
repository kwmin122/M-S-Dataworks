/**
 * Studio API client — project CRUD and stage management.
 */

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (typeof window !== 'undefined' && window.location.port === '5173'
    ? 'http://localhost:8000'
    : '');

async function studioFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(init?.headers || {}) },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    let userMessage = `오류 ${res.status}`;
    try {
      const json = JSON.parse(body);
      if (json.detail) userMessage = json.detail;
    } catch { /* non-JSON body */ }
    throw new Error(userMessage);
  }
  return res.json();
}

// --- Types ---

export interface StudioProject {
  id: string;
  title: string;
  status: string;
  project_type: string;
  studio_stage: string | null;
  pinned_style_skill_id: string | null;
  active_analysis_snapshot_id: string | null;
  rfp_source_type: string | null;
  rfp_source_ref: string | null;
  created_at: string;
  updated_at: string;
}

export type StudioStage =
  | 'rfp'
  | 'package'
  | 'company'
  | 'style'
  | 'generate'
  | 'review'
  | 'relearn';

export const STUDIO_STAGES: { key: StudioStage; label: string }[] = [
  { key: 'rfp', label: '공고' },
  { key: 'package', label: '제출 패키지' },
  { key: 'company', label: '회사 역량' },
  { key: 'style', label: '스타일 학습' },
  { key: 'generate', label: '생성' },
  { key: 'review', label: '검토/보완' },
  { key: 'relearn', label: '재학습' },
];

// --- API functions ---

export type RfpSourceType = 'upload' | 'nara_search' | 'manual';

export async function createStudioProject(params: {
  title: string;
  from_analysis_snapshot_id?: string;
  rfp_source_type?: RfpSourceType;
  rfp_source_ref?: string;
}): Promise<StudioProject> {
  return studioFetch('/api/studio/projects', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function listStudioProjects(): Promise<StudioProject[]> {
  return studioFetch('/api/studio/projects');
}

export async function getStudioProject(projectId: string): Promise<StudioProject> {
  return studioFetch(`/api/studio/projects/${projectId}`);
}

export async function updateStudioStage(
  projectId: string,
  stage: StudioStage,
): Promise<StudioProject> {
  return studioFetch(`/api/studio/projects/${projectId}/stage`, {
    method: 'PATCH',
    body: JSON.stringify({ studio_stage: stage }),
  });
}
