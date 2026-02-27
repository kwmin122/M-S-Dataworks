import { useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useChatContext, createNewConversation } from '../context/ChatContext';
import { useActiveConversation } from './useActiveConversation';
import * as api from '../services/kiraApiService';
import { trackEvent } from '../utils/analytics';
import { REGIONS } from '../constants/filters';
import type {
  ChatMessage,
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
    (text: string, references?: { page: number; text: string }[]) => {
      push({
        id: msgId(),
        role: 'bot',
        type: 'text',
        timestamp: Date.now(),
        text,
        references,
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
    async (text: string, _sourceFiles?: string[]) => {
      if (!conversationId || !conversation) return;

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
          const res = await api.chatWithReferences(conversation.sessionId, text);
          removeLastStatus();
          pushText(res.answer, res.references);
          if (res.references?.length) {
            const currentUrl = conversation?.uploadedFileUrl ||
              (state.contextPanel.type === 'pdf' ? state.contextPanel.blobUrl : '') ||
              (state.contextPanel.type === 'documents' ? state.contextPanel.tabs[0]?.url : '');

            if (state.contextPanel.type === 'documents') {
              const updatedTabs = state.contextPanel.tabs.map((tab, i) =>
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

      // 일반 챗봇 모드: AI 대화
      if (conversation.phase === 'free_chat' || conversation.phase === 'greeting') {
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
    [conversationId, conversation, push, pushText, pushStatus, removeLastStatus, setProcessing, setPhase, updateConv, dispatch, state.contextPanel],
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
            multiple: false,
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
        navigate('/settings/alerts');
      }
    },
    [conversationId, conversation, push, pushText, setPhase, navigate],
  );

  // ── Handle message actions (FSM transitions) ──

  const handleAction = useCallback(
    async (action: MessageAction) => {
      if (!conversationId || !conversation) return;

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
            skip_to_target: '바로 문서 분석',
          };
          const label = labelMap[action.value] || action.value;
          push({
            id: msgId(),
            role: 'user',
            type: 'text',
            timestamp: Date.now(),
            text: label,
          } as TextChatMessage);

          if (action.value === 'doc_analysis' || action.value === 'bid_search' || action.value === 'setup_alert') {
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
              multiple: false,
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
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '회사 문서를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: true,
            } as FileUploadMessage);
          } else if (action.value === 'skip_to_target') {
            setPhase('doc_upload_target');
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '분석할 문서(RFP/입찰공고)를 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: false,
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
              // Create session if needed
              let sid = conversation.sessionId;
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
                if ((prevPhase === 'doc_chat' || prevPhase === 'bid_search_results' || prevPhase === 'bid_eval_results') && conversation.sessionId) {
                  pushStatus('loading', '회사 역량과 공고 요건을 비교 분석하고 있어요...');
                  try {
                    const rematchResult = await api.rematchWithCompanyDocs(conversation.sessionId);
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
                  multiple: false,
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
            trackEvent('document_uploaded', { doc_type: 'analysis', file_type: files[0]?.name.split('.').pop() });
            setProcessing(true);
            setPhase('doc_analyzing');
            pushStatus('loading', '문서를 분석하고 있어요. 잠시만 기다려주세요...');

            try {
              let sid = conversation.sessionId;
              if (!sid) {
                sid = await api.createSession();
                updateConv({ sessionId: sid });
              }

              const result = await api.analyzeDocument(sid, files[0]);
              removeLastStatus();

              // Build document tabs for context panel
              const fileName = files[0].name;
              let analysisUrl: string | null = null;
              if (result.fileUrl) {
                analysisUrl = `${api.getApiBaseUrl()}${result.fileUrl}`;
              } else if (files[0].type.includes('pdf')) {
                analysisUrl = URL.createObjectURL(files[0]);
              }

              if (analysisUrl) {
                updateConv({ uploadedFileUrl: analysisUrl, uploadedFileName: fileName });
                const companyDocs = conversation.companyDocUrls || [];
                const tabs = buildDocumentTabs({ url: analysisUrl, fileName }, companyDocs);
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

              trackEvent('document_analyzed', { doc_type: 'analysis', analysis_type: result.analysis?.document_type });
              if (conversation.companyProfile?.companyName) {
                pushText(`🏢 ${conversation.companyProfile.companyName} 정보와 함께 비교 분석이 완료되었습니다! 결과에 대해 자유롭게 질문해주세요.`);
              } else {
                pushText('📄 문서 분석이 완료되었습니다! 결과에 대해 자유롭게 질문해주세요. 💡 설정 > 회사 정보를 등록하면 맞춤 비교 분석이 가능합니다.');
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

          // 세션 없으면 생성
          let sid = conversation.sessionId;
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
                multiple: false,
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
          const currentUrl = conversation?.uploadedFileUrl ||
            (state.contextPanel.type === 'pdf' ? state.contextPanel.blobUrl : '') ||
            (state.contextPanel.type === 'documents' ? state.contextPanel.tabs[0]?.url : '');

          // If we have a documents panel, update the active tab's page/highlight
          if (state.contextPanel.type === 'documents') {
            const updatedTabs = state.contextPanel.tabs.map((tab, i) =>
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
            push({
              id: msgId(),
              role: 'bot',
              type: 'file_upload',
              timestamp: Date.now(),
              text: '분석할 문서를 다시 업로드해주세요.',
              accept: UPLOAD_ACCEPT,
              multiple: false,
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

        case 'open_bid_detail': {
          dispatch({
            type: 'SET_CONTEXT_PANEL',
            content: { type: 'bid_detail', bid: action.bid },
          });
          break;
        }

        case 'open_proposal': {
          dispatch({
            type: 'SET_CONTEXT_PANEL',
            content: { type: 'proposal', sections: action.sections, bidNoticeId: action.bidNoticeId },
          });
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
            multiple: false,
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

        case 'generate_proposal': {
          if (!conversation.sessionId) {
            pushStatus('error', '세션이 없습니다. 먼저 문서를 분석해주세요.');
            break;
          }

          setProcessing(true);
          pushStatus('loading', '제안서 초안을 생성하고 있어요...');

          try {
            const result = await api.generateProposalDraft(conversation.sessionId, action.bidNoticeId);
            removeLastStatus();

            // Show proposal in context panel
            dispatch({
              type: 'SET_CONTEXT_PANEL',
              content: { type: 'proposal', sections: result.sections, bidNoticeId: action.bidNoticeId },
            });

            pushText(`"${action.bidTitle}" 공고에 대한 제안서 초안이 생성되었습니다. 오른쪽 패널에서 내용을 확인하고 수정하세요.`);
            trackEvent('proposal_generated', { bid_id: action.bidNoticeId });
          } catch (error) {
            removeLastStatus();
            const msg = error instanceof Error ? error.message : '알 수 없는 오류';
            pushStatus('error', `제안서 생성 실패: ${msg}`);
          } finally {
            setProcessing(false);
          }
          break;
        }

        case 'delete_company_doc': {
          const { sourceFile } = action;
          const sid = conversation.sessionId;
          if (!sid) break;

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
              }
            }
          } catch (err) {
            const msg = err instanceof Error ? err.message : '삭제 실패';
            pushStatus('error', msg);
          }
          break;
        }

        case 'undo_company_upload': {
          const { sourceFiles } = action;
          const sid = conversation.sessionId;
          if (!sid) break;

          for (const sf of sourceFiles) {
            try {
              await api.deleteSessionCompanyDocument(sid, sf);
            } catch { /* 일부 실패 무시 */ }
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
          } catch { /* ignore */ }
          break;
        }

        case 'go_back': {
          const phase = conversation.phase;
          if (phase === 'doc_upload_target') {
            setPhase('doc_upload_company');
            pushText('회사 문서 업로드 단계로 돌아왔습니다.');
          } else if (phase === 'doc_upload_company') {
            setPhase('greeting');
          }
          break;
        }
      }
    },
    [conversationId, conversation, state.contextPanel, push, pushText, pushStatus, removeLastStatus, updateMsg, updateConv, setPhase, setProcessing, dispatch, handleFeatureSelection],
  );

  return {
    startNewConversation,
    handleUserText,
    handleAction,
    isProcessing: state.isProcessing,
  };
}
