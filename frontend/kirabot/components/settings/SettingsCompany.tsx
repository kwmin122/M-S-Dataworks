import React, { useEffect, useState, useCallback, useRef } from 'react';
import { Upload, Trash2, RefreshCw, Sparkles, FileText, CheckCircle, AlertTriangle, Info, Briefcase, Users, Plus, ChevronDown, ChevronUp } from 'lucide-react';
import ChipInput from '../shared/ChipInput';
import type { CompanyProfile, TrackRecordListItem, PersonnelListItem } from '../../types';
import {
  getCompanyProfile,
  uploadCompanyProfileDocs,
  updateCompanyProfile,
  deleteCompanyDocument,
  reanalyzeCompanyProfile,
  listTrackRecords,
  listPersonnel,
  addTrackRecord,
  addPersonnel,
  deleteCompanyDbItem,
  getCompanyDbStats,
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
  const [uploadPhase, setUploadPhase] = useState<'idle' | 'saving' | 'analyzing'>('idle');
  const [reanalyzing, setReanalyzing] = useState(false);
  const [saveMsg, setSaveMsg] = useState('');
  const [uploadMsg, setUploadMsg] = useState<{ type: 'success' | 'warning' | 'info'; text: string } | null>(null);
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

  // ── Company DB (실적/인력) state ──
  const [trackRecords, setTrackRecords] = useState<TrackRecordListItem[]>([]);
  const [personnelList, setPersonnelList] = useState<PersonnelListItem[]>([]);
  const [dbStats, setDbStats] = useState<{ track_record_count: number; personnel_count: number; total_knowledge_units: number } | null>(null);
  const [showAddTrackRecord, setShowAddTrackRecord] = useState(false);
  const [showAddPersonnel, setShowAddPersonnel] = useState(false);
  const [addingTr, setAddingTr] = useState(false);
  const [addingPs, setAddingPs] = useState(false);
  const [dbSection, setDbSection] = useState(true);

  // Track record form
  const [trProjectName, setTrProjectName] = useState('');
  const [trClient, setTrClient] = useState('');
  const [trPeriod, setTrPeriod] = useState('');
  const [trAmount, setTrAmount] = useState('');
  const [trDescription, setTrDescription] = useState('');
  const [trTechnologies, setTrTechnologies] = useState<string[]>([]);

  // Personnel form
  const [psName, setPsName] = useState('');
  const [psRole, setPsRole] = useState('');
  const [psExperience, setPsExperience] = useState('');
  const [psCertifications, setPsCertifications] = useState<string[]>([]);

  const loadCompanyDb = useCallback(async () => {
    try {
      const cid = sessionStorage.getItem('kira_company_id') || '_default';
      const [trRes, psRes, statsRes] = await Promise.all([
        listTrackRecords(cid),
        listPersonnel(cid),
        getCompanyDbStats(cid),
      ]);
      setTrackRecords(trRes.records);
      setPersonnelList(psRes.personnel);
      setDbStats(statsRes);
    } catch { /* ignore */ }
  }, []);

  const handleAddTrackRecord = async () => {
    if (!trProjectName.trim() || !trClient.trim()) return;
    setAddingTr(true);
    try {
      const cid = sessionStorage.getItem('kira_company_id') || '_default';
      const sid = sessionStorage.getItem('kira_session_id') || '';
      await addTrackRecord({
        project_name: trProjectName,
        client: trClient,
        period: trPeriod,
        contract_amount: trAmount,
        description: trDescription,
        technologies: trTechnologies,
      }, cid, sid);
      setTrProjectName(''); setTrClient(''); setTrPeriod('');
      setTrAmount(''); setTrDescription(''); setTrTechnologies([]);
      setShowAddTrackRecord(false);
      await loadCompanyDb();
    } catch { /* ignore */ }
    setAddingTr(false);
  };

  const handleAddPersonnel = async () => {
    if (!psName.trim() || !psRole.trim()) return;
    setAddingPs(true);
    try {
      const cid = sessionStorage.getItem('kira_company_id') || '_default';
      const sid = sessionStorage.getItem('kira_session_id') || '';
      await addPersonnel({
        name: psName,
        role: psRole,
        experience_years: parseInt(psExperience) || 0,
        certifications: psCertifications,
        description: '',
      }, cid, sid);
      setPsName(''); setPsRole(''); setPsExperience(''); setPsCertifications([]);
      setShowAddPersonnel(false);
      await loadCompanyDb();
    } catch { /* ignore */ }
    setAddingPs(false);
  };

  const handleDeleteDbItem = async (docId: string) => {
    try {
      const cid = sessionStorage.getItem('kira_company_id') || '_default';
      const sid = sessionStorage.getItem('kira_session_id') || '';
      await deleteCompanyDbItem(docId, cid, sid);
      setTrackRecords(prev => prev.filter(r => r.doc_id !== docId));
      setPersonnelList(prev => prev.filter(p => p.doc_id !== docId));
    } catch { /* ignore */ }
  };

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
    let cancelled = false;
    Promise.all([
      getCompanyProfile(),
      loadCompanyDb(),
    ]).then(([p]) => {
      if (cancelled) return;
      setProfile(p);
      if (p) fillForm(p);
    })
      .catch(() => {})
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [fillForm, loadCompanyDb]);

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
    setUploadPhase('saving');
    setUploadMsg(null);
    try {
      const files = Array.from(fileList);
      setUploadPhase('analyzing');
      const result = await uploadCompanyProfileDocs(files);
      const updated = result.profile;
      const ur = result.uploadResult;
      setProfile(updated);
      fillForm(updated);

      // Show feedback based on extraction status
      if (ur?.extractionStatus === 'success' && ur.filledFields?.length) {
        setUploadMsg({
          type: 'success',
          text: `${ur.savedCount}개 파일 저장 완료. AI가 프로필을 자동으로 채웠습니다: ${ur.filledFields.join(', ')}`,
        });
      } else if (ur?.extractionStatus === 'partial') {
        setUploadMsg({
          type: 'info',
          text: `${ur.savedCount}개 파일 저장 완료. 문서에서 회사 정보를 찾지 못했습니다. 회사소개서나 사업자등록증을 올려보세요.`,
        });
      } else if (ur?.extractionStatus === 'failed') {
        setUploadMsg({
          type: 'warning',
          text: `${ur.savedCount}개 파일 저장 완료. AI 분석 중 오류가 발생했습니다. "재분석" 버튼으로 다시 시도해보세요.`,
        });
      } else if (ur?.extractionStatus === 'no_text') {
        setUploadMsg({
          type: 'warning',
          text: `${ur.savedCount}개 파일 저장 완료. 문서에서 텍스트를 추출하지 못했습니다.`,
        });
      } else {
        setUploadMsg({
          type: 'success',
          text: `${files.length}개 파일이 저장되었습니다.`,
        });
      }
      setTimeout(() => setUploadMsg(null), 10000);
    } catch (e) {
      setUploadMsg({
        type: 'warning',
        text: e instanceof Error ? e.message : '업로드 실패',
      });
    } finally {
      setUploading(false);
      setUploadPhase('idle');
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
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-slate-900 mb-1">회사 정보 관리</h2>
        <p className="text-sm text-slate-500">
          회사 정보를 등록하면 입찰 분석, 발주예측, 알림 설정에서 자동으로 활용됩니다.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* ─── 좌측: 문서 등록 (Primary CTA) ─── */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-200 p-5 space-y-4">
            <div className="flex items-center gap-2">
              <FileText size={18} className="text-kira-600" />
              <h3 className="text-base font-semibold text-slate-800">회사 문서 등록</h3>
            </div>
            <p className="text-sm text-slate-500">
              사업자등록증, 실적증명, 자격증 등을 업로드하면 AI가 자동으로 프로필을 채웁니다.
            </p>

            {/* 업로드 영역 */}
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); e.stopPropagation(); }}
              onDrop={(e) => { e.preventDefault(); e.stopPropagation(); if (e.dataTransfer.files.length) handleUpload(e.dataTransfer.files); }}
              className="flex flex-col items-center justify-center rounded-lg border-2 border-dashed border-slate-300 hover:border-kira-400 py-8 cursor-pointer transition-colors"
            >
              {uploading ? (
                <div className="flex flex-col items-center gap-2">
                  <div className="flex gap-1">
                    <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
                    <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
                    <span className="typing-dot h-2 w-2 rounded-full bg-kira-500" />
                  </div>
                  <p className="text-sm text-kira-600 font-medium">
                    {uploadPhase === 'saving' ? '파일 업로드 중...' : 'AI가 문서를 분석하고 있습니다...'}
                  </p>
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

            {/* 업로드 결과 메시지 */}
            {uploadMsg && (
              <div className={`flex items-start gap-2 rounded-lg border p-3 text-sm ${
                uploadMsg.type === 'success'
                  ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                  : uploadMsg.type === 'warning'
                  ? 'border-amber-200 bg-amber-50 text-amber-700'
                  : 'border-blue-200 bg-blue-50 text-blue-700'
              }`}>
                {uploadMsg.type === 'success' ? (
                  <CheckCircle size={16} className="text-emerald-500 mt-0.5 shrink-0" />
                ) : uploadMsg.type === 'warning' ? (
                  <AlertTriangle size={16} className="text-amber-500 mt-0.5 shrink-0" />
                ) : (
                  <Info size={16} className="text-blue-500 mt-0.5 shrink-0" />
                )}
                <span>{uploadMsg.text}</span>
              </div>
            )}

            {/* 업로드된 문서 목록 */}
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
          </div>

          {/* 등록 시 제공 기능 안내 */}
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-5">
            <h4 className="text-sm font-semibold text-slate-700 mb-3">문서 등록 시 제공 기능</h4>
            <ul className="space-y-2 text-sm text-slate-600">
              <li className="flex items-start gap-2"><span className="text-kira-600 mt-0.5">•</span>입찰 자격요건 vs 회사 역량 비교 분석</li>
              <li className="flex items-start gap-2"><span className="text-kira-600 mt-0.5">•</span>강점·약점 매칭 및 적합도 점수</li>
              <li className="flex items-start gap-2"><span className="text-kira-600 mt-0.5">•</span>발주 예측 맞춤 매칭</li>
              <li className="flex items-start gap-2"><span className="text-kira-600 mt-0.5">•</span>프로필 자동 채우기 (AI 추출)</li>
            </ul>
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

          {/* 미등록 안내 (문서 없을 때) */}
          {!profile && (
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-6 text-center">
              <Upload size={32} className="text-slate-300 mx-auto mb-3" />
              <p className="text-sm text-slate-500">회사 문서를 업로드하면 AI가 자동으로 정보를 추출합니다.</p>
            </div>
          )}
        </div>

        {/* ─── 우측: 프로필 폼 ─── */}
        <div className="rounded-xl border border-slate-200 p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-base font-semibold text-slate-800">회사 프로필</h3>
            {profile?.aiExtraction && (
              <span className="text-xs text-kira-600 bg-kira-50 px-2 py-0.5 rounded-full">
                문서 등록 시 자동 채움
              </span>
            )}
          </div>

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
      </div>

      {/* ─── 회사 역량 DB (실적/인력) ─── */}
      <div className="rounded-xl border border-slate-200 p-5 space-y-4">
        <button
          type="button"
          onClick={() => setDbSection(!dbSection)}
          className="flex items-center justify-between w-full"
        >
          <div className="flex items-center gap-2">
            <Briefcase size={18} className="text-kira-600" />
            <h3 className="text-base font-semibold text-slate-800">회사 역량 DB (실적/인력)</h3>
            {dbStats && (
              <span className="text-xs text-slate-500">
                실적 {dbStats.track_record_count}건 | 인력 {dbStats.personnel_count}명
              </span>
            )}
          </div>
          {dbSection ? <ChevronUp size={18} className="text-slate-400" /> : <ChevronDown size={18} className="text-slate-400" />}
        </button>

        {dbSection && (
          <>
            <p className="text-sm text-slate-500">
              등록된 실적과 인력은 제안서, PPT, WBS 생성 시 자동으로 활용됩니다.
            </p>

            {/* ── 수행실적 ── */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Briefcase size={16} className="text-slate-600" />
                  <h4 className="text-sm font-semibold text-slate-700">수행실적</h4>
                  <span className="text-xs text-slate-400">{trackRecords.length}건</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddTrackRecord(!showAddTrackRecord)}
                  className="flex items-center gap-1 rounded-lg border border-kira-300 px-2.5 py-1 text-xs font-medium text-kira-600 hover:bg-kira-50"
                >
                  <Plus size={14} /> 실적 추가
                </button>
              </div>

              {/* Add Track Record Form */}
              {showAddTrackRecord && (
                <div className="rounded-lg border border-kira-200 bg-kira-50/30 p-4 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">프로젝트명 <span className="text-red-500">*</span></label>
                      <input value={trProjectName} onChange={e => setTrProjectName(e.target.value)}
                        placeholder="예: 교육청 통합 플랫폼 구축"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">발주처 <span className="text-red-500">*</span></label>
                      <input value={trClient} onChange={e => setTrClient(e.target.value)}
                        placeholder="예: 서울특별시교육청"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">수행기간</label>
                      <input value={trPeriod} onChange={e => setTrPeriod(e.target.value)}
                        placeholder="예: 2024.03 ~ 2024.12"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">계약금액</label>
                      <input value={trAmount} onChange={e => setTrAmount(e.target.value)}
                        placeholder="예: 5억"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-600 mb-1">설명</label>
                    <textarea value={trDescription} onChange={e => setTrDescription(e.target.value)}
                      rows={2} placeholder="프로젝트 개요, 주요 성과 등"
                      className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none resize-none" />
                  </div>
                  <ChipInput label="기술 스택" chips={trTechnologies} onChange={setTrTechnologies} placeholder="기술명 입력 후 Enter" />
                  <div className="flex gap-2">
                    <button type="button" onClick={handleAddTrackRecord} disabled={addingTr || !trProjectName.trim() || !trClient.trim()}
                      className="rounded-md bg-kira-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50">
                      {addingTr ? '추가 중...' : '추가'}
                    </button>
                    <button type="button" onClick={() => setShowAddTrackRecord(false)}
                      className="rounded-md border border-slate-300 px-4 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                      취소
                    </button>
                  </div>
                </div>
              )}

              {/* Track Records List */}
              {trackRecords.length > 0 ? (
                <div className="space-y-2">
                  {trackRecords.map((tr) => (
                    <div key={tr.doc_id} className="flex items-start justify-between rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-800 truncate">{tr.project_name}</p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          {tr.client}{tr.period ? ` | ${tr.period}` : ''}{tr.amount > 0 ? ` | ${(tr.amount / 1e8).toFixed(1)}억원` : ''}
                        </p>
                        {tr.technologies.length > 0 && (
                          <div className="flex flex-wrap gap-1 mt-1.5">
                            {tr.technologies.map((t, i) => (
                              <span key={i} className="rounded bg-slate-200 px-1.5 py-0.5 text-[10px] text-slate-600">{t}</span>
                            ))}
                          </div>
                        )}
                      </div>
                      <button type="button" onClick={() => handleDeleteDbItem(tr.doc_id)}
                        className="text-slate-400 hover:text-red-500 shrink-0 ml-2 mt-0.5">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 text-center py-3">등록된 실적이 없습니다.</p>
              )}
            </div>

            {/* ── 핵심 인력 ── */}
            <div className="space-y-3 pt-2 border-t border-slate-100">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Users size={16} className="text-slate-600" />
                  <h4 className="text-sm font-semibold text-slate-700">핵심 인력</h4>
                  <span className="text-xs text-slate-400">{personnelList.length}명</span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowAddPersonnel(!showAddPersonnel)}
                  className="flex items-center gap-1 rounded-lg border border-kira-300 px-2.5 py-1 text-xs font-medium text-kira-600 hover:bg-kira-50"
                >
                  <Plus size={14} /> 인력 추가
                </button>
              </div>

              {/* Add Personnel Form */}
              {showAddPersonnel && (
                <div className="rounded-lg border border-kira-200 bg-kira-50/30 p-4 space-y-3">
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">이름 <span className="text-red-500">*</span></label>
                      <input value={psName} onChange={e => setPsName(e.target.value)}
                        placeholder="예: 홍길동"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">역할 <span className="text-red-500">*</span></label>
                      <select value={psRole} onChange={e => setPsRole(e.target.value)}
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none">
                        <option value="">선택</option>
                        <option value="PM">PM</option>
                        <option value="PL">PL</option>
                        <option value="개발자">개발자</option>
                        <option value="시스템 엔지니어">시스템 엔지니어</option>
                        <option value="데이터베이스 관리자">DBA</option>
                        <option value="UI/UX 디자이너">UI/UX 디자이너</option>
                        <option value="QA">QA</option>
                        <option value="컨설턴트">컨설턴트</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-600 mb-1">경력 (년)</label>
                      <input type="number" min="0" value={psExperience} onChange={e => setPsExperience(e.target.value)}
                        placeholder="예: 10"
                        className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-kira-500 outline-none" />
                    </div>
                  </div>
                  <ChipInput label="자격증" chips={psCertifications} onChange={setPsCertifications} placeholder="자격증 입력 후 Enter" />
                  <div className="flex gap-2">
                    <button type="button" onClick={handleAddPersonnel} disabled={addingPs || !psName.trim() || !psRole.trim()}
                      className="rounded-md bg-kira-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-kira-700 disabled:opacity-50">
                      {addingPs ? '추가 중...' : '추가'}
                    </button>
                    <button type="button" onClick={() => setShowAddPersonnel(false)}
                      className="rounded-md border border-slate-300 px-4 py-1.5 text-xs text-slate-600 hover:bg-slate-50">
                      취소
                    </button>
                  </div>
                </div>
              )}

              {/* Personnel List */}
              {personnelList.length > 0 ? (
                <div className="space-y-2">
                  {personnelList.map((ps) => (
                    <div key={ps.doc_id} className="flex items-start justify-between rounded-lg border border-slate-100 bg-slate-50/50 p-3">
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-slate-800">{ps.name} <span className="text-xs text-slate-500 font-normal">({ps.role})</span></p>
                        <p className="text-xs text-slate-500 mt-0.5">
                          경력 {ps.experience_years}년
                          {ps.certifications.length > 0 && ` | ${ps.certifications.join(', ')}`}
                        </p>
                      </div>
                      <button type="button" onClick={() => handleDeleteDbItem(ps.doc_id)}
                        className="text-slate-400 hover:text-red-500 shrink-0 ml-2 mt-0.5">
                        <Trash2 size={14} />
                      </button>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-xs text-slate-400 text-center py-3">등록된 인력이 없습니다.</p>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
};

export default SettingsCompany;
