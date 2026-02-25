import React, { useState } from 'react';

interface SettingsAccountProps {
  user?: { email: string } | null;
  onLogout: () => void;
}

const SettingsAccount: React.FC<SettingsAccountProps> = ({ user, onLogout }) => {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

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
        <div className="rounded-xl border border-red-200 p-4">
          {!showDeleteConfirm ? (
            <button
              type="button"
              onClick={() => setShowDeleteConfirm(true)}
              className="text-sm text-red-600 hover:text-red-700 font-medium"
            >
              계정 삭제
            </button>
          ) : (
            <div className="space-y-3">
              <p className="text-sm text-slate-700">정말로 계정을 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.</p>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => setShowDeleteConfirm(false)}
                  className="rounded-lg border border-slate-300 px-4 py-2 text-sm text-slate-600 hover:bg-slate-50"
                >
                  취소
                </button>
                <button
                  type="button"
                  onClick={onLogout}
                  className="rounded-lg bg-red-600 px-4 py-2 text-sm text-white hover:bg-red-700"
                >
                  삭제 확인
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SettingsAccount;
