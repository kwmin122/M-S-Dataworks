import { useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatContext, createNewConversation } from '../context/ChatContext';
import { useActiveConversation } from './useActiveConversation';
import * as api from '../services/kiraApiService';
import { trackEvent } from '../utils/analytics';
import { REGIONS } from '../constants/filters';
import type {
  ChatMessage,
  ChecklistChatMessage,
  CompanyProfile,
  MessageAction,
  ConversationPhase,
  TextChatMessage,
  ButtonChoiceMessage,
  FileUploadMessage,
  StatusChatMessage,
  BidCardListMessage,
  AnalysisResultMessage,
  InlineFormMessage,
  DocFileType,
  DocumentTab,
} from '../types';

const UPLOAD_ACCEPT = '.pdf,.doc,.docx,.txt,.hwp,.hwpx,.xlsx,.xls,.csv,.pptx,.ppt';

const DOC_HISTORY_MAX = 10;

/** Push a new entry to a sessionStorage document history array (max DOC_HISTORY_MAX). */
function pushDocHistory<T>(key: string, data: T, label: string): void {
  try {
    const raw = sessionStorage.getItem(key);
    let arr: Array<{ id: string; timestamp: number; label: string; data: T }> = [];
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        arr = parsed;
      } else {
        // Legacy single-object format — wrap it
        arr = [{ id: `legacy_${Date.now()}`, timestamp: Date.now(), label: '이전 생성물', data: parsed as T }];
      }
    }
    const entry = { id: `doc_${Date.now()}`, timestamp: Date.now(), label, data };
    arr = [entry, ...arr].slice(0, DOC_HISTORY_MAX);
    sessionStorage.setItem(key, JSON.stringify(arr));
  } catch { /* noop */ }
}

const GREETING_PATTERN = /^(안녕|하이|헬로|hi|hello|반가|좋은\s*(아침|오후|저녁)|감사|고마워|ㅎㅇ|ㅎ2)[\s!?.~ㅋㅎ]*$/i;

function detectFileType(fileName: string): DocFileType {
  const ext = fileName.toLowerCase().split('.').pop() || '';
  if (ext === 'pdf') return 'pdf';
  if (['xlsx', 'xls', 'csv'].includes(ext)) return 'excel';
  if (['hwp', 'hwpx'].includes(ext)) return 'hwp';
  if (['doc', 'docx'].includes(ext)) return 'docx';
  if (['ppt', 'pptx'].includes(ext)) return 'ppt';
  return 'other';
}

function buildDocumentTabs(
  analysisDoc: { url: string; fileName: string } | null,
  companyDocs: { name: string; url: string }[],
): DocumentTab[] {
  const tabs: DocumentTab[] = [];
  if (analysisDoc) {
    tabs.push({
      label: '분석문서',
      url: analysisDoc.url,
      fileName: analysisDoc.fileName,
      fileType: detectFileType(analysisDoc.fileName),
      page: 1,
    });
  }
  if (companyDocs.length === 1) {
    tabs.push({
      label: '회사문서',
      url: companyDocs[0].url,
      fileName: companyDocs[0].name,
      fileType: detectFileType(companyDocs[0].name),
    });
  } else if (companyDocs.length > 1) {
    // Show first company doc — user can switch via the tab
    tabs.push({
      label: `회사문서 (${companyDocs.length})`,
      url: companyDocs[0].url,
      fileName: companyDocs[0].name,
      fileType: detectFileType(companyDocs[0].name),
    });
  }
  return tabs;
}

const CATEGORY_MAP: Record<string, string> = {
  '전체': 'all',
  '물품': 'goods',
  '용역': 'service',
  '공사': 'construction',
  '외자': 'foreign',
  '기타': 'etc',
};

const PERIOD_MAP: Record<string, string> = {
  '최근 1개월': '1m',
  '최근 3개월': '3m',
  '최근 6개월': '6m',
};

let msgCounter = 0;
function msgId(): string {
  msgCounter += 1;
  return `msg_${Date.now()}_${msgCounter}`;
}

function buildSearchFormFields() {
  return [
    { key: 'keywords', label: '공고명 키워드', type: 'text' as const },
    {
      key: 'category',
      label: '업무구분',
      type: 'select' as const,
      options: ['전체', '물품', '용역', '공사', '외자', '기타'],
    },
    {
      key: 'region',
      label: '지역 (선택)',
      type: 'select' as const,
      options: ['전체', ...REGIONS],
    },
    {
      key: 'period',
      label: '기간',
      type: 'select' as const,
      options: ['최근 1개월', '최근 3개월', '최근 6개월'],
    },
    { key: 'minAmt', label: '최소 금액 (선택)', type: 'number' as const },
    { key: 'maxAmt', label: '최대 금액 (선택)', type: 'number' as const },
  ];
}

export function useConversationFlow() {
  const { state, dispatch } = useChatContext();
  const { conversation, conversationId } = useActiveConversation();
  const navigate = useNavigate();

  // Keep latest refs for async operations to avoid stale closures
  const conversationRef = useRef(conversation);
  conversationRef.current = conversation;
  const contextPanelRef = useRef(state.contextPanel);
  contextPanelRef.current = state.contextPanel;

  const push = useCallback(
    (message: ChatMessage) => {
      if (!conversationId) return;
      dispatch({ type: 'PUSH_MESSAGE', conversationId, message });
    },
    [conversationId, dispatch],
  );

  const updateMsg = useCallback(
    (messageId: string, updates: Partial<ChatMessage>) => {
      if (!conversationId) return;
      dispatch({ type: 'UPDATE_MESSAGE', conversationId, messageId, updates });
    },
    [conversationId, dispatch],
  );

  const setPhase = useCallback(
    (phase: ConversationPhase) => {
      if (!conversationId) return;
      dispatch({ type: 'SET_PHASE', conversationId, phase });
    },
    [conversationId, dispatch],
  );

  const setProcessing = useCallback(
    (v: boolean) => dispatch({ type: 'SET_PROCESSING', value: v }),
    [dispatch],
  );

  const updateConv = useCallback(
    (updates: Record<string, unknown>) => {
      if (!conversationId) return;
      dispatch({ type: 'UPDATE_CONVERSATION', conversationId, updates });
    },
    [conversationId, dispatch],
  );

  // ── Helper message builders ──

  const pushText = useCallback(
    (text: string, references?: { page: number; text: string }[], scoped_to?: string[]) => {
      push({
        id: msgId(),
        role: 'bot',
        type: 'text',
        timestamp: Date.now(),
        text,
        references,
        scoped_to,
      } as TextChatMessage);
    },
    [push],
  );

  const pushStatus = useCallback(
    (level: 'loading' | 'success' | 'error' | 'info', text: string, retryAction?: string) => {
      const id = msgId();
      push({
        id,
        role: 'bot',
        type: 'status',
        timestamp: Date.now(),
        text,
        level,
        retryAction,
      } as StatusChatMessage);
      return id;
    },
    [push],
  );

  const removeLastStatus = useCallback(() => {
    if (!conversationId) return;
    dispatch({ type: 'REMOVE_LAST_STATUS', conversationId });
  }, [conversationId, dispatch]);

  // ── Start new conversation with greeting ──

  const startNewConversation = useCallback(() => {
    const conv = createNewConversation();
    dispatch({ type: 'CREATE_CONVERSATION', conversation: conv });

    // Load company profile and store in conversation
    api.getCompanyProfile().then((profile: CompanyProfile | null) => {
      if (profile && profile.companyName) {
        dispatch({
          type: 'UPDATE_CONVERSATION',
          conversationId: conv.id,
          updates: { companyProfile: profile },
        });
      }
    }).catch(() => {});

    return conv.id;
  }, [dispatch]);

  // ── Handle user text input ──

  const handleUserText = useCallback(
    async (text: string, sourceFiles?: string[]) => {
      if (!conversationId || !conversation) return;
      if (state.isProcessing) return;

      push({
        id: msgId(),
        role: 'user',
        type: 'text',
        timestamp: Date.now(),
        text,
      } as TextChatMessage);

      trackEvent('chat_message_sent', { message_length: text.length, conversation_id: conversationId });

      // Auto-title for non-greeting phases
      if (conversation.phase !== 'greeting' && conversation.title === 'KiraBot') {
        const autoTitle = text.length > 20 ? text.slice(0, 20) + '...' : text;
        updateConv({ title: autoTitle });
      }

      // If in doc_chat phase, send to chat API
      if (conversation.phase === 'doc_chat' && conversation.sessionId) {
        setProcessing(true);
        pushStatus('loading', '답변을 생성하고 있어요...');
        try {
          const res = await api.chatWithReferences(conversation.sessionId, text, sourceFiles);
          removeLastStatus();
          pushText(res.answer, res.references, res.scoped_to);
          if (conversation.activeDocFilter) updateConv({ activeDocFilter: null });
          if (res.references?.length) {
            const panel = contextPanelRef.current;
            const currentUrl = conversation?.uploadedFileUrl ||
              (panel.type === 'pdf' ? panel.blobUrl : '') ||
              (panel.type === 'documents' ? panel.tabs[0]?.url : '');

            if (panel.type === 'documents') {
              const updatedTabs = panel.tabs.map((tab, i) =>
                i === 0 ? { ...tab, page: res.references![0].page } : tab,
              );
              dispatch({
                type: 'SET_CONTEXT_PANEL',
                content: { type: 'documents', tabs: updatedTabs, activeTabIndex: 0 },
              });
            } else if (currentUrl) {
              dispatch({
                type: 'SET_CONTEXT_PANEL',
                content: { type: 'pdf', blobUrl: currentUrl, page: res.references[0].page },
              });
            }
          }
        } catch (error) {
          removeLastStatus();
          const msg = error instanceof Error ? error.message : '알 수 없는 오류';
          pushStatus('error', `질문 처리 실패: ${msg}`, 'chat');
        } finally {
          setProcessing(false);
        }
        return;
      }

      // doc_upload_company phase: 텍스트로 회사 정보 입력
      if (conversation.phase === 'doc_upload_company' && text.length > 0 && text.length < 10) {
        pushText('회사 정보를 10자 이상 입력해주세요. 예: "IT 서비스 전문기업, 직원 50명, 연매출 30억, 소프트웨어 개발 실적 보유"');
        return;
      }
      if (conversation.phase === 'doc_upload_company' && text.length >= 10) {
        setProcessing(true);
        pushStatus('loading', '회사 정보를 등록하고 있어요...');
        try {
          let sid = conversationRef.current?.sessionId ?? conversation.sessionId;
          if (!sid) {
            sid = await api.createSession();
            updateConv({ sessionId: sid });
          }
          const result = await api.uploadCompanyText(sid, text);
          removeLastStatus();
          const existingUrls = (conversationRef.current?.companyDocUrls || []).filter(d => d.name !== 'company_info.txt');
          updateConv({
            companyChunks: result.company_chunks,
            companyDocuments: result.documents || [],
            companyDocUrls: [...existingUrls, { name: 'company_info.txt', url: `/api/files/${sid}/company/company_info.txt` }],
          });

          const prevPhase = conversation._prevPhase;
          if (prevPhase && prevPhase !== 'doc_upload_company') {
            pushText(`회사 정보가 등록되었습니다. (${result.company_chunks}개 지식 조각)`);
            if ((prevPhase === 'doc_chat' || prevPhase === 'bid_search_results' || prevPhase === 'bid_eval_results') && sid) {
              pushStatus('loading', '회사 역량과 공고 요건을 비교 분석하고 있어요...');
              try {
                const rematchResult = await api.rematchWithCompanyDocs(sid);
                removeLastStatus();
                push({
                  id: msgId(), role: 'bot', type: 'analysis_result', timestamp: Date.now(),
                  analysis: rematchResult, opinionMode: conversation.opinionMode,
                } as AnalysisResultMessage);
                pushText('회사 정보를 기반으로 GO/NO-GO 맞춤 분석이 완료되었습니다!');
              } catch (rematchErr) {
                removeLastStatus();
                pushStatus('error', `재매칭 실패: ${rematchErr instanceof Error ? rematchErr.message : '알 수 없는 오류'}`);
              }
            }
            setPhase(prevPhase);
            updateConv({ _prevPhase: undefined });
          } else {
            pushText(`회사 정보 등록 완료! ${result.company_chunks}개 지식 조각이 준비되었습니다.`);
            setPhase('doc_upload_target');
            push({
              id: msgId(), role: 'bot', type: 'file_upload', timestamp: Date.now(),
              text: '이제 분석할 문서(RFP/입찰공고)를 업로드해주세요.',
              accept: UPLOAD_ACCEPT, multiple: true,
            } as FileUploadMessage);
          }
        } catch (error) {
          removeLastStatus();
          pushStatus('error', `회사 정보 등록 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`, 'upload_company');
        } finally {
          setProcessing(false);
        }
        return;
      }

      // doc_chat phase: 회사 정보가 포함된 텍스트 감지 → 자동 등록 + 재매칭
      if (conversation.phase === 'doc_chat' && conversation.sessionId && /우리\s*(회사|업체|기업)|보유\s*(면허|인증|자격)|연매출|직원\s*수|실적/i.test(text)) {
        setProcessing(true);
        pushStatus('loading', '회사 정보를 등록하고 분석에 반영하고 있어요...');
        try {
          await api.uploadCompanyText(conversation.sessionId, text);
          const rematchResult = await api.rematchWithCompanyDocs(conversation.sessionId);
          removeLastStatus();
          push({
            id: msgId(), role: 'bot', type: 'analysis_result', timestamp: Date.now(),
            analysis: rematchResult, opinionMode: conversation.opinionMode,
          } as AnalysisResultMessage);
          pushText('입력하신 회사 정보를 기반으로 GO/NO-GO 분석을 업데이트했습니다! 추가 질문이 있으시면 말씀해주세요.');
        } catch (error) {
          removeLastStatus();
          // 실패 시 일반 채팅으로 폴백
          pushStatus('loading', '답변을 생성하고 있어요...');
          try {
            const res = await api.chatWithReferences(conversation.sessionId!, text, sourceFiles);
            removeLastStatus();
            pushText(res.answer, res.references, res.scoped_to);
          } catch {
            removeLastStatus();
            pushStatus('error', `처리 실패: ${error instanceof Error ? error.message : '알 수 없는 오류'}`);
          }
        } finally {
          setProcessing(false);
        }
        return;
      }

      // greeting phase: 텍스트 입력
      if (conversation.phase === 'greeting') {
        // 인사말 감지 → 봇 인사 응답 + phase 유지 (WelcomeScreen 유지, 타이틀 변경 없음)
        if (GREETING_PATTERN.test(text)) {
          pushText('안녕하세요! 공고 키워드를 입력하거나 아래 기능을 선택해주세요.');
          return;
        }

        // 비인사 텍스트 → 일반 챗봇 모드로 전환 + 자동 타이틀 설정
        if (conversation.title === 'KiraBot') {
          const autoTitle = text.length > 20 ? text.slice(0, 20) + '...' : text;
          updateConv({ title: autoTitle });
        }
        setPhase('free_chat');
        // free_chat으로 fall-through
      }

      // 일반 챗봇 모드 또는 기타 페이즈에서 텍스트 입력 시 generalChat으로 폴백
      {
        setProcessing(true);
        pushStatus('loading', '답변을 생성하고 있어요...');

        try {
          // 최근 대화 히스토리 수집 (최대 6개)
          const history = conversation.messages
            .filter(m => m.type === 'text')
            .slice(-6)
            .map(m => ({
              role: m.role === 'user' ? 'user' : 'assistant',
              content: (m as TextChatMessage).text,
            }));

          const res = await api.generalChat(text, history);
          removeLastStatus();
          pushText(res.answer);
        } catch (error) {
          removeLastStatus();
          const msg = error instanceof Error ? error.message : '알 수 없는 오류';
          pushStatus('error', `응답 생성 실패: ${msg}`);
        } finally {
          setProcessing(false);
        }
        return;
      }
    },
    [conversationId, conversation, push, pushText, pushStatus, removeLastStatus, setProcessing, setPhase, updateConv, dispatch],
  );

  // ── Shared FSM transition for feature selection ──

  const handleFeatureSelection = useCallback(
    (value: string) => {
      if (!conversationId || !conversation) return;

      if (value === 'doc_analysis') {
        trackEvent('chat_started', { mode: 'document_analysis' });

        if (conversation.companyProfile?.companyName) {
          // Company profile exists — skip company upload choice, go to target upload
          pushText(`🏢 ${conversation.companyProfile.companyName} 정보가 연동되어 있습니다. 분석할 문서를 업로드해주세요.`);
          setPhase('doc_upload_target');
          push({
            id: msgId(),
            role: 'bot',
            type: 'file_upload',
            timestamp: Date.now(),
            text: '분석할 문서(RFP/입찰공고)를 업로드해주세요.',
            accept: UPLOAD_ACCEPT,
            multiple: true,
          } as FileUploadMessage);
        } else {
          // No company profile — show original choice with settings hint
          pushText('회사 문서를 먼저 등록하면 자격 매칭 비교가 가능합니다. 문서만 분석할 수도 있습니다.\n\n💡 설정 > 회사 정보에서 등록하면 매번 업로드 없이 자동 분석됩니다.');
          setPhase('doc_upload_company');
          push({
            id: msgId(),
            role: 'bot',
            type: 'button_choice',
            timestamp: Date.now(),
            text: '',
            choices: [
              { label: '회사 문서 먼저 등록', value: 'start_company_upload' },
              { label: '바로 문서 분석', value: 'skip_to_target' },
            ],
          } as ButtonChoiceMessage);
        }
      } else if (value === 'bid_search') {
        trackEvent('chat_started', { mode: 'bid_search' });
        if (conversation.companyProfile?.companyName) {
          pushText(`🏢 ${conversation.companyProfile.companyName} 정보가 연동되어 공고 분석 시 자동 활용됩니다.`);
        } else if (!conversation.companyChunks || conversation.companyChunks <= 0) {
          pushText('💡 설정 > 회사 정보에서 등록하면 검색된 공고에 대해 자동 맞춤 분석과 GO/NO-GO 판정을 받을 수 있어요.');
        }
        setPhase('bid_search_input');
        push({
          id: msgId(),
          role: 'bot',
          type: 'inline_form',
          timestamp: Date.now(),
          text: '검색 조건을 입력해주세요.',
          fields: buildSearchFormFields(),
          submitLabel: '검색',
        } as InlineFormMessage);
      } else if (value === 'setup_alert') {
        trackEvent('chat_started', { mode: 'alert_setup' });
        navigate('/alerts');
      } else if (value === 'company_onboarding') {
        trackEvent('chat_started', { mode: 'company_onboarding' });
        setPhase('doc_chat');
        pushText('회사 역량 DB를 구축합니다. 먼저 기본 정보를 입력해주세요.');
        push({
          id: msgId(),
          role: 'bot',
          type: 'inline_form',
          timestamp: Date.now(),
          text: '회사 기본정보',
          fields: [
            { key: 'company_name', label: '회사명', type: 'text' },
            { key: 'business_type', label: '업종 (예: IT, 건설)', type: 'text' },
            { key: 'employee_count', label: '직원 수', type: 'number' },
          ],
          submitLabel: '저장 후 실적 입력',
        } as InlineFormMessage);
        updateConv({ _onboardingStep: 'basic_info' });
      }
    },
    [conversationId, conversation, push, pushText, setPhase, navigate, updateConv],
  );

  // ── Handle message actions (FSM transitions) ──

  const handleAction = useCallback(
    async (action: MessageAction) => {
      if (!conversationId || !conversation) return;
      // Guard against concurrent async operations — ignore if already processing
      if (state.isProcessing) return;

      switch (action.type) {
        case 'choice_selected': {
          // Mark button as selected
          updateMsg(action.messageId, { selectedValue: action.value } as Partial<ButtonChoiceMessage>);

          // Push user "selected" message
          const labelMap: Record<string, string> = {
            doc_analysis: '일반 문서 분석',
            bid_search: '공고 검색/분석',
            setup_alert: '공고 알림 설정',
            upload_target: '분석 문서 업로드',
            add_company_docs: '회사 문서 추가 업로드',
            start_company_upload: '회사 문서 먼저 등록',
            company_upload_file: '파일 업로드',
            company_input_text: '텍스트로 입력',
            skip_to_target: '바로 문서 분석',
            company_onboarding: '회사 역량 DB 구축',
          };
          const label = labelMap[action.value] || action.value;
          push({
            id: msgId(),
            role: 'user',
            type: 'text',
            timestamp: Date.now(),
            text: label,
          } as TextChatMessage);

          if (action.value === 'doc_analysis' || action.value === 'bid_search' || action.value === 'setup_alert' || action.value === 'company_onboarding') {
            handleFeatureSelection(action.value);
          } else if (action.value === 'upload_target') {
            setPhase('doc_upload_target');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '분석할 문서(RFP/입찰공고)를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.value === 'add_company_docs') {
            setPhase('doc_upload_company');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '추가할 회사 문서를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.value === 'start_company_upload') {
            setPhase('doc_upload_company');
            pushText('회사 정보를 어떻게 등록하시겠어요?');
            push({
              id: msgId(),
              role: 'bot',
              type: 'button_choice',
              timestamp: Date.now(),
              text: '',
              choices: [
                { label: '파일 업로드', value: 'company_upload_file' },
                { label: '텍스트로 입력', value: 'company_input_text' },
              ],
            } as ButtonChoiceMessage);
          } else if (action.value === 'company_upload_file') {
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '회사 문서를 업로드해주세요. (여러 파일 가능)',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.value === 'company_input_text') {
            pushText('회사 정보를 자유롭게 입력해주세요.\n\n예시:\n- 업종: 정보통신공사업 면허 보유\n- 연매출: 50억원\n- 직원 수: 30명\n- 주요 실적: CCTV 설치 공사 10건 이상\n- 보유 인증: ISO 9001, 정보보안 인증');
          } else if (action.value === 'skip_to_target') {
            setPhase('doc_upload_target');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '분석할 문서(RFP/입찰공고)를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          }
          break;
        }

        case 'files_uploaded': {
          const { files, messageId } = action;
          const fileNames = files.map((f) => f.name);

          // Update file upload message with uploaded names
          updateMsg(messageId, { uploadedFileNames: fileNames } as Partial<FileUploadMessage>);

          if (conversation.phase === 'doc_upload_company') {
            trackEvent('document_uploaded', { doc_type: 'company', file_type: files[0]?.name.split('.').pop() });
            setProcessing(true);
            pushStatus('loading', '회사 문서를 등록하고 있어요...');

            try {
              // Create session if needed — use ref for latest value
              let sid = conversationRef.current?.sessionId ?? conversation.sessionId;
              if (!sid) {
                sid = await api.createSession();
                updateConv({ sessionId: sid });
              }

              const result = await api.uploadCompanyDocuments(sid, files);
              removeLastStatus();

              // Store company doc URLs from server
              const newCompanyDocs = (result.fileUrls || []).map((url: string, i: number) => ({
                name: files[i]?.name || url.split('/').pop() || 'document',
                url: `${api.getApiBaseUrl()}${url}`,
              }));
              const existingDocs = conversation.companyDocUrls || [];
              updateConv({
                companyChunks: result.company_chunks,
                companyDocUrls: [...existingDocs, ...newCompanyDocs],
                companyDocuments: result.documents || [],
                _justUploadedFiles: files.map(f => f.name),
              });

              // 헤더 버튼으로 추가 업로드한 경우 → 이전 phase로 복귀
              // eslint-disable-next-line @typescript-eslint/no-explicit-any
              const prevPhase = (conversation as any)._prevPhase as ConversationPhase | undefined;
              if (prevPhase && prevPhase !== 'doc_upload_company') {
                pushText(`회사 문서가 추가되었습니다. (총 ${result.company_chunks}개 지식 조각)`);

                // 이전에 분석한 문서가 있으면 자동 재매칭 수행
                if ((prevPhase === 'doc_chat' || prevPhase === 'bid_search_results' || prevPhase === 'bid_eval_results') && sid) {
                  pushStatus('loading', '회사 역량과 공고 요건을 비교 분석하고 있어요...');
                  try {
                    const rematchResult = await api.rematchWithCompanyDocs(sid);
                    removeLastStatus();
                    push({
                      id: msgId(),
                      role: 'bot',
                      type: 'analysis_result',
                      timestamp: Date.now(),
                      analysis: rematchResult,
                      opinionMode: conversation.opinionMode,
                    } as AnalysisResultMessage);
                    pushText('회사 문서를 기반으로 GO/NO-GO 맞춤 분석이 완료되었습니다! 결과에 대해 자유롭게 질문해주세요.');
                  } catch (rematchErr) {
                    removeLastStatus();
                    const rmsg = rematchErr instanceof Error ? rematchErr.message : '알 수 없는 오류';
                    pushStatus('error', `재매칭 실패: ${rmsg}`);
                  }
                }

                setPhase(prevPhase);
                updateConv({ _prevPhase: undefined });
              } else {
                // 최초 회사 문서 등록 → 분석 문서 업로드 진행
                pushText(`회사 문서 등록 완료! ${result.company_chunks}개 지식 조각이 준비되었습니다.`);
                setPhase('doc_upload_target');

                push({
                  id: msgId(),
                  role: 'bot',
                  type: 'file_upload',
                  timestamp: Date.now(),
                  text: '이제 분석할 문서(RFP/입찰공고)를 업로드해주세요.',
                  accept: UPLOAD_ACCEPT,
                  multiple: true,
                } as FileUploadMessage);
              }
            } catch (error) {
              removeLastStatus();
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `회사 문서 등록 실패: ${msg}`, 'upload_company');
            } finally {
              setProcessing(false);
            }
          } else if (conversation.phase === 'doc_upload_target') {
            trackEvent('document_uploaded', { doc_type: 'analysis', file_type: files[0]?.name.split('.').pop(), file_count: files.length });
            setProcessing(true);
            setPhase('doc_analyzing');
            pushStatus('loading', files.length > 1
              ? `${files.length}개 문서를 분석하고 있어요. 잠시만 기다려주세요...`
              : '문서를 분석하고 있어요. 잠시만 기다려주세요...');

            try {
              // Use ref for latest session value
              let sid = conversationRef.current?.sessionId ?? conversation.sessionId;
              if (!sid) {
                sid = await api.createSession();
                updateConv({ sessionId: sid });
              }

              const result = await api.analyzeDocument(sid, files);
              removeLastStatus();

              // Build document tabs for context panel
              const allFileNames = result.filenames || [result.filename];
              const allFileUrls = (result.fileUrls || (result.fileUrl ? [result.fileUrl] : []))
                .map(u => `${api.getApiBaseUrl()}${u}`);
              const primaryFileName = allFileNames[0];

              // Primary analysis URL — prefer server URL, fallback to blob for PDF
              let analysisUrl: string | null = allFileUrls[0] || null;
              if (!analysisUrl && files[0].type.includes('pdf')) {
                analysisUrl = URL.createObjectURL(files[0]);
              }

              if (analysisUrl) {
                // Revoke previous blob URL if it exists
                const prev = conversation.uploadedFileUrl;
                if (prev?.startsWith('blob:')) URL.revokeObjectURL(prev);
                updateConv({
                  uploadedFileUrl: analysisUrl,
                  uploadedFileName: primaryFileName,
                  uploadedFileUrls: allFileUrls,
                  uploadedFileNames: allFileNames,
                });
                const companyDocs = conversation.companyDocUrls || [];
                const tabs = buildDocumentTabs({ url: analysisUrl, fileName: primaryFileName }, companyDocs);
                if (tabs.length > 0) {
                  dispatch({
                    type: 'SET_CONTEXT_PANEL',
                    content: { type: 'documents', tabs, activeTabIndex: 0 },
                  });
                }
              }

              push({
                id: msgId(),
                role: 'bot',
                type: 'analysis_result',
                timestamp: Date.now(),
                analysis: result,
                opinionMode: conversation.opinionMode,
              } as AnalysisResultMessage);

              // Save analysis to localStorage for DocumentWorkspace RFP tab
              try {
                const analysisLabel = result.analysis?.title || allFileNames[0] || '문서 분석';
                const analysisWithMeta = { ...result.analysis, _fileNames: allFileNames, _fileUrl: analysisUrl && !analysisUrl.startsWith('blob:') ? analysisUrl : '' };
                pushDocHistory('kira_last_analysis', analysisWithMeta, analysisLabel);
                if (sid) sessionStorage.setItem('kira_session_id', sid);
              } catch { /* noop */ }

              trackEvent('document_analyzed', { doc_type: 'analysis', analysis_type: result.analysis?.document_type, file_count: files.length });
              if (conversation.companyProfile?.companyName) {
                pushText(`🏢 ${conversation.companyProfile.companyName} 정보와 함께 비교 분석이 완료되었습니다! 결과에 대해 자유롭게 질문해주세요.`);
              } else {
                const multiNote = files.length > 1 ? ` (${files.length}개 문서 통합 분석)` : '';
                pushText(`📄 문서 분석이 완료되었습니다${multiNote}! 결과에 대해 자유롭게 질문해주세요. 💡 설정 > 회사 정보를 등록하면 맞춤 비교 분석이 가능합니다.`);
              }
              setPhase('doc_chat');
              updateConv({ title: result.analysis?.title || '문서 분석' });
            } catch (error) {
              removeLastStatus();
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `문서 분석 실패: ${msg}`, 'analyze');
              setPhase('doc_upload_target');
            } finally {
              setProcessing(false);
            }
          }
          break;
        }

        case 'form_submitted': {
          const { values, messageId } = action;
          updateMsg(messageId, { submittedValues: values } as Partial<InlineFormMessage>);

          // ── 회사 DB 온보딩 폼 처리 ──
          const _obStep = conversation?._onboardingStep;
          if (_obStep === 'basic_info') {
            setProcessing(true);
            try {
              await api.updateCompanyDbProfile({
                company_name: values.company_name || '',
                business_type: values.business_type || '',
                employee_count: parseInt(values.employee_count || '0', 10),
              });
              pushText(`회사 기본정보가 저장되었습니다: **${values.company_name}**`);
              push({
                id: msgId(), role: 'bot', type: 'inline_form', timestamp: Date.now(),
                text: '실적을 추가해주세요. (완료하려면 프로젝트명을 비워두고 제출)',
                fields: [
                  { key: 'project_name', label: '프로젝트명', type: 'text' },
                  { key: 'client', label: '발주처', type: 'text' },
                  { key: 'contract_amount', label: '계약금액', type: 'text' },
                  { key: 'period', label: '수행기간 (예: 2024.01~2024.12)', type: 'text' },
                  { key: 'description', label: '사업 설명', type: 'text' },
                ],
                submitLabel: '실적 추가',
              } as InlineFormMessage);
              updateConv({ _onboardingStep: 'track_records' });
            } catch (error) {
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `기본정보 저장 실패: ${msg}`);
            } finally {
              setProcessing(false);
            }
            break;
          }

          if (_obStep === 'track_records') {
            if (!values.project_name?.trim()) {
              pushText('실적 입력을 완료합니다. 이제 주요 인력을 등록해주세요.');
              push({
                id: msgId(), role: 'bot', type: 'inline_form', timestamp: Date.now(),
                text: '인력 정보를 추가해주세요. (완료하려면 이름을 비워두고 제출)',
                fields: [
                  { key: 'name', label: '이름', type: 'text' },
                  { key: 'role', label: '역할 (PM, PL, 개발자 등)', type: 'text' },
                  { key: 'experience_years', label: '경력(년)', type: 'number' },
                  { key: 'certifications', label: '자격증 (쉼표 구분)', type: 'text' },
                ],
                submitLabel: '인력 추가',
              } as InlineFormMessage);
              updateConv({ _onboardingStep: 'personnel' });
              break;
            }
            setProcessing(true);
            try {
              const result = await api.addTrackRecord({
                project_name: values.project_name,
                client: values.client || '',
                contract_amount: values.contract_amount || '',
                period: values.period || '',
                description: values.description || '',
              });
              pushText(`실적이 추가되었습니다: **${values.project_name}** (DB 총 ${result.total}건)`);
              push({
                id: msgId(), role: 'bot', type: 'inline_form', timestamp: Date.now(),
                text: '추가 실적을 입력하세요. (완료하려면 프로젝트명을 비워두고 제출)',
                fields: [
                  { key: 'project_name', label: '프로젝트명', type: 'text' },
                  { key: 'client', label: '발주처', type: 'text' },
                  { key: 'contract_amount', label: '계약금액', type: 'text' },
                  { key: 'period', label: '수행기간', type: 'text' },
                  { key: 'description', label: '사업 설명', type: 'text' },
                ],
                submitLabel: '실적 추가',
              } as InlineFormMessage);
            } catch (error) {
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `실적 추가 실패: ${msg}`);
            } finally {
              setProcessing(false);
            }
            break;
          }

          if (_obStep === 'personnel') {
            if (!values.name?.trim()) {
              setProcessing(true);
              try {
                const stats = await api.getCompanyDbStats();
                pushText(
                  `회사 역량 DB 구축이 완료되었습니다!\n\n` +
                  `- 실적: **${stats.track_record_count}건**\n` +
                  `- 인력: **${stats.personnel_count}명**\n` +
                  `- 전체 지식 단위: **${stats.total_knowledge_units}건**\n\n` +
                  `이제 제안서 생성 시 회사 맞춤 정보가 자동으로 반영됩니다.`
                );
                updateConv({ _onboardingStep: undefined });
                trackEvent('company_onboarding_complete', { units: stats.total_knowledge_units });
              } catch (error) {
                const msg = error instanceof Error ? error.message : '알 수 없는 오류';
                pushStatus('error', `통계 조회 실패: ${msg}`);
              } finally {
                setProcessing(false);
              }
              break;
            }
            setProcessing(true);
            try {
              const certs = values.certifications ? values.certifications.split(',').map((s: string) => s.trim()).filter(Boolean) : [];
              const result = await api.addPersonnel({
                name: values.name,
                role: values.role || '',
                experience_years: parseInt(values.experience_years || '0', 10),
                certifications: certs,
                description: '',
              });
              pushText(`인력이 추가되었습니다: **${values.name}** (${values.role}) (DB 총 ${result.total}건)`);
              push({
                id: msgId(), role: 'bot', type: 'inline_form', timestamp: Date.now(),
                text: '추가 인력을 입력하세요. (완료하려면 이름을 비워두고 제출)',
                fields: [
                  { key: 'name', label: '이름', type: 'text' },
                  { key: 'role', label: '역할', type: 'text' },
                  { key: 'experience_years', label: '경력(년)', type: 'number' },
                  { key: 'certifications', label: '자격증 (쉼표 구분)', type: 'text' },
                ],
                submitLabel: '인력 추가',
              } as InlineFormMessage);
            } catch (error) {
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `인력 추가 실패: ${msg}`);
            } finally {
              setProcessing(false);
            }
            break;
          }

          if (conversation.phase === 'bid_search_input') {
            trackEvent('bid_search', { keyword: values.keywords, region: values.region, category: values.category });
            setProcessing(true);
            pushStatus('loading', '공고를 검색하고 있어요...');

            try {
              const keywords = values.keywords
                ? values.keywords.split(',').map((k) => k.trim()).filter(Boolean)
                : [];
              const category = CATEGORY_MAP[values.category || '전체'] || 'all';
              const period = PERIOD_MAP[values.period] || values.period || '1m';
              const conditions = {
                keywords,
                category,
                region: values.region && values.region !== '전체' ? values.region : undefined,
                minAmt: values.minAmt ? Number(values.minAmt) : undefined,
                maxAmt: values.maxAmt ? Number(values.maxAmt) : undefined,
                period,
                excludeExpired: true,
                page: 1,
                pageSize: 20,
              };

              const result = await api.searchBids(conditions);
              removeLastStatus();

              // Auto-title from search keywords
              if (conversation.title === 'KiraBot' && values.keywords) {
                const kw = values.keywords.length > 20 ? values.keywords.slice(0, 20) + '...' : values.keywords;
                updateConv({ title: `검색: ${kw}` });
              }

              if (result.notices.length > 0) {
                push({
                  id: msgId(),
                  role: 'bot',
                  type: 'bid_card_list',
                  timestamp: Date.now(),
                  text: `${result.total}건 중 ${result.notices.length}건을 표시합니다.`,
                  cards: result.notices,
                  total: result.total,
                  page: result.page,
                  pageSize: result.pageSize,
                  searchConditions: values,
                } as BidCardListMessage);
                setPhase('bid_search_results');
                // 재검색 버튼
                push({
                  id: msgId(),
                  role: 'bot',
                  type: 'button_choice',
                  timestamp: Date.now(),
                  text: '',
                  choices: [
                    { label: '조건 초기화 재검색', value: 'bid_search' },
                  ],
                } as ButtonChoiceMessage);
              } else {
                pushText('검색 결과가 없습니다. 조건을 변경하여 다시 시도해보세요.');
                setPhase('bid_search_input');
                push({
                  id: msgId(),
                  role: 'bot',
                  type: 'inline_form',
                  timestamp: Date.now(),
                  text: '검색 조건을 다시 입력해주세요.',
                  fields: buildSearchFormFields(),
                  submitLabel: '검색',
                } as InlineFormMessage);
              }
            } catch (error) {
              removeLastStatus();
              const msg = error instanceof Error ? error.message : '알 수 없는 오류';
              pushStatus('error', `검색에 실패했어요: ${msg}`, 'bid_search');
            } finally {
              setProcessing(false);
            }
          }
          break;
        }

        case 'search_page': {
          // 페이지네이션: 다른 페이지 검색
          setProcessing(true);
          pushStatus('loading', '페이지를 불러오고 있어요...');

          try {
            const prevConditions = action.conditions;
            const keywords = prevConditions.keywords
              ? prevConditions.keywords.split(',').map((k: string) => k.trim()).filter(Boolean)
              : [];
            const category = CATEGORY_MAP[prevConditions.category || '전체'] || 'all';
            const pagePeriod = PERIOD_MAP[prevConditions.period] || prevConditions.period || '1m';
            const conditions = {
              keywords,
              category,
              region: prevConditions.region && prevConditions.region !== '전체' ? prevConditions.region : undefined,
              minAmt: prevConditions.minAmt ? Number(prevConditions.minAmt) : undefined,
              maxAmt: prevConditions.maxAmt ? Number(prevConditions.maxAmt) : undefined,
              period: pagePeriod,
              excludeExpired: true,
              page: action.page,
              pageSize: 20,
            };

            const result = await api.searchBids(conditions);
            removeLastStatus();

            if (result.notices.length > 0) {
              updateMsg(action.messageId, {
                cards: result.notices,
                total: result.total,
                page: result.page,
                pageSize: result.pageSize,
                selectedIds: undefined,
              } as Partial<BidCardListMessage>);
            }
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `페이지 로드 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'analyze_bid': {
          const { bid } = action;
          trackEvent('bid_evaluation_started', { bid_id: bid.id, bid_title: bid.title });

          setProcessing(true);
          setPhase('bid_analyzing');

          // 세션 없으면 생성 — use ref for latest value
          let sid = conversationRef.current?.sessionId ?? conversation.sessionId;
          if (!sid) {
            try {
              sid = await api.createSession();
              updateConv({ sessionId: sid });
            } catch (err) {
              setProcessing(false);
              const msg = err instanceof Error ? err.message : '알 수 없는 오류';
              pushStatus('error', `세션 생성 실패: ${msg}`);
              setPhase('bid_search_results');
              break;
            }
          }

          pushStatus('loading', `"${bid.title}" 공고를 분석하고 있어요...`);

          try {
            const result = await api.analyzeBidFromNara(
              sid,
              bid.id,
              bid.bidNtceOrd || undefined,
              bid.category || undefined,
            );
            removeLastStatus();

            // 회사 문서 미등록 시 안내 메시지 추가
            if (!conversation.companyChunks || conversation.companyChunks <= 0) {
              pushText('회사 문서를 등록하면 GO/NO-GO 판정과 맞춤 매칭 분석을 받을 수 있어요. 상단의 "회사 문서 추가" 버튼을 이용해보세요.');
            }

            // Document tabs for context panel
            if (result.fileUrl) {
              const fullUrl = `${api.getApiBaseUrl()}${result.fileUrl}`;
              const bidFileName = result.fileUrl.split('/').pop() || `${bid.title}.pdf`;
              updateConv({ uploadedFileUrl: fullUrl, uploadedFileName: bidFileName });
              const companyDocs = conversation.companyDocUrls || [];
              const tabs = buildDocumentTabs({ url: fullUrl, fileName: bidFileName }, companyDocs);
              if (tabs.length > 0) {
                dispatch({
                  type: 'SET_CONTEXT_PANEL',
                  content: { type: 'documents', tabs, activeTabIndex: 0 },
                });
              }
            }

            push({
              id: msgId(),
              role: 'bot',
              type: 'analysis_result',
              timestamp: Date.now(),
              analysis: result,
              opinionMode: conversation.opinionMode,
            } as AnalysisResultMessage);

            // Save analysis to localStorage for DocumentWorkspace RFP tab
            try {
              const bidAnalysisUrl = result.fileUrl ? `${api.getApiBaseUrl()}${result.fileUrl}` : '';
              pushDocHistory('kira_last_analysis', { ...result.analysis, _fileUrl: bidAnalysisUrl }, result.analysis?.title || bid.title || '공고 분석');
              if (sid) sessionStorage.setItem('kira_session_id', sid);
            } catch { /* noop */ }

            trackEvent('bid_evaluation_completed', {
              bid_id: bid.id,
              result: result.matching?.recommendation || 'N/A',
              score: result.matching?.overall_score,
            });
            pushText('분석이 완료되었습니다! 결과에 대해 자유롭게 질문해주세요. 상단의 버튼으로 추가 분석이나 회사 문서 추가가 가능합니다.');
            setPhase('doc_chat');
            updateConv({ title: bid.title || result.analysis?.title || '공고 분석' });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';

            // 첨부파일 자동 다운로드 실패 → 수동 업로드 폴백
            let isAttachmentUnavailable = false;
            try {
              const parsed = JSON.parse(msg);
              if (parsed.code === 'attachment_unavailable') isAttachmentUnavailable = true;
            } catch { /* not JSON */ }

            if (isAttachmentUnavailable) {
              const bidUrl = bid.url || `https://www.g2b.go.kr/link/PNPE027_01/single/?bidPbancNo=${bid.id}&bidPbancOrd=${bid.bidNtceOrd || '000'}`;
              pushText(
                `공고 첨부파일을 자동으로 가져올 수 없습니다.\n\n` +
                `**나라장터에서 직접 다운로드** 후 아래에서 업로드해주세요.\n` +
                `(나라장터 로그인 필요)\n\n` +
                `[나라장터에서 공고 보기](${bidUrl})`,
              );
              setPhase('doc_upload_target');
              push({
                id: msgId(),
                role: 'bot',
                type: 'file_upload',
                timestamp: Date.now(),
                text: '다운로드한 공고 문서를 여기에 업로드해주세요.',
                accept: UPLOAD_ACCEPT,
                multiple: true,
              } as FileUploadMessage);
            } else {
              pushStatus('error', `공고 분석 실패: ${msg}`, 'bid_analyze');
              setPhase('bid_search_results');
            }
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'bid_selected': {
          const { bidIds, messageId } = action;
          updateConv({ selectedBidIds: bidIds });

          // 회사 문서 미등록 시 안내
          if (!conversation.sessionId || !conversation.companyChunks || conversation.companyChunks <= 0) {
            pushText('일괄 평가를 하려면 먼저 회사 문서를 등록해야 합니다.');
            updateConv({ _prevPhase: conversation.phase });
            setPhase('doc_upload_company');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '회사 문서를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
            break;
          }

          trackEvent('bid_evaluation_started', { bid_count: bidIds.length });
          setProcessing(true);
          setPhase('bid_eval_running');
          pushStatus('loading', `${bidIds.length}건의 공고를 평가하고 있어요...`);

          try {
            const result = await api.evaluateBatch(conversation.sessionId, bidIds);
            removeLastStatus();

            // 성공 후에만 selectedIds 설정 (에러 시 버튼 유지)
            updateMsg(messageId, { selectedIds: bidIds } as Partial<BidCardListMessage>);

            pushText(`${result.jobsCreated}건의 평가가 완료되었습니다.`);

            for (const job of result.jobs) {
              trackEvent('bid_evaluation_completed', {
                bid_id: job.bidNoticeId,
                result: job.isEligible === true ? 'GO' : job.isEligible === false ? 'NO-GO' : 'PENDING',
              });
              push({
                id: msgId(),
                role: 'bot',
                type: 'text',
                timestamp: Date.now(),
                text: `**${job.bidNotice.title}**\n${job.isEligible === true ? 'GO' : job.isEligible === false ? 'NO-GO' : '대기'} — ${job.evaluationReason}${job.actionPlan ? `\n\n준비 사항: ${job.actionPlan}` : ''}`,
              } as TextChatMessage);
            }
            setPhase('bid_eval_results');
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `평가에 실패했어요: ${msg}`, 'bid_eval');
            setPhase('bid_search_results');
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'reference_clicked': {
          trackEvent('reference_clicked', { page_number: action.page, document_name: conversation?.uploadedFileName });
          const refPanel = contextPanelRef.current;
          const currentUrl = conversation?.uploadedFileUrl ||
            (refPanel.type === 'pdf' ? refPanel.blobUrl : '') ||
            (refPanel.type === 'documents' ? refPanel.tabs[0]?.url : '');

          if (!currentUrl) break;

          // If we have a documents panel, update the active tab's page/highlight
          if (refPanel.type === 'documents') {
            const updatedTabs = refPanel.tabs.map((tab, i) =>
              i === 0 ? { ...tab, page: action.page, highlightText: action.text } : tab,
            );
            dispatch({
              type: 'SET_CONTEXT_PANEL',
              content: { type: 'documents', tabs: updatedTabs, activeTabIndex: 0 },
            });
          } else {
            dispatch({
              type: 'SET_CONTEXT_PANEL',
              content: {
                type: 'pdf',
                blobUrl: currentUrl,
                page: action.page,
                highlightText: action.text,
              },
            });
          }
          break;
        }

        case 'retry_action': {
          // Re-push the appropriate starting message based on retry action
          if (action.action === 'upload_company') {
            setPhase('doc_upload_company');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '회사 문서를 다시 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.action === 'analyze') {
            setPhase('doc_upload_target');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '분석할 문서를 다시 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.action === 'bid_search') {
            setPhase('bid_search_input');
            push({
              id: msgId(),
              role: 'bot',
              type: 'inline_form',
              timestamp: Date.now(),
              text: '검색 조건을 다시 입력해주세요.',
              fields: buildSearchFormFields(),
              submitLabel: '검색',
            } as InlineFormMessage);
          } else if (action.action === 'bid_analyze') {
            pushText('다시 시도하려면 공고 목록에서 [분석하기] 버튼을 눌러주세요.');
            setPhase('bid_search_results');
          }
          break;
        }

        case 'header_upload_target': {
          setPhase('doc_upload_target');
          push({
            id: msgId(),
            role: 'bot',
            type: 'file_upload',
            timestamp: Date.now(),
            text: '분석할 문서(RFP/입찰공고)를 업로드해주세요.',
            accept: UPLOAD_ACCEPT,
            multiple: true,
          } as FileUploadMessage);
          break;
        }

        case 'header_add_company': {
          const prevPhase = conversation.phase;
          setPhase('doc_upload_company');
          push({
            id: msgId(),
            role: 'bot',
            type: 'file_upload',
            timestamp: Date.now(),
            text: '추가할 회사 문서를 업로드해주세요.',
            accept: UPLOAD_ACCEPT,
            multiple: true,
          } as FileUploadMessage);
          // 회사 문서 업로드 후 이전 phase로 복귀하기 위해 저장
          updateConv({ _prevPhase: prevPhase });
          break;
        }

        case 'welcome_action': {
          const welcomeLabel: Record<string, string> = {
            doc_analysis: '일반 문서 분석',
            bid_search: '공고 검색/분석',
            setup_alert: '공고 알림 설정',
            company_onboarding: '회사 역량 DB 구축',
          };
          push({
            id: msgId(),
            role: 'user',
            type: 'text',
            timestamp: Date.now(),
            text: welcomeLabel[action.value] || action.value,
          } as TextChatMessage);
          // Auto-title from welcome action
          if (conversation.title === 'KiraBot') {
            updateConv({ title: welcomeLabel[action.value] || 'KiraBot' });
          }
          handleFeatureSelection(action.value);
          break;
        }

        case 'generate_proposal_v2': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 문서를 분석해주세요.');
            break;
          }

          const format = action.format || 'docx';
          const formatName = format === 'hwpx' ? 'HWPX' : 'DOCX';
          const companyId = sessionStorage.getItem('kira_company_id') || '_default';

          setProcessing(true);
          pushStatus('loading', `A-lite 제안서(${formatName})를 생성하고 있어요... (약 3~5분 소요)`);

          try {
            const result = await api.generateProposalV2(conversation.sessionId, 50, format, companyId);
            removeLastStatus();

            const sectionList = result.sections.map((s, i) => `${i + 1}. ${s.name}`).join('\n');
            let msg = `제안서 ${formatName}가 생성되었습니다! (${result.generation_time_sec}초)\n\n**섹션 구성:**\n${sectionList}`;
            msg += `\n\n⚠️ **중요**: 서버 재시작 시 파일이 삭제됩니다. 지금 바로 다운로드하세요!`;

            const filename = result.output_filename || result.docx_filename || result.hwpx_filename;
            if (filename) {
              const downloadUrl = api.getProposalDownloadUrl(filename);
              msg += `\n\n[📥 제안서 ${formatName} 다운로드](${downloadUrl})`;
              pushDocHistory('kira_last_proposal', filename, result.sections[0]?.name || filename);
            }
            if (result.quality_issues.length > 0) {
              msg += `\n\n**품질 이슈 ${result.quality_issues.length}건:**\n` +
                result.quality_issues.map(q => `- [${q.severity}] ${q.detail}`).join('\n');
            }
            pushText(msg);
            trackEvent('proposal_v2_generated', { time: result.generation_time_sec, format });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `A-lite 제안서 생성 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'view_checklist': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 공고를 분석해주세요.');
            break;
          }

          // Check if server still has analysis data (may have expired)
          try {
            const sc = await api.checkSession(conversation.sessionId);
            if (!sc.has_analysis) {
              pushStatus('error', '분석 상태가 만료되었습니다. 공고를 다시 분석해주세요.');
              break;
            }
          } catch { /* proceed anyway — server will return 400 if truly gone */ }

          setProcessing(true);
          pushStatus('loading', '제출 체크리스트를 추출하고 있어요...');

          try {
            const result = await api.getChecklist(conversation.sessionId);
            removeLastStatus();

            push({
              id: msgId(),
              role: 'bot',
              type: 'checklist',
              timestamp: Date.now(),
              items: result.items,
              total: result.total,
              mandatory_count: result.mandatory_count,
            } as ChecklistChatMessage);
            trackEvent('checklist_viewed');
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `체크리스트 추출 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'generate_wbs': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 문서를 분석해주세요.');
            break;
          }

          try {
            const sc = await api.checkSession(conversation.sessionId);
            if (!sc.has_analysis) {
              pushStatus('error', '분석 상태가 만료되었습니다. 공고를 다시 분석해주세요.');
              break;
            }
          } catch { /* proceed */ }

          setProcessing(true);
          pushStatus('loading', '수행계획서/WBS를 생성하고 있어요... (약 2~3분 소요)');

          try {
            const usePack = localStorage.getItem('kira_use_pack') === 'true';
            const companyId = sessionStorage.getItem('kira_company_id') || '_default';
            const result = await api.generateWbs(conversation.sessionId, undefined, usePack, companyId);
            removeLastStatus();

            let msg = `수행계획서/WBS가 생성되었습니다! (${result.generation_time_sec}초)\n\n`;
            msg += `**총 ${result.total_months}개월, ${result.tasks_count}개 태스크**\n\n`;
            msg += `⚠️ **중요**: 서버 재시작 시 파일이 삭제됩니다. 지금 바로 다운로드하세요!\n\n`;
            if (result.xlsx_filename) {
              const url = api.getFileDownloadUrl(result.xlsx_filename);
              msg += `[📊 WBS Excel 다운로드](${url})\n\n`;
            }
            if (result.gantt_filename) {
              const url = api.getFileDownloadUrl(result.gantt_filename);
              msg += `[📈 간트차트 다운로드](${url})\n\n`;
            }
            if (result.docx_filename) {
              const url = api.getFileDownloadUrl(result.docx_filename);
              msg += `[📄 수행계획서 DOCX 다운로드](${url})`;
            }
            pushText(msg);
            // Save WBS result to localStorage for DocumentWorkspace WBS tab
            pushDocHistory('kira_last_wbs', result, conversation.title || 'WBS');
            trackEvent('wbs_generated', { time: result.generation_time_sec });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `수행계획서/WBS 생성 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'generate_ppt': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 문서를 분석해주세요.');
            break;
          }

          try {
            const sc = await api.checkSession(conversation.sessionId);
            if (!sc.has_analysis) {
              pushStatus('error', '분석 상태가 만료되었습니다. 공고를 다시 분석해주세요.');
              break;
            }
          } catch { /* proceed */ }

          setProcessing(true);
          pushStatus('loading', 'PPT 발표자료를 생성하고 있어요... (약 3~5분 소요)');
          const companyId = sessionStorage.getItem('kira_company_id') || '_default';

          try {
            const result = await api.generatePpt(conversation.sessionId, 30, 10, companyId);
            removeLastStatus();

            let msg = `PPT 발표자료가 생성되었습니다! (${result.generation_time_sec}초)\n\n`;
            msg += `**${result.slide_count}장, 발표시간 ${result.total_duration_min}분**\n\n`;
            msg += `⚠️ **중요**: 서버 재시작 시 파일이 삭제됩니다. 지금 바로 다운로드하세요!\n\n`;
            if (result.pptx_filename) {
              const url = api.getFileDownloadUrl(result.pptx_filename);
              msg += `[🎯 PPT 다운로드](${url})\n\n`;
            }
            if (result.qna_pairs.length > 0) {
              msg += `**예상질문 ${result.qna_pairs.length}개:**\n`;
              result.qna_pairs.forEach((q, i) => {
                msg += `\n**Q${i + 1}.** ${q.question}\n**A${i + 1}.** ${q.answer}\n`;
              });
            }
            pushText(msg);
            // Save PPT result to localStorage for DocumentWorkspace PPT tab
            pushDocHistory('kira_last_ppt', result, conversation.title || 'PPT');
            trackEvent('ppt_generated', { time: result.generation_time_sec });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `PPT 발표자료 생성 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'generate_track_record': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 문서를 분석해주세요.');
            break;
          }

          try {
            const sc = await api.checkSession(conversation.sessionId);
            if (!sc.has_analysis) {
              pushStatus('error', '분석 상태가 만료되었습니다. 공고를 다시 분석해주세요.');
              break;
            }
          } catch { /* proceed */ }

          setProcessing(true);
          pushStatus('loading', '실적/경력 기술서를 생성하고 있어요... (약 2~3분 소요)');
          const companyId = sessionStorage.getItem('kira_company_id') || '_default';

          try {
            const result = await api.generateTrackRecord(conversation.sessionId, companyId);
            removeLastStatus();

            // Save to localStorage for DocumentWorkspace track_record tab
            pushDocHistory('kira_last_track_record', result, conversation.title || '실적기술서');

            let msg = `실적/경력 기술서가 생성되었습니다! (${result.generation_time_sec}초)\n\n`;
            msg += `**실적 ${result.track_record_count}건, 인력 ${result.personnel_count}명**\n\n`;
            msg += `⚠️ **중요**: 서버 재시작 시 파일이 삭제됩니다. 지금 바로 다운로드하세요!\n\n`;
            if (result.docx_filename) {
              const url = api.getFileDownloadUrl(result.docx_filename);
              msg += `[📄 실적/경력 기술서 DOCX 다운로드](${url})`;
            }
            if (!result.docx_filename && result.track_record_count === 0) {
              msg += '\n\n회사 DB에 실적/인력 정보가 없습니다. 먼저 회사 정보를 등록해주세요.';
            }
            pushText(msg);
            trackEvent('track_record_generated', { time: result.generation_time_sec });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `실적/경력 기술서 생성 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'delete_company_doc': {
          const { sourceFile } = action;
          const sid = conversation.sessionId;
          if (!sid) break;

          setProcessing(true);
          try {
            const result = await api.deleteSessionCompanyDocument(sid, sourceFile);
            // 문서 목록 갱신
            const docs = conversation.companyDocuments?.filter(d => d.source_file !== sourceFile) || [];
            const urls = conversation.companyDocUrls?.filter(d => !d.name.includes(sourceFile)) || [];
            updateConv({
              companyChunks: result.remaining_chunks,
              companyDocuments: docs,
              companyDocUrls: urls,
            });
            pushText(`"${sourceFile}" 문서가 삭제되었습니다. (남은 청크: ${result.remaining_chunks})`);

            // 분석 결과 있으면 자동 rematch
            if (result.remaining_chunks > 0 && conversation.phase === 'doc_chat') {
              pushStatus('loading', '삭제 후 자격 요건을 재평가하고 있어요...');
              try {
                const rematchResult = await api.rematchWithCompanyDocs(sid);
                removeLastStatus();
                push({
                  id: msgId(),
                  role: 'bot',
                  type: 'analysis_result',
                  timestamp: Date.now(),
                  analysis: rematchResult,
                  opinionMode: conversation.opinionMode,
                } as AnalysisResultMessage);
              } catch {
                removeLastStatus();
                pushText('재평가 중 오류가 발생했습니다.');
              }
            }
          } catch (err) {
            const msg = err instanceof Error ? err.message : '삭제 실패';
            pushStatus('error', msg);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'undo_company_upload': {
          const { sourceFiles } = action;
          const sid = conversation.sessionId;
          if (!sid) break;

          setProcessing(true);
          for (const sf of sourceFiles) {
            try {
              await api.deleteSessionCompanyDocument(sid, sf);
            } catch { /* 일부 파일 삭제 실패는 허용 */ }
          }
          // 목록 새로 가져오기
          try {
            const listResult = await api.listCompanyDocuments(sid);
            updateConv({
              companyChunks: listResult.total_chunks,
              companyDocuments: listResult.documents,
              _justUploadedFiles: undefined,
            });
            pushText('업로드가 취소되었습니다.');
          } catch {
            pushText('업로드 취소 중 일부 오류가 발생했습니다.');
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'ask_about_doc': {
          updateConv({ activeDocFilter: [action.sourceFile] });
          break;
        }
      }
    },
    [conversationId, conversation, push, pushText, pushStatus, removeLastStatus, updateMsg, updateConv, setPhase, setProcessing, dispatch, handleFeatureSelection],
  );

  return {
    startNewConversation,
    handleUserText,
    handleAction,
    isProcessing: state.isProcessing,
  };
}
