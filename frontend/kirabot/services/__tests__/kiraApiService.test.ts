import { describe, it, expect } from 'vitest';
import { getFileDownloadUrl } from '../kiraApiService';

describe('getFileDownloadUrl', () => {
  it('returns a valid URL for a safe Korean filename', () => {
    const url = getFileDownloadUrl('제안서_v2.docx');
    expect(url).toContain('/api/proposal/download/');
    expect(url).toContain(encodeURIComponent('제안서_v2.docx'));
  });

  it('returns a valid URL for an ASCII filename', () => {
    const url = getFileDownloadUrl('proposal_2026.docx');
    expect(url).toContain('proposal_2026.docx');
  });

  it('throws on empty filename', () => {
    expect(() => getFileDownloadUrl('')).toThrow('잘못된 파일명');
  });

  it('throws on path traversal attempt', () => {
    expect(() => getFileDownloadUrl('../../../etc/passwd')).toThrow('잘못된 파일명');
  });

  it('throws on filename with spaces', () => {
    expect(() => getFileDownloadUrl('my file.docx')).toThrow('잘못된 파일명');
  });

  it('throws on filename with special characters', () => {
    expect(() => getFileDownloadUrl('file<script>.docx')).toThrow('잘못된 파일명');
  });

  it('allows hyphens and dots in filenames', () => {
    const url = getFileDownloadUrl('my-file.v2.docx');
    expect(url).toContain('my-file.v2.docx');
  });

  it('throws on filename with double dots (..)', () => {
    expect(() => getFileDownloadUrl('file..docx')).toThrow('잘못된 파일명');
  });
});
