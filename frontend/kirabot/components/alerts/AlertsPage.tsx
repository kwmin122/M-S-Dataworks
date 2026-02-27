import React, { useState, useEffect } from 'react';
import { Bell, Save, X } from 'lucide-react';
import CompanyProfileSection from './CompanyProfileSection';
import AlertFilterSection from './AlertFilterSection';
import type { AlertCompanyProfile, AlertRule } from '../../services/kiraApiService';

export const AlertsPage: React.FC = () => {
  const [email, setEmail] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [loading, setLoading] = useState(true);
  const [companyProfile, setCompanyProfile] = useState<AlertCompanyProfile>({
    description: '',
  });
  const [rules, setRules] = useState<AlertRule[]>([]);

  useEffect(() => {
    // TODO: Load config from API
    setLoading(false);
  }, []);

  const handleAddRule = () => {
    const newRule: AlertRule = {
      id: `rule${Date.now()}`,
      keywords: [],
      excludeKeywords: [],
      categories: [],
      regions: [],
      excludeRegions: [],
      productCodes: [],
      detailedItems: [],
      enabled: true,
    };
    setRules([...rules, newRule]);
  };

  const handleUpdateRule = (index: number, rule: AlertRule) => {
    const updated = [...rules];
    updated[index] = rule;
    setRules(updated);
  };

  const handleDeleteRule = (index: number) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="text-slate-400">로딩 중...</div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col bg-slate-50">
      {/* Header */}
      <div className="shrink-0 border-b border-slate-200 bg-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bell size={20} className="text-primary-600" />
            <h1 className="text-lg font-bold text-slate-800">알림 설정</h1>
          </div>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-sm text-slate-600">전체 활성화</span>
            <input
              type="checkbox"
              checked={enabled}
              onChange={(e) => setEnabled(e.target.checked)}
              className="rounded border-slate-300"
            />
          </label>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        <div className="mx-auto max-w-3xl space-y-6">
          {/* Basic Settings Placeholder */}
          <div className="rounded-xl border border-slate-200 bg-white p-6">
            <h2 className="text-base font-semibold text-slate-700">기본 설정</h2>
            <div className="mt-4 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">이메일</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="alert@example.com"
                  className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
                />
              </div>
            </div>
          </div>

          {/* Company Profile Section */}
          <CompanyProfileSection
            profile={companyProfile}
            onChange={setCompanyProfile}
          />

          {/* Alert Filter Section */}
          <AlertFilterSection
            rules={rules}
            onAddRule={handleAddRule}
            onUpdateRule={handleUpdateRule}
            onDeleteRule={handleDeleteRule}
          />
        </div>
      </div>

      {/* Footer */}
      <div className="shrink-0 border-t border-slate-200 bg-white px-6 py-4">
        <div className="mx-auto flex max-w-3xl justify-end gap-2">
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
          >
            <X size={16} />
            취소
          </button>
          <button
            type="button"
            className="flex items-center gap-1.5 rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white hover:bg-primary-700"
          >
            <Save size={16} />
            저장
          </button>
        </div>
      </div>
    </div>
  );
};

export default AlertsPage;
