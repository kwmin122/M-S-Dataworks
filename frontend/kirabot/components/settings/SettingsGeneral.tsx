import React from 'react';

interface SettingsGeneralProps {
  user?: { name: string; email: string; avatarUrl?: string } | null;
}

const SettingsGeneral: React.FC<SettingsGeneralProps> = ({ user }) => {
  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">프로필</h2>
        <div className="flex items-center gap-4 rounded-xl border border-slate-200 bg-slate-50 p-4">
          {user?.avatarUrl ? (
            <img src={user.avatarUrl} alt="" className="h-14 w-14 rounded-full" />
          ) : (
            <div className="flex h-14 w-14 items-center justify-center rounded-full bg-kira-100 text-lg font-bold text-kira-600">
              {user?.name?.charAt(0) || '?'}
            </div>
          )}
          <div>
            <p className="text-base font-medium text-slate-900">{user?.name || '사용자'}</p>
            <p className="text-sm text-slate-500">{user?.email || ''}</p>
          </div>
        </div>
      </div>

      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-4">모양</h2>
        <div className="rounded-xl border border-slate-200 p-4">
          <p className="text-sm font-medium text-slate-700 mb-3">테마</p>
          <div className="flex gap-3">
            {(['시스템', '라이트', '다크'] as const).map((label) => (
              <label key={label} className="flex items-center gap-2 cursor-pointer">
                <input
                  type="radio"
                  name="theme"
                  value={label}
                  defaultChecked={label === '라이트'}
                  className="text-kira-600 focus:ring-kira-500"
                />
                <span className="text-sm text-slate-700">{label}</span>
              </label>
            ))}
          </div>
          <p className="text-xs text-slate-400 mt-2">테마 기능은 추후 지원 예정입니다.</p>
        </div>
      </div>
    </div>
  );
};

export default SettingsGeneral;
