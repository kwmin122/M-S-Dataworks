import React, { useEffect, useMemo, useState } from 'react';
import {
  Bot,
  CheckCircle2,
  FileText,
  Loader2,
  Send,
  UploadCloud,
  User as UserIcon,
} from 'lucide-react';
import {
  analyzeDocument,
  chatWithReferences,
  createSession,
  getSessionStats,
  uploadCompanyDocuments,
} from '../services/kiraApiService';
import { AnalyzeResponse, ChatReference, User } from '../types';
import Button from './Button';
import SearchPanel from './workspace/SearchPanel';
import MultiAnalysisPanel from './workspace/MultiAnalysisPanel';
import ProposalPanel from './workspace/ProposalPanel';

interface DashboardProps {
  user: User | null;
}

interface ChatLine {
  id: string;
  role: 'user' | 'model';
  text: string;
  references?: ChatReference[];
}

type OpinionMode = 'conservative' | 'balanced' | 'aggressive';
type PreviewMode = 'company' | 'target';
type WorkspaceMode = 'rfx' | 'search' | 'multi' | 'proposal';

const WORKSPACE_TABS: { mode: WorkspaceMode; label: string }[] = [
  { mode: 'rfx', label: 'RFx 분석' },
  { mode: 'search', label: '공고 검색' },
  { mode: 'multi', label: '다중 분석' },
  { mode: 'proposal', label: '제안서' },
];

const SESSION_KEY = 'kira_web_session_id';

const modeLabel: Record<OpinionMode, string> = {
  conservative: '보수적',
  balanced: '균형',
  aggressive: '공격적',
};

const defaultQuestions = [
  '우리 회사 이름과 핵심 역량을 문서 근거로 알려줘',
  '핵심 요건 3개만 먼저 요약해줘',
  '미충족 요건 준비 순서를 알려줘',
  '마감 전 체크리스트를 만들어줘',
];

const Dashboard: React.FC<DashboardProps> = ({ user }) => {
  const [sessionId, setSessionId] = useState('');
  const [companyChunks, setCompanyChunks] = useState(0);
  const [companyFiles, setCompanyFiles] = useState<File[]>([]);
  const [targetFile, setTargetFile] = useState<File | null>(null);
  const [targetFileUrl, setTargetFileUrl] = useState('');
  const [companyPreviewFile, setCompanyPreviewFile] = useState<File | null>(null);
  const [companyPreviewUrl, setCompanyPreviewUrl] = useState('');
  const [previewMode, setPreviewMode] = useState<PreviewMode>('target');
  const [selectedPdfPage, setSelectedPdfPage] = useState(1);

  const [isUploading, setIsUploading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [isChatting, setIsChatting] = useState(false);

  const [messages, setMessages] = useState<ChatLine[]>([
    {
      id: 'welcome',
      role: 'model',
      text: '안녕하세요. 회사 문서를 등록하고 분석 문서를 올리면, 근거 페이지와 함께 답변해드릴게요.',
    },
  ]);
  const [chatInput, setChatInput] = useState('');
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [opinionMode, setOpinionMode] = useState<OpinionMode>('balanced');
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(defaultQuestions);
  const [workspaceMode, setWorkspaceMode] = useState<WorkspaceMode>('rfx');

  useEffect(() => {
    const boot = async (): Promise<void> => {
      try {
        let sid = localStorage.getItem(SESSION_KEY) || '';
        if (!sid) {
          sid = await createSession();
          localStorage.setItem(SESSION_KEY, sid);
        }
        setSessionId(sid);
        const stats = await getSessionStats(sid);
        setCompanyChunks(stats.company_chunks || 0);
      } catch (error) {
        const message = error instanceof Error ? error.message : '세션 초기화에 실패했습니다.';
        setMessages((prev) => [
          ...prev,
          { id: `${Date.now()}_boot_error`, role: 'model', text: `초기화 실패: ${message}` },
        ]);
      }
    };

    void boot();
  }, []);

  useEffect(() => {
    if (!targetFile) {
      setTargetFileUrl('');
      setSelectedPdfPage(1);
      return;
    }

    const objectUrl = URL.createObjectURL(targetFile);
    setTargetFileUrl(objectUrl);
    setSelectedPdfPage(1);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [targetFile]);

  useEffect(() => {
    if (!companyPreviewFile) {
      setCompanyPreviewUrl('');
      return;
    }
    const objectUrl = URL.createObjectURL(companyPreviewFile);
    setCompanyPreviewUrl(objectUrl);
    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [companyPreviewFile]);

  const selectedOpinion = useMemo(() => {
    if (!result?.matching?.assistant_opinions) {
      return null;
    }

    const opinions = result.matching.assistant_opinions;
    if (opinions[opinionMode]) {
      return opinions[opinionMode];
    }

    const prefixed = Object.entries(opinions).find(([key]) => key.startsWith(opinionMode));
    if (prefixed) {
      return prefixed[1];
    }

    return opinions.balanced || Object.values(opinions)[0] || null;
  }, [opinionMode, result]);

  const pushModelMessage = (text: string, references: ChatReference[] = []): void => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}_model`,
        role: 'model',
        text,
        references,
      },
    ]);
  };

  const pushUserMessage = (text: string): void => {
    setMessages((prev) => [
      ...prev,
      {
        id: `${Date.now()}_user`,
        role: 'user',
        text,
      },
    ]);
  };

  const uploadCompany = async (): Promise<void> => {
    if (!sessionId) {
      pushModelMessage('세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.');
      return;
    }
    if (!companyFiles.length) {
      pushModelMessage('회사 문서를 먼저 선택해주세요.');
      return;
    }

    try {
      setIsUploading(true);
      const response = await uploadCompanyDocuments(sessionId, companyFiles);
      setCompanyChunks(response.company_chunks || 0);
      const companyPdf = companyFiles.find((file) => file.type.includes('pdf'));
      if (companyPdf) {
        setCompanyPreviewFile(companyPdf);
        if (!targetFile) {
          setPreviewMode('company');
        }
      }
      setCompanyFiles([]);
      pushModelMessage(`회사 문서 등록 완료: ${response.company_chunks}개 지식 조각이 준비되었습니다.`);
    } catch (error) {
      const message = error instanceof Error ? error.message : '회사 문서 등록 중 오류가 발생했습니다.';
      pushModelMessage(`오류: ${message}`);
    } finally {
      setIsUploading(false);
    }
  };

  const runAnalysis = async (): Promise<void> => {
    if (!sessionId) {
      pushModelMessage('세션이 아직 준비되지 않았습니다. 잠시 후 다시 시도해주세요.');
      return;
    }
    if (!targetFile) {
      pushModelMessage('분석할 문서를 먼저 선택해주세요.');
      return;
    }

    if (companyChunks <= 0) {
      pushModelMessage('회사 문서가 없습니다. 먼저 회사 문서를 등록해주세요.');
      return;
    }

    try {
      setIsAnalyzing(true);
      pushModelMessage('문서 분석을 시작합니다. 문서 길이에 따라 수십 초~수분이 걸릴 수 있습니다.');
      const response = await analyzeDocument(sessionId, targetFile);
      setResult(response);
      setOpinionMode('balanced');
      setPreviewMode('target');

      const summary = response.matching.summary || '요약 없음';
      const score = Math.round(response.matching.overall_score || 0);
      const recommendation = response.matching.recommendation;
      pushModelMessage(`분석 완료\n- 적합도: ${score}%\n- 추천: ${recommendation}\n- 요약: ${summary}`);
    } catch (error) {
      const message = error instanceof Error ? error.message : '분석 중 오류가 발생했습니다.';
      pushModelMessage(`분석 실패: ${message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const sendQuestion = async (text?: string): Promise<void> => {
    const question = (text || chatInput).trim();
    if (!question || !sessionId || isChatting) return;

    pushUserMessage(question);
    setChatInput('');
    try {
      setIsChatting(true);
      const response = await chatWithReferences(sessionId, question);
      if (response.suggested_questions?.length) {
        setSuggestedQuestions(response.suggested_questions.slice(0, 4));
      }
      pushModelMessage(response.answer, response.references || []);
      if (response.references?.length) {
        setPreviewMode('target');
        setSelectedPdfPage(response.references[0].page);
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : '채팅 처리 중 오류가 발생했습니다.';
      pushModelMessage(`질문 처리 실패: ${message}`);
    } finally {
      setIsChatting(false);
    }
  };

  const canViewCompanyPdf = Boolean(companyPreviewFile?.type.includes('pdf') && companyPreviewUrl);
  const canViewTargetPdf = Boolean(targetFile?.type.includes('pdf') && targetFileUrl);
  const targetIsNonPdf = Boolean(targetFile && !targetFile.type.includes('pdf'));
  const activePreviewMode: PreviewMode = previewMode === 'company'
    ? (canViewCompanyPdf ? 'company' : 'target')
    : (canViewTargetPdf ? 'target' : 'company');
  const activePreviewUrl = activePreviewMode === 'company' ? companyPreviewUrl : targetFileUrl;
  const activePreviewTitle = activePreviewMode === 'company'
    ? (companyPreviewFile?.name || '회사 문서')
    : (targetFile?.name || '분석 문서');

  return (
    <div className="flex h-[calc(100vh-64px)] overflow-hidden bg-slate-50">
      <div className="hidden w-[60%] flex-col border-r border-slate-200 bg-slate-100 lg:flex">
        <div className="flex h-14 items-center justify-between border-b border-slate-200 bg-white px-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-semibold text-slate-800">{activePreviewTitle || '문서를 선택해주세요'}</p>
            <p className="text-xs text-slate-500">세션: {sessionId || '생성 중...'}</p>
          </div>
          <span className="rounded-full bg-primary-50 px-2 py-1 text-xs font-semibold text-primary-700">
            회사 지식 {companyChunks}개
          </span>
        </div>
        <div className="flex items-center gap-2 border-b border-slate-200 bg-white px-4 py-2">
          <button
            type="button"
            onClick={() => setPreviewMode('company')}
            disabled={!canViewCompanyPdf}
            className={`rounded-lg border px-3 py-1 text-xs font-medium ${
              activePreviewMode === 'company'
                ? 'border-primary-600 bg-primary-50 text-primary-700'
                : 'border-slate-300 bg-white text-slate-600'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            회사 문서 보기
          </button>
          <button
            type="button"
            onClick={() => setPreviewMode('target')}
            disabled={!canViewTargetPdf}
            className={`rounded-lg border px-3 py-1 text-xs font-medium ${
              activePreviewMode === 'target'
                ? 'border-primary-600 bg-primary-50 text-primary-700'
                : 'border-slate-300 bg-white text-slate-600'
            } disabled:cursor-not-allowed disabled:opacity-50`}
          >
            분석 문서 보기
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {!activePreviewUrl ? (
            targetIsNonPdf && (previewMode === 'target' || !canViewCompanyPdf) ? (
              <div className="flex h-full min-h-[720px] items-center justify-center whitespace-pre-line rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
                PDF 외 문서는 브라우저 미리보기를 지원하지 않습니다.\n분석은 정상적으로 진행됩니다.
              </div>
            ) : (
              <div className="flex h-full items-center justify-center whitespace-pre-line rounded-2xl border border-dashed border-slate-300 bg-white text-center text-sm text-slate-500">
                왼쪽 영역은 업로드 문서 미리보기입니다.\n오른쪽에서 회사 문서와 분석 문서를 등록해 주세요.
              </div>
            )
          ) : (
            <iframe
              title={activePreviewMode === 'company' ? '회사 문서 미리보기' : '분석 문서 미리보기'}
              src={`${activePreviewUrl}#page=${selectedPdfPage}`}
              className="h-full min-h-[720px] w-full rounded-2xl border border-slate-200 bg-white"
            />
          )}
        </div>
      </div>

      <div className="flex w-full flex-col bg-white lg:w-[40%]">
        <div className="flex h-14 items-center justify-between border-b border-slate-200 px-4">
          <h3 className="flex items-center gap-2 text-sm font-bold text-slate-800">
            <Bot className="h-4 w-4 text-primary-600" /> Kira 워크스페이스
          </h3>
          <span className="text-xs text-slate-500">{user?.name || '로그인 사용자'}</span>
        </div>

        <div className="flex border-b border-slate-200 bg-white px-4">
          {WORKSPACE_TABS.map((tab) => (
            <button
              key={tab.mode}
              type="button"
              onClick={() => setWorkspaceMode(tab.mode)}
              className={`px-3 py-2 text-xs font-medium border-b-2 -mb-px ${
                workspaceMode === tab.mode
                  ? 'border-primary-600 text-primary-700'
                  : 'border-transparent text-slate-500 hover:text-slate-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {workspaceMode === 'search' && <SearchPanel organizationId={user?.id ?? ''} />}
        {workspaceMode === 'multi' && <MultiAnalysisPanel organizationId={user?.id ?? ''} />}
        {workspaceMode === 'proposal' && <ProposalPanel organizationId={user?.id ?? ''} />}

        {workspaceMode === 'rfx' && (<>
        <div className="space-y-3 border-b border-slate-200 bg-slate-50 p-4">
          <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
            <label className="block rounded-lg border border-dashed border-slate-300 bg-white p-3 text-xs text-slate-600">
              <span className="mb-2 inline-flex items-center gap-1 font-semibold text-slate-700">
                <UploadCloud className="h-4 w-4" /> 회사 문서 등록
              </span>
              <input
                className="block w-full text-xs"
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                multiple
                onChange={(event) => setCompanyFiles(Array.from(event.target.files || []))}
              />
              <p className="mt-2 truncate text-[11px] text-slate-500">
                {companyFiles.length ? `${companyFiles.length}개 파일 선택됨` : '선택된 파일 없음'}
              </p>
            </label>

            <label className="block rounded-lg border border-dashed border-slate-300 bg-white p-3 text-xs text-slate-600">
              <span className="mb-2 inline-flex items-center gap-1 font-semibold text-slate-700">
                <FileText className="h-4 w-4" /> 분석 문서 등록
              </span>
              <input
                className="block w-full text-xs"
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={(event) => setTargetFile(event.target.files?.[0] || null)}
              />
              <p className="mt-2 truncate text-[11px] text-slate-500">
                {targetFile?.name || '선택된 파일 없음'}
              </p>
            </label>
          </div>

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Button
              size="sm"
              onClick={uploadCompany}
              disabled={isUploading || !companyFiles.length || !sessionId}
              className="w-full"
            >
              {isUploading ? <Loader2 className="h-4 w-4 animate-spin" /> : '회사 문서 등록'}
            </Button>
            <Button
              size="sm"
              onClick={runAnalysis}
              disabled={isAnalyzing || !targetFile || !sessionId}
              className="w-full"
            >
              {isAnalyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : '분석 실행'}
            </Button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto bg-slate-50 p-4">
          <div className="space-y-4">
            {messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                {msg.role === 'model' ? (
                  <div className="mr-2 mt-0.5 flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white">
                    <Bot className="h-4 w-4 text-primary-600" />
                  </div>
                ) : null}
                <div className={`max-w-[86%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${msg.role === 'user' ? 'bg-primary-700 text-white' : 'border border-slate-200 bg-white text-slate-700'}`}>
                  <p className="whitespace-pre-line">{msg.text}</p>
                  {msg.references?.length ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {msg.references.slice(0, 5).map((ref, idx) => (
                        <button
                          key={`${msg.id}_ref_${idx}`}
                          type="button"
                          className="rounded-full border border-slate-300 bg-slate-50 px-2 py-0.5 text-[11px] text-slate-600 hover:bg-slate-100"
                          onClick={() => setSelectedPdfPage(ref.page)}
                          title={ref.text || `p.${ref.page}`}
                        >
                          📄 p.{ref.page}
                        </button>
                      ))}
                    </div>
                  ) : null}
                </div>
                {msg.role === 'user' ? (
                  <div className="ml-2 mt-0.5 flex h-7 w-7 items-center justify-center rounded-full border border-slate-200 bg-white">
                    <UserIcon className="h-4 w-4 text-slate-500" />
                  </div>
                ) : null}
              </div>
            ))}

            {result ? (
              <div className="rounded-2xl border border-slate-200 bg-white p-3 text-xs text-slate-600">
                <p className="font-semibold text-slate-700">분석 상태</p>
                <p className="mt-1">적합도 {Math.round(result.matching.overall_score)}% · 미충족 {result.matching.not_met_count}개</p>
                <div className="mt-2 flex gap-2">
                  {(Object.keys(result.matching.assistant_opinions || {}) as OpinionMode[])
                    .filter((mode, index, arr) => arr.indexOf(mode) === index)
                    .map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        className={`rounded-full border px-2 py-0.5 text-[11px] ${
                          opinionMode === mode
                            ? 'border-primary-700 bg-primary-700 text-white'
                            : 'border-slate-300 bg-white text-slate-600'
                        }`}
                        onClick={() => setOpinionMode(mode)}
                      >
                        {modeLabel[mode] || mode}
                      </button>
                    ))}
                </div>
                {selectedOpinion?.actions?.length ? (
                  <ul className="mt-2 space-y-1">
                    {selectedOpinion.actions.slice(0, 3).map((action, idx) => (
                      <li key={idx} className="flex items-start gap-1">
                        <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 text-emerald-600" />
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>

        <div className="border-t border-slate-200 bg-white p-3">
          <div className="mb-2 flex flex-wrap gap-2">
            {suggestedQuestions.map((item) => (
              <button
                key={item}
                type="button"
                className="rounded-full border border-slate-300 bg-slate-50 px-3 py-1 text-xs text-slate-600 hover:bg-slate-100"
                onClick={() => void sendQuestion(item)}
              >
                {item}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-2">
            <input
              value={chatInput}
              onChange={(event) => setChatInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter') {
                  event.preventDefault();
                  void sendQuestion();
                }
              }}
              placeholder="분석 결과에 대해 질문하세요"
              className="h-10 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-primary-500"
            />
            <Button size="sm" onClick={() => void sendQuestion()} disabled={isChatting}>
              {isChatting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
            </Button>
          </div>
        </div>
        </>)}
      </div>
    </div>
  );
};

export default Dashboard;
