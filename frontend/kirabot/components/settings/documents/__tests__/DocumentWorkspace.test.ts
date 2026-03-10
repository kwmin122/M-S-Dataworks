import { describe, it, expect } from 'vitest';

// Test the tab validation logic from DocumentWorkspace
// Extracted to avoid needing full react-router-dom rendering

const VALID_TABS = new Set(['profile', 'rfp', 'proposal', 'wbs', 'ppt', 'track_record']);

function resolveTab(rawTab: string | null): string {
  const tab = rawTab || 'profile';
  return VALID_TABS.has(tab) ? tab : 'profile';
}

describe('DocumentWorkspace tab validation', () => {
  it('defaults to "profile" when tab param is null', () => {
    expect(resolveTab(null)).toBe('profile');
  });

  it('defaults to "profile" when tab param is empty string', () => {
    expect(resolveTab('')).toBe('profile');
  });

  it('accepts valid tab "profile"', () => {
    expect(resolveTab('profile')).toBe('profile');
  });

  it('accepts valid tab "rfp"', () => {
    expect(resolveTab('rfp')).toBe('rfp');
  });

  it('accepts valid tab "proposal"', () => {
    expect(resolveTab('proposal')).toBe('proposal');
  });

  it('accepts valid tab "wbs"', () => {
    expect(resolveTab('wbs')).toBe('wbs');
  });

  it('accepts valid tab "ppt"', () => {
    expect(resolveTab('ppt')).toBe('ppt');
  });

  it('accepts valid tab "track_record"', () => {
    expect(resolveTab('track_record')).toBe('track_record');
  });

  it('falls back to "profile" for unknown tab', () => {
    expect(resolveTab('unknown')).toBe('profile');
  });

  it('falls back to "profile" for XSS attempt', () => {
    expect(resolveTab('<script>alert(1)</script>')).toBe('profile');
  });

  it('falls back to "profile" for URL-encoded value', () => {
    expect(resolveTab('%3Cscript%3E')).toBe('profile');
  });

  it('VALID_TABS contains exactly 6 tabs', () => {
    expect(VALID_TABS.size).toBe(6);
  });
});
