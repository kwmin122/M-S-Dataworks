import React from 'react';

interface SettingsAccountProps {
  user?: { email: string } | null;
  onLogout: () => void;
}

const SettingsAccount: React.FC<SettingsAccountProps> = ({ user, onLogout }) => {

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
          <p className="text-sm text-slate-600">
            계정 삭제는 현재 준비 중입니다. 탈퇴를 원하시면 고객지원으로 문의해주세요.
          </p>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-lg border border-red-300 px-4 py-2 text-sm font-medium text-red-600 hover:bg-red-50 transition-colors"
          >
            로그아웃
          </button>
        </div>
      </div>
    </div>
  );
};

export default SettingsAccount;
