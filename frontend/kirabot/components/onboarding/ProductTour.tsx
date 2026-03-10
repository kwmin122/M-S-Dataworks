import React, { useEffect, useRef, useCallback } from 'react';
import { driver, type Driver } from 'driver.js';
import 'driver.js/dist/driver.css';

const TOUR_COMPLETED_KEY = 'kira_tour_completed';

/** Start (or restart) the product tour imperatively. */
export function startProductTour() {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('kira:start-tour'));
}

const TOUR_STEPS = [
  {
    selector: '[data-tour="sidebar"]',
    title: '사이드바',
    description: '대화 목록이 여기 있어요. 새 채팅을 시작하거나 이전 대화를 이어갈 수 있습니다.',
    side: 'right' as const,
    align: 'start' as const,
  },
  {
    selector: '[data-tour="new-chat"]',
    title: '새 채팅',
    description: '새로운 대화를 시작할 수 있어요. 공고를 검색하거나 문서를 분석해보세요.',
    side: 'right' as const,
    align: 'start' as const,
  },
  {
    selector: '[data-tour="chat-input"]',
    title: '메시지 입력',
    description: '여기에 검색어나 질문을 입력하세요. 공고 키워드, 분석 요청, 자유 질문 모두 가능해요.',
    side: 'top' as const,
    align: 'center' as const,
  },
  {
    selector: '[data-tour="file-upload"]',
    title: '파일 업로드',
    description: 'PDF, HWP, DOCX 등 문서를 업로드하여 분석할 수 있어요. 회사 문서와 공고 문서를 구분해서 올려보세요.',
    side: 'top' as const,
    align: 'end' as const,
  },
  {
    selector: '[data-tour="company-db"]',
    title: '회사 역량 DB 구축',
    description: '회사 문서를 등록하면 맞춤형 GO/NO-GO 분석과 제안서가 생성돼요. 소개서, 실적표 등을 등록해보세요.',
    side: 'top' as const,
    align: 'center' as const,
  },
  {
    selector: '[data-tour="user-guide"]',
    title: '사용 가이드',
    description: '사용법이 궁금하면 여기를 클릭하세요. 단계별 안내를 확인할 수 있습니다.',
    side: 'right' as const,
    align: 'start' as const,
  },
];

const ProductTour: React.FC = () => {
  const driverRef = useRef<Driver | null>(null);
  const completedNormallyRef = useRef(false);

  const createDriver = useCallback(() => {
    completedNormallyRef.current = false;

    // Filter steps to only include elements present in the DOM
    const availableSteps = TOUR_STEPS
      .filter(step => document.querySelector(step.selector))
      .map(step => ({
        element: step.selector,
        popover: {
          title: step.title,
          description: step.description,
          side: step.side,
          align: step.align,
        },
      }));

    if (availableSteps.length === 0) return null;

    return driver({
      showProgress: true,
      animate: true,
      allowClose: true,
      overlayColor: 'rgba(0,0,0,0.6)',
      stagePadding: 8,
      stageRadius: 12,
      popoverClass: 'kira-tour-popover',
      nextBtnText: '다음',
      prevBtnText: '이전',
      doneBtnText: '시작하기',
      progressText: '{{current}} / {{total}}',
      onDestroyStarted: () => {
        // Mark as normally completed only if we're on the last step
        const d = driverRef.current;
        if (d && !d.hasNextStep()) {
          completedNormallyRef.current = true;
        }
        d?.destroy();
      },
      onDestroyed: () => {
        // Only mark tour as completed if user finished all steps
        if (completedNormallyRef.current) {
          localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
        }
      },
      steps: availableSteps,
    });
  }, []);

  const runTour = useCallback(() => {
    if (typeof window === 'undefined') return;
    // Destroy any existing instance first
    if (driverRef.current) {
      driverRef.current.destroy();
    }
    const d = createDriver();
    if (!d) return; // No tour steps available
    driverRef.current = d;
    // Small delay to ensure DOM elements have data-tour attributes
    requestAnimationFrame(() => {
      d.drive();
    });
  }, [createDriver]);

  // Auto-start for first-time users
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const completed = localStorage.getItem(TOUR_COMPLETED_KEY);
    if (completed) return;

    // Wait for the UI to settle after initial render
    const timer = setTimeout(() => {
      runTour();
    }, 800);

    return () => clearTimeout(timer);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Listen for manual restart via custom event
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const handler = () => runTour();
    window.addEventListener('kira:start-tour', handler);
    return () => window.removeEventListener('kira:start-tour', handler);
  }, [runTour]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      driverRef.current?.destroy();
    };
  }, []);

  return null;
};

export default ProductTour;
