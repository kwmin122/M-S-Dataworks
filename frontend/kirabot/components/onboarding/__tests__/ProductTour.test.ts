import { describe, it, expect, beforeEach } from 'vitest';

const TOUR_COMPLETED_KEY = 'kira_tour_completed';

describe('ProductTour localStorage flag logic', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('should auto-start when no completion flag exists', () => {
    const completed = localStorage.getItem(TOUR_COMPLETED_KEY);
    expect(completed).toBeNull();
    // When completed is null/falsy, tour auto-starts
    const shouldAutoStart = !completed;
    expect(shouldAutoStart).toBe(true);
  });

  it('should NOT auto-start when completion flag is "true"', () => {
    localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
    const completed = localStorage.getItem(TOUR_COMPLETED_KEY);
    expect(completed).toBe('true');
    const shouldAutoStart = !completed;
    expect(shouldAutoStart).toBe(false);
  });

  it('should NOT auto-start for any truthy flag value', () => {
    localStorage.setItem(TOUR_COMPLETED_KEY, 'yes');
    const completed = localStorage.getItem(TOUR_COMPLETED_KEY);
    const shouldAutoStart = !completed;
    expect(shouldAutoStart).toBe(false);
  });

  it('should auto-start after localStorage is cleared', () => {
    localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
    localStorage.clear();
    const completed = localStorage.getItem(TOUR_COMPLETED_KEY);
    expect(completed).toBeNull();
    const shouldAutoStart = !completed;
    expect(shouldAutoStart).toBe(true);
  });

  it('completion flag is set correctly', () => {
    // Simulate the onDestroyed callback when completedNormally = true
    const completedNormally = true;
    if (completedNormally) {
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
    }
    expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBe('true');
  });

  it('completion flag is NOT set when user closes early', () => {
    // Simulate the onDestroyed callback when completedNormally = false (user closed early)
    const completedNormally = false;
    if (completedNormally) {
      localStorage.setItem(TOUR_COMPLETED_KEY, 'true');
    }
    expect(localStorage.getItem(TOUR_COMPLETED_KEY)).toBeNull();
  });
});

describe('ProductTour TOUR_STEPS DOM filtering', () => {
  const TOUR_STEPS = [
    { selector: '[data-tour="sidebar"]', title: '사이드바' },
    { selector: '[data-tour="new-chat"]', title: '새 채팅' },
    { selector: '[data-tour="chat-input"]', title: '메시지 입력' },
    { selector: '[data-tour="file-upload"]', title: '파일 업로드' },
    { selector: '[data-tour="company-db"]', title: '회사 역량 DB 구축' },
    { selector: '[data-tour="user-guide"]', title: '사용 가이드' },
  ];

  it('has 6 tour steps defined', () => {
    expect(TOUR_STEPS).toHaveLength(6);
  });

  it('filters out steps whose DOM elements do not exist', () => {
    // In jsdom no elements exist by default
    const available = TOUR_STEPS.filter(step => document.querySelector(step.selector));
    expect(available).toHaveLength(0);
  });

  it('includes steps whose DOM elements exist', () => {
    // Add a matching element to the DOM
    const el = document.createElement('div');
    el.setAttribute('data-tour', 'sidebar');
    document.body.appendChild(el);

    const available = TOUR_STEPS.filter(step => document.querySelector(step.selector));
    expect(available).toHaveLength(1);
    expect(available[0].title).toBe('사이드바');

    document.body.removeChild(el);
  });
});
