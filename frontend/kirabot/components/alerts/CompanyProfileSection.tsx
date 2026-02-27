import React, { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
import type { AlertCompanyProfile } from '../../services/kiraApiService';

interface CompanyProfileSectionProps {
  profile: AlertCompanyProfile | undefined;
  onChange: (profile: AlertCompanyProfile) => void;
}

export const CompanyProfileSection: React.FC<CompanyProfileSectionProps> = ({
  profile,
  onChange,
}) => {
  const [showAdvanced, setShowAdvanced] = useState(false);

  const updateDescription = (description: string) => {
    onChange({ ...profile, description });
  };

  const updateField = (field: keyof AlertCompanyProfile, value: string[]) => {
    onChange({ ...profile, [field]: value });
  };

  const parseCommaSeparated = (text: string): string[] => {
    return text.split(',').map(s => s.trim()).filter(s => s.length > 0);
  };

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-6">
      <h2 className="text-base font-semibold text-slate-700">회사 프로필</h2>
      <p className="mt-1 text-sm text-slate-500">
        자연어로 회사 역량을 입력하면 LLM이 자격요건과 비교합니다 (Pro 버전 전용)
      </p>

      <div className="mt-4">
        <label className="block text-sm font-medium text-slate-700">
          회사 설명 (자연어)
        </label>
        <textarea
          value={profile?.description || ''}
          onChange={(e) => updateDescription(e.target.value)}
          placeholder="예시: 우리 회사는 교통신호등 및 CCTV 제조 전문 업체입니다. 물품분류번호 42101, 42105를 취급하며, 안산/부산 지역 공고는 제외합니다. ISO 9001 인증 보유."
          rows={6}
          className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
        />
      </div>

      {/* Collapsible Advanced Fields */}
      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1 text-sm font-medium text-primary-600 hover:text-primary-700"
        >
          {showAdvanced ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
          구조화된 입력 (선택)
        </button>

        {showAdvanced && (
          <div className="mt-4 space-y-4 rounded-lg border border-slate-200 bg-slate-50 p-4">
            <div>
              <label className="block text-sm font-medium text-slate-700">
                주력 제품 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.mainProducts?.join(', ') || ''}
                onChange={(e) => updateField('mainProducts', parseCommaSeparated(e.target.value))}
                placeholder="교통신호등, CCTV, 주차관제시스템"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                보유 인증 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.certifications?.join(', ') || ''}
                onChange={(e) => updateField('certifications', parseCommaSeparated(e.target.value))}
                placeholder="ISO 9001, KS 인증, 벤처기업 확인서"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700">
                제외 지역/품목 (쉼표 구분)
              </label>
              <input
                type="text"
                value={profile?.excludedAreas?.join(', ') || ''}
                onChange={(e) => updateField('excludedAreas', parseCommaSeparated(e.target.value))}
                placeholder="안산, 부산, 유지보수만"
                className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default CompanyProfileSection;
