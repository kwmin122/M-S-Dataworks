import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Upload, Trash2, RefreshCw, Sparkles, FileText } from 'lucide-react';
import ChipInput from '../shared/ChipInput';
import type { CompanyProfile } from '../../types';
import {
  getCompanyProfile,
  uploadCompanyProfileDocs,
  updateCompanyProfile,
  deleteCompanyDocument,
  reanalyzeCompanyProfile,
} from '../../services/kiraApiService';

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes}B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
}

const SettingsCompany: React.FC = () => {
  const [profile, setProfile] = useState<CompanyProfile | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [reanalyzing, setReanalyzing] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Form state
  const [companyName, setCompanyName] = useState('');
  const [businessType, setBusinessType] = useState('');
  const [businessNumber, setBusinessNumber] = useState('');
  const [certifications, setCertifications] = useState<string[]>([]);
  const [regions, setRegions] = useState<string[]>([]);
  const [employeeCount, setEmployeeCount] = useState('');
  const [annualRevenue, setAnnualRevenue] = useState('');
  const [keyExperience, setKeyExperience] = useState<string[]>([]);
  const [specializations, setSpecializations] = useState<string[]>([]);

  const fillForm = useCallback((p: CompanyProfile) => {
    setCompanyName(p.companyName || '');
    setBusinessType(p.businessType || '');
    setBusinessNumber(p.businessNumber || '');
    setCertifications(p.certifications || []);
    setRegions(p.regions || []);
    setEmployeeCount(p.employeeCount ? String(p.employeeCount) : '');
    setAnnualRevenue(p.annualRevenue || '');
    setKeyExperience(p.keyExperience || []);
    setSpecializations(p.specializations || []);
  }, []);

  useEffect(() => {
    getCompanyProfile()
      .then((p) => {
        setProfile(p);
        if (p) fillForm(p);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [fillForm]);

  const handleSave = async () => {
    setSaving(true);
    setSaveMsg('');
    try {
      const updated = await updateCompanyProfile({
        companyName, businessType, businessNumber,
        certifications, regions, specializations, keyExperience,
        employeeCount: employeeCount ? parseInt(employeeCount) : null,
        annualRevenue,
      });
      setProfile(updated);
      setSaveMsg('저장되었습니다.');
      setTimeout(() => setSaveMsg(''), 3000);
    } catch (e) {
      setSaveMsg(e instanceof Error ? e.message : '저장 실패');
    } finally {
      setSaving(false);
    }
  };

  const handleUpload = async (fileList: FileList) => {
    setUploading(true);
    try {
      const files = Array.from(fileList);
      const updated = await uploadCompanyProfileDocs(files);
      setProfile(updated);
      fillForm(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : '업로드 실패');
    } finally {
      setUploading(false);
    }
  };

  const handleDeleteDoc = async (docId: string) => {
    try {
      const updated = await deleteCompanyDocument(docId);
      setProfile(updated);
    } catch { /* ignore */ }
  };

  const handleReanalyze = async () => {
    setReanalyzing(true);
    try {
      const updated = await reanalyzeCompanyProfile();
      setProfile(updated);
    } catch (e) {
      alert(e instanceof Error ? e.message : '재분석 실패');
    } finally {
      setReanalyzing(false);
    }
  };

  const handleApplyAi = () => {
    if (!profile?.aiExtraction?.raw) return;
    const raw = profile.aiExtraction.raw as Record<string, unknown>;
    if (raw.companyName) setCompanyName(String(raw.companyName));
    if (raw.businessType) setBusinessType(String(raw.businessType));
    if (raw.businessNumber) setBusinessNumber(String(raw.businessNumber));
    if (Array.isArray(raw.certifications)) setCertifications(raw.certifications as string[]);
    if (Array.isArray(raw.regions)) setRegions(raw.regions as string[]);
    if (raw.employeeCount) setEmployeeCount(String(raw.employeeCount));
    if (raw.annualRevenue) setAnnualRevenue(String(raw.annualRevenue));
    if (Array.isArray(raw.keyExperience)) setKeyExperience(raw.keyExperience as string[]);
    if (Array.isArray(raw.specializations)) setSpecializations(raw.specializations as string[]);
  };

  if (loading) {
    return (
      <div className="flex justify-center py-16">
        <div className="flex gap-1">
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
          <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">회사 정보 관리</h2>
        <p className="text-sm text-slate-500 mb-6">
          회사 정보를 등록하면 입찰 분석, 발주예측, 알림 설정에서 자동으로 활용됩니다.
        </p>
      </div>

      {/* 프로필 폼 */}
      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <h3 className="text-base font-semibold text-slate-800">회사 프로필</h3>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">회사명</label>
            <input value={companyName} onChange={e => setCompanyName(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">업종</label>
            <input value={businessType} onChange={e => setBusinessType(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">사업자번호</label>
            <input value={businessNumber} onChange={e => setBusinessNumber(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">연매출</label>
            <input value={annualRevenue} onChange={e => setAnnualRevenue(e.target.value)} placeholder="예: 30억" className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1">직원 수</label>
            <input type="number" value={employeeCount} onChange={e => setEmployeeCount(e.target.value)} className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-kira-500 focus:ring-2 focus:ring-kira-200 outline-none" />
          </div>
        </div>

        {/* ChipInput fields -- ChipInput uses "chips" prop and renders its own label */}
        <ChipInput label="자격증/인증" chips={certifications} onChange={setCertifications} placeholder="자격증 입력 후 Enter" />
        <ChipInput label="활동 지역" chips={regions} onChange={setRegions} placeholder="지역 입력 후 Enter" />
        <ChipInput label="전문 분야" chips={specializations} onChange={setSpecializations} placeholder="전문 분야 입력 후 Enter" />
        <ChipInput label="주요 경험" chips={keyExperience} onChange={setKeyExperience} placeholder="주요 경험 입력 후 Enter" />

        <div className="flex items-center gap-3">
          <button type="button" onClick={handleSave} disabled={saving}
            className="rounded-lg bg-kira-600 px-5 py-2 text-sm font-medium text-white hover:bg-kira-700 disabled:opacity-50 transition-colors">
            {saving ? '저장 중...' : '프로필 저장'}
          </button>
          {saveMsg && <span className="text-sm text-emerald-600">{saveMsg}</span>}
        </div>
      </div>

      {/* 문서 목록 + 업로드 */}
      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <h3 className="text-base font-semibold text-slate-800">등록 문서</h3>

        {profile?.documents && profile.documents.length > 0 && (
          <div className="space-y-2">
            {profile.documents.map((doc) => (
              <div key={doc.id} className="flex items-center justify-between rounded-lg bg-slate-50 px-3 py-2">
                <div className="flex items-center gap-2 min-w-0">
                  <FileText size={16} className="text-slate-400 shrink-0" />
                  <span className="text-sm text-slate-700 truncate">{doc.name}</span>
                  <span className="text-xs text-slate-400 shrink-0">{formatBytes(doc.size)}</span>
                </div>
                <button type="button" onClick={() => handleDeleteDoc(doc.id)}
                  className="text-slate-400 hover:text-red-500 transition-colors shrink-0">
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        )}

        {/* 업로드 영역 */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
          onDrop={(e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files); }}
          className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 hover:border-kira-400 py-8 cursor-pointer transition-colors"
        >
          {uploading ? (
            <div className="flex gap-1">
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
              <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
            </div>
          ) : (
            <>
              <Upload size={24} className="text-slate-400 mb-2" />
              <p className="text-sm text-slate-600 font-medium">파일을 드래그하거나 클릭하여 업로드</p>
              <p className="text-xs text-slate-400 mt-1">PDF, DOCX, HWP, TXT, MD, PPT (최대 10MB)</p>
            </>
          )}
        </div>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.doc,.docx,.txt,.md,.hwp,.hwpx,.xlsx,.xls,.csv,.pptx,.ppt"
          onChange={(e) => { if (e.target.files?.length) handleUpload(e.target.files); e.target.value = ''; }}
          className="hidden"
        />
      </div>

      {/* AI 추출 요약 */}
      {profile?.aiExtraction && (
        <div className="rounded-xl border border-kira-200 bg-kira-50/50 p-5 space-y-3">
          <div className="flex items-center gap-2">
            <Sparkles size={16} className="text-kira-600" />
            <h3 className="text-base font-semibold text-slate-800">AI 추출 역량 요약</h3>
          </div>
          <p className="text-sm text-slate-700">{profile.aiExtraction.summary || '요약 정보가 없습니다.'}</p>
          <div className="flex gap-2">
            <button type="button" onClick={handleReanalyze} disabled={reanalyzing}
              className="flex items-center gap-1.5 rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-50 disabled:opacity-50">
              <RefreshCw size={14} className={reanalyzing ? 'animate-spin' : ''} />
              재분석
            </button>
            <button type="button" onClick={handleApplyAi}
              className="flex items-center gap-1.5 rounded-lg bg-kira-600 px-3 py-1.5 text-sm text-white hover:bg-kira-700">
              <Sparkles size={14} />
              프로필에 반영
            </button>
          </div>
        </div>
      )}

      {/* 미등록 안내 */}
      {!profile && (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
          <Upload size={32} className="text-slate-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500">회사 문서를 업로드하면 AI가 자동으로 정보를 추출합니다.</p>
        </div>
      )}
    </div>
  );
};

export default SettingsCompany;
