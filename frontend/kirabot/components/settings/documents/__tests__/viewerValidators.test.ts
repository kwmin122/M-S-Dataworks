import { describe, it, expect } from 'vitest';

// Extract and test the shape validators used by WbsViewer, PptViewer, TrackRecordViewer
// These are the same validation functions defined in the component files

function isValidWbsResponse(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.tasks_count === 'number' && typeof d.total_months === 'number';
}

function isValidPptResponse(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.slide_count === 'number' && typeof d.generation_time_sec === 'number';
}

function isValidTrackRecordResponse(data: unknown): boolean {
  if (!data || typeof data !== 'object') return false;
  const d = data as Record<string, unknown>;
  return typeof d.track_record_count === 'number' && typeof d.personnel_count === 'number';
}

describe('isValidWbsResponse', () => {
  it('accepts valid WBS data', () => {
    expect(isValidWbsResponse({
      tasks_count: 10,
      total_months: 6,
      xlsx_filename: 'wbs.xlsx',
      gantt_filename: 'gantt.png',
      docx_filename: 'plan.docx',
      generation_time_sec: 12.3,
    })).toBe(true);
  });

  it('accepts minimal valid data', () => {
    expect(isValidWbsResponse({ tasks_count: 0, total_months: 0 })).toBe(true);
  });

  it('rejects null', () => {
    expect(isValidWbsResponse(null)).toBe(false);
  });

  it('rejects missing tasks_count', () => {
    expect(isValidWbsResponse({ total_months: 6 })).toBe(false);
  });

  it('rejects missing total_months', () => {
    expect(isValidWbsResponse({ tasks_count: 10 })).toBe(false);
  });

  it('rejects string values for numbers', () => {
    expect(isValidWbsResponse({ tasks_count: '10', total_months: '6' })).toBe(false);
  });
});

describe('isValidPptResponse', () => {
  it('accepts valid PPT data', () => {
    expect(isValidPptResponse({
      slide_count: 15,
      generation_time_sec: 25.4,
      pptx_filename: 'slides.pptx',
      total_duration_min: 30,
      qna_pairs: [],
    })).toBe(true);
  });

  it('accepts minimal valid data', () => {
    expect(isValidPptResponse({ slide_count: 0, generation_time_sec: 0 })).toBe(true);
  });

  it('rejects null', () => {
    expect(isValidPptResponse(null)).toBe(false);
  });

  it('rejects missing slide_count', () => {
    expect(isValidPptResponse({ generation_time_sec: 10 })).toBe(false);
  });

  it('rejects missing generation_time_sec', () => {
    expect(isValidPptResponse({ slide_count: 15 })).toBe(false);
  });

  it('rejects string values', () => {
    expect(isValidPptResponse({ slide_count: '15', generation_time_sec: '10' })).toBe(false);
  });
});

describe('isValidTrackRecordResponse', () => {
  it('accepts valid track record data', () => {
    expect(isValidTrackRecordResponse({
      track_record_count: 5,
      personnel_count: 3,
      docx_filename: 'records.docx',
      generation_time_sec: 8.1,
    })).toBe(true);
  });

  it('accepts minimal valid data', () => {
    expect(isValidTrackRecordResponse({ track_record_count: 0, personnel_count: 0 })).toBe(true);
  });

  it('rejects null', () => {
    expect(isValidTrackRecordResponse(null)).toBe(false);
  });

  it('rejects missing track_record_count', () => {
    expect(isValidTrackRecordResponse({ personnel_count: 3 })).toBe(false);
  });

  it('rejects missing personnel_count', () => {
    expect(isValidTrackRecordResponse({ track_record_count: 5 })).toBe(false);
  });

  it('rejects corrupt data from localStorage', () => {
    // Simulating what happens when localStorage has old/corrupt data
    expect(isValidTrackRecordResponse({ some_old_field: 'value' })).toBe(false);
  });
});

describe('localStorage round-trip with validators', () => {
  it('Execution Plan: stores and retrieves valid data', () => {
    const wbs = { tasks_count: 10, total_months: 6, xlsx_filename: 'test.xlsx', gantt_filename: 'test.png', docx_filename: 'test.docx', generation_time_sec: 5 };
    localStorage.setItem('kira_last_execution_plan', JSON.stringify(wbs));
    const raw = localStorage.getItem('kira_last_execution_plan');
    const parsed = raw ? JSON.parse(raw) : null;
    expect(isValidWbsResponse(parsed)).toBe(true);
  });

  it('Execution Plan: rejects corrupt localStorage data', () => {
    localStorage.setItem('kira_last_execution_plan', 'not-json{');
    let parsed: unknown = null;
    try {
      const raw = localStorage.getItem('kira_last_execution_plan');
      parsed = raw ? JSON.parse(raw) : null;
    } catch {
      parsed = null;
    }
    expect(isValidWbsResponse(parsed)).toBe(false);
  });

  it('Presentation: returns null for empty localStorage', () => {
    const raw = localStorage.getItem('kira_last_presentation');
    expect(raw).toBeNull();
    expect(isValidPptResponse(null)).toBe(false);
  });

  it('TrackRecord: returns null for empty localStorage', () => {
    const raw = localStorage.getItem('kira_last_track_record');
    expect(raw).toBeNull();
    expect(isValidTrackRecordResponse(null)).toBe(false);
  });
});
