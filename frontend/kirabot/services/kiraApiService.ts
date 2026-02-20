import { AnalyzeResponse, ChatResponse, SessionStats } from '../types';

const API_BASE_URL = (
  import.meta.env.VITE_KIRA_API_BASE_URL?.trim()
  || (typeof window !== 'undefined'
    ? `${window.location.protocol}//${window.location.hostname}:8000`
    : 'http://localhost:8000')
).replace(/\/+$/, '');

async function fetchWithError(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init);
  } catch (error) {
    const reason = error instanceof Error ? error.message : '네트워크 오류';
    throw new Error(`API 서버 연결 실패 (${API_BASE_URL}): ${reason}`);
  }
}

async function parseJson<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = '요청 처리 중 오류가 발생했습니다.';
    try {
      const data = await response.json();
      if (typeof data?.detail === 'string' && data.detail.trim()) {
        detail = data.detail;
      }
    } catch {
      // noop
    }
    throw new Error(detail);
  }
  return response.json() as Promise<T>;
}

export async function createSession(): Promise<string> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session`, {
    method: 'POST',
  });
  const data = await parseJson<{ session_id: string }>(response);
  return data.session_id;
}

export async function getSessionStats(sessionId: string): Promise<SessionStats> {
  const response = await fetchWithError(`${API_BASE_URL}/api/session/stats`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<SessionStats>(response);
}

export async function uploadCompanyDocuments(sessionId: string, files: File[]): Promise<{ company_chunks: number; added_chunks: number }> {
  const form = new FormData();
  form.append('session_id', sessionId);
  files.forEach((file) => form.append('files', file));

  const response = await fetchWithError(`${API_BASE_URL}/api/company/upload`, {
    method: 'POST',
    body: form,
  });
  return parseJson<{ company_chunks: number; added_chunks: number }>(response);
}

export async function clearCompanyDocuments(sessionId: string): Promise<{ company_chunks: number }> {
  const response = await fetchWithError(`${API_BASE_URL}/api/company/clear`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
  return parseJson<{ company_chunks: number }>(response);
}

export async function analyzeDocument(sessionId: string, file: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append('session_id', sessionId);
  form.append('file', file);

  const response = await fetchWithError(`${API_BASE_URL}/api/analyze/upload`, {
    method: 'POST',
    body: form,
  });
  return parseJson<AnalyzeResponse>(response);
}

export async function chatWithReferences(sessionId: string, message: string): Promise<ChatResponse> {
  const response = await fetchWithError(`${API_BASE_URL}/api/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, message }),
  });
  return parseJson<ChatResponse>(response);
}

export function getApiBaseUrl(): string {
  return API_BASE_URL;
}
