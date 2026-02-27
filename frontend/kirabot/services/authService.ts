import { User } from '../types';

const API_BASE_URL = (
  import.meta.env.VITE_KIRA_API_BASE_URL?.trim()
  || (typeof window !== 'undefined' && window.location.origin !== 'http://localhost:5173'
    ? window.location.origin
    : 'http://localhost:8000')
).replace(/\/+$/, '');

const GOOGLE_LOGIN_URL = import.meta.env.VITE_GOOGLE_LOGIN_URL?.trim() || `${API_BASE_URL}/auth/google/login`;
const KAKAO_LOGIN_URL = `${API_BASE_URL}/auth/kakao/login`;
const AUTH_ME_URL = import.meta.env.VITE_AUTH_ME_URL?.trim() || `${API_BASE_URL}/auth/me`;
const AUTH_LOGOUT_URL = import.meta.env.VITE_AUTH_LOGOUT_URL?.trim() || `${API_BASE_URL}/auth/logout`;

interface AuthMeResponse {
  ok?: boolean;
  user?: {
    id?: string;
    username?: string;
    email?: string;
    name?: string;
    avatar_url?: string;
    isAdmin?: boolean;
  };
}

function mapAuthUser(payload: AuthMeResponse['user']): User | null {
  if (!payload) {
    return null;
  }
  const userId = String(payload.id || payload.username || '').trim();
  const email = String(payload.email || '').trim();
  if (!userId) {
    return null;
  }
  return {
    id: userId,
    name: String(payload.name || payload.username || email || 'M&S 사용자'),
    email,
    avatarUrl: String(payload.avatar_url || ''),
    isAdmin: Boolean(payload.isAdmin),
  };
}

export function isGoogleOAuthConfigured(): boolean {
  // In production (same-origin), always configured via API_BASE_URL fallback
  return Boolean(GOOGLE_LOGIN_URL);
}

export async function signInWithGoogle(): Promise<void> {
  if (!GOOGLE_LOGIN_URL) {
    throw new Error('VITE_GOOGLE_LOGIN_URL 환경변수를 설정해주세요. 예: http://localhost:8000/auth/google/login');
  }
  sessionStorage.setItem('kira_post_login_target', 'dashboard');
  window.location.assign(GOOGLE_LOGIN_URL);
}

export async function getCurrentGoogleUser(): Promise<User | null> {
  if (!AUTH_ME_URL) {
    return null;
  }
  let response: Response;
  try {
    response = await fetch(AUTH_ME_URL, {
      method: 'GET',
      credentials: 'include',
    });
  } catch (error) {
    const reason = error instanceof Error ? error.message : '네트워크 오류';
    throw new Error(
      `인증 서버 연결 실패: ${AUTH_ME_URL} (${reason}). ` +
      '백엔드 실행 상태와 CORS(WEB_API_ALLOW_ORIGINS)에 현재 프론트 주소가 포함되어 있는지 확인하세요.'
    );
  }
  if (!response.ok) {
    return null;
  }
  const payload = (await response.json()) as AuthMeResponse;
  return mapAuthUser(payload.user);
}

export function consumePostLoginTarget(): boolean {
  const value = sessionStorage.getItem('kira_post_login_target');
  if (!value) {
    return false;
  }
  sessionStorage.removeItem('kira_post_login_target');
  return value === 'dashboard';
}

export async function signInWithKakao(): Promise<void> {
  sessionStorage.setItem('kira_post_login_target', 'dashboard');
  window.location.assign(KAKAO_LOGIN_URL);
}

export async function signOutGoogleUser(): Promise<void> {
  if (!AUTH_LOGOUT_URL) {
    return;
  }
  const response = await fetch(AUTH_LOGOUT_URL, {
    method: 'POST',
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('로그아웃 요청에 실패했습니다. 잠시 후 다시 시도해주세요.');
  }
}
