import React, { useState } from 'react';

interface SettingsAccountProps {
  user?: { email: string } | null;
  onLogout: () => void;
}

const SettingsAccount: React.FC<SettingsAccountProps> = ({ user, onLogout }) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState('');
  const [deleting, setDeleting] = useState(false);
  const [deleted, setDeleted] = useState(false);
  const [error, setError] = useState('');

  const handleDeleteAccount = async () => {
    if (!user?.email || confirmEmail !== user.email) return;
    setDeleting(true);
    setError('');
    try {
      const API_BASE =
        import.meta.env.VITE_API_BASE_URL ||
        (typeof window !== 'undefined' && window.location.port === '5173'
          ? 'http://localhost:8000'
          : '');
      const res = await fetch(`${API_BASE}/api/studio/account`, {
        method: 'DELETE',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!res.ok) throw new Error('계정 삭제 요청 실패');
      setDeleted(true);
      setTimeout(() => onLogout(), 500);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '오류가 발생했습니다');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">로그인 정보</h2>
        <div className="rounded-xl border border-slate-200 p-4 space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-slate-700">Google 계정</p>
              <p className="text-sm text-slate-500">{user?.email || '-'}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-red-600 mb-4">위험 구역</h2>
        <div className="rounded-xl border border-red-200 p-4 space-y-3">
          {deleted ? (
            <div className="rounded-lg bg-green-50 border border-green-200 p-3">
              <p className="text-sm text-green-700 font-medium">계정이 비활성화되었습니다. 잠시 후 로그아웃됩니다.</p>
            </div>
          ) : showDeleteConfirm ? (
            <>
              <p className="text-sm text-slate-600">
                계정을 삭제하면 모든 프로젝트와 데이터가 영구적으로 삭제됩니다.
                확인을 위해 이메일 주소를 입력해주세요.
              </p>
              <input
                type="text"
                value={confirmEmail}
                onChange={(e) => setConfirmEmail(e.target.value)}
                placeholder={user?.email || '이메일 입력'}
                className="w-full rounded-lg border border-red-200 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-400"
              />
              {error && <p className="text-xs text-red-600">{error}</p>}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={handleDeleteAccount}
                  disabled={confirmEmail !== user?.email || deleting}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                >
                  {deleting ? '처리 중...' : '계정 영구 삭제'}
                </button>
                <button
                  type="button"
                  onClick={() => { setShowDeleteConfirm(false); setConfirmEmail(''); setError(''); }}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50 transition-colors"
                >
                  취소
                </button>
              </div>
            </>
          ) : (
            <>
              <p className="text-sm text-slate-600">
                계정을 삭제하면 모든 데이터가 영구적으로 제거됩니다.
              </p>
              <button
                type="button"
                onClick={() => setShowDeleteConfirm(true)}
                className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
              >
                계정 삭제
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsAccount;
