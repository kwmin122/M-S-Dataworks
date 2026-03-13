import React, { useState } from 'react';
import { X, Building2, Briefcase, Users, Check } from 'lucide-react';
import { TrackRecordInput, PersonnelInput } from '../../types';
import * as kiraApi from '../../services/kiraApiService';
import { sanitizeCompanyId } from '../../services/kiraApiService';

interface CompanyOnboardingModalProps {
  isOpen: boolean;
  onClose: () => void;
  onComplete: (companyName: string) => void;
  sessionId?: string;
}

type Step = 1 | 2 | 3;

const CompanyOnboardingModal: React.FC<CompanyOnboardingModalProps> = ({
  isOpen,
  onClose,
  onComplete,
  sessionId = '',
}) => {
  const [step, setStep] = useState<Step>(1);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Step 1: 회사명 + 실적
  const [companyName, setCompanyName] = useState('');
  const [projectName, setProjectName] = useState('');
  const [client, setClient] = useState('');
  const [periodStart, setPeriodStart] = useState('');
  const [periodEnd, setPeriodEnd] = useState('');

  // Step 2: 인력
  const [personnelName, setPersonnelName] = useState('');
  const [role, setRole] = useState('');
  const [experienceYears, setExperienceYears] = useState('');

  if (!isOpen) return null;

  const handleStep1Next = () => {
    if (!companyName.trim() || !projectName.trim() || !client.trim()) {
      setError('회사명, 프로젝트명, 발주처는 필수 입력 항목입니다.');
      return;
    }
    setError(null);
    setStep(2);
  };

  const handleStep2Next = () => {
    if (!personnelName.trim() || !role.trim() || !experienceYears.trim()) {
      setError('이름, 역할, 경력은 필수 입력 항목입니다.');
      return;
    }
    const years = parseInt(experienceYears, 10);
    if (isNaN(years) || years < 0) {
      setError('경력은 0 이상의 숫자를 입력해주세요.');
      return;
    }
    setError(null);
    setStep(3);
  };

  const handleComplete = async () => {
    setIsSubmitting(true);
    setError(null);

    try {
      // Get canonical company_id first
      let companyId: string;
      try {
        companyId = await kiraApi.getCanonicalCompanyId(companyName);
      } catch {
        companyId = sanitizeCompanyId(companyName);
      }

      // 1. 회사명 업데이트
      await kiraApi.updateCompanyDBProfile({ company_name: companyName }, companyId, sessionId);

      // 2. 실적 추가
      const trackRecord: TrackRecordInput = {
        project_name: projectName,
        client,
        period: `${periodStart} ~ ${periodEnd}`,
        description: '',
        technologies: [],
      };
      await kiraApi.addTrackRecord(trackRecord, companyId, sessionId);

      // 3. 인력 추가
      const personnel: PersonnelInput = {
        name: personnelName,
        role,
        experience_years: parseInt(experienceYears, 10),
        certifications: [],
        description: '',
      };
      await kiraApi.addPersonnel(personnel, companyId, sessionId);

      sessionStorage.setItem('kira_company_id', companyId);

      // 완료
      onComplete(companyName);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : '저장 중 오류가 발생했습니다.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleSkip = () => {
    sessionStorage.setItem('kira_onboarding_dismissed', 'true');
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="relative w-full max-w-md rounded-lg bg-white shadow-xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
          <div className="flex items-center gap-2">
            <Building2 className="text-kira-600" size={20} />
            <h2 className="text-lg font-bold text-slate-800">회사 정보 입력</h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            <X size={18} />
          </button>
        </div>

        {/* Progress */}
        <div className="flex items-center justify-center gap-2 border-b border-slate-100 px-6 py-3">
          <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step >= 1 ? 'bg-kira-500 text-white' : 'bg-slate-200 text-slate-400'}`}>
            {step > 1 ? <Check size={14} /> : '1'}
          </div>
          <div className={`h-0.5 w-8 ${step >= 2 ? 'bg-kira-500' : 'bg-slate-200'}`} />
          <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step >= 2 ? 'bg-kira-500 text-white' : 'bg-slate-200 text-slate-400'}`}>
            {step > 2 ? <Check size={14} /> : '2'}
          </div>
          <div className={`h-0.5 w-8 ${step >= 3 ? 'bg-kira-500' : 'bg-slate-200'}`} />
          <div className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${step >= 3 ? 'bg-kira-500 text-white' : 'bg-slate-200 text-slate-400'}`}>
            {step > 3 ? <Check size={14} /> : '3'}
          </div>
        </div>

        {/* Content */}
        <div className="px-6 py-5">
          {error && (
            <div className="mb-4 rounded-md bg-red-50 border border-red-200 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Briefcase size={16} className="text-kira-600" />
                회사명 및 대표 실적
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  회사명 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={companyName}
                  onChange={(e) => setCompanyName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  placeholder="예: (주)키라솔루션"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  프로젝트명 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={projectName}
                  onChange={(e) => setProjectName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  placeholder="예: 교육청 통합 플랫폼 구축"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  발주처 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={client}
                  onChange={(e) => setClient(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  placeholder="예: 서울특별시교육청"
                />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    시작일 (선택)
                  </label>
                  <input
                    type="month"
                    value={periodStart}
                    onChange={(e) => setPeriodStart(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1">
                    종료일 (선택)
                  </label>
                  <input
                    type="month"
                    value={periodEnd}
                    onChange={(e) => setPeriodEnd(e.target.value)}
                    className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  />
                </div>
              </div>
              <p className="text-xs text-slate-500">
                💡 최소 1개 실적만 입력하세요. 나머지는 나중에 추가할 수 있습니다.
              </p>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-slate-700">
                <Users size={16} className="text-kira-600" />
                핵심 인력 1명
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  이름 <span className="text-red-500">*</span>
                </label>
                <input
                  type="text"
                  value={personnelName}
                  onChange={(e) => setPersonnelName(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  placeholder="예: 홍길동"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  역할 <span className="text-red-500">*</span>
                </label>
                <select
                  value={role}
                  onChange={(e) => setRole(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                >
                  <option value="">선택하세요</option>
                  <option value="PM">PM (프로젝트 관리자)</option>
                  <option value="PL">PL (프로젝트 리더)</option>
                  <option value="개발자">개발자</option>
                  <option value="시스템 엔지니어">시스템 엔지니어</option>
                  <option value="데이터베이스 관리자">데이터베이스 관리자</option>
                  <option value="UI/UX 디자이너">UI/UX 디자이너</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">
                  경력 (년) <span className="text-red-500">*</span>
                </label>
                <input
                  type="number"
                  min="0"
                  value={experienceYears}
                  onChange={(e) => setExperienceYears(e.target.value)}
                  className="w-full rounded-md border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:outline-none"
                  placeholder="예: 10"
                />
              </div>
              <p className="text-xs text-slate-500">
                💡 핵심 인력 1명만 입력하세요. 나머지는 나중에 추가할 수 있습니다.
              </p>
            </div>
          )}

          {step === 3 && (
            <div className="space-y-4">
              <div className="text-center py-6">
                <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
                  <Check className="text-green-600" size={32} />
                </div>
                <h3 className="text-lg font-bold text-slate-800 mb-2">입력 완료!</h3>
                <p className="text-sm text-slate-600 mb-4">
                  회사명, 실적 1개, 인력 1명이 입력되었습니다.
                  <br />
                  이제 회사 맞춤형 제안서를 생성할 수 있습니다.
                </p>
                <div className="rounded-lg bg-kira-50 border border-kira-200 px-4 py-3 text-left">
                  <p className="text-xs font-semibold text-kira-700 mb-1">✅ 입력된 정보</p>
                  <ul className="text-xs text-slate-700 space-y-1">
                    <li>• 회사명: {companyName}</li>
                    <li>• 실적: {projectName}</li>
                    <li>• 인력: {personnelName} ({role})</li>
                  </ul>
                </div>
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-200 px-6 py-4">
          <button
            type="button"
            onClick={handleSkip}
            className="text-sm text-slate-500 hover:text-slate-700"
            disabled={isSubmitting}
          >
            건너뛰기
          </button>
          <div className="flex gap-2">
            {step > 1 && step < 3 && (
              <button
                type="button"
                onClick={() => setStep((prev) => (prev - 1) as Step)}
                className="rounded-md border border-slate-300 bg-white px-4 py-2 text-sm font-medium text-slate-700 hover:bg-slate-50"
                disabled={isSubmitting}
              >
                이전
              </button>
            )}
            {step === 1 && (
              <button
                type="button"
                onClick={handleStep1Next}
                className="rounded-md bg-kira-500 px-4 py-2 text-sm font-medium text-white hover:bg-kira-600"
              >
                다음
              </button>
            )}
            {step === 2 && (
              <button
                type="button"
                onClick={handleStep2Next}
                className="rounded-md bg-kira-500 px-4 py-2 text-sm font-medium text-white hover:bg-kira-600"
              >
                다음
              </button>
            )}
            {step === 3 && (
              <button
                type="button"
                onClick={handleComplete}
                className="rounded-md bg-kira-500 px-6 py-2 text-sm font-medium text-white hover:bg-kira-600 disabled:bg-slate-300"
                disabled={isSubmitting}
              >
                {isSubmitting ? '저장 중...' : '완료'}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default CompanyOnboardingModal;
