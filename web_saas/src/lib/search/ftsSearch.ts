export function buildFtsQuery(keywords: string[]): string {
  if (!keywords.length) return '';
  const sanitized = keywords.map((kw) => kw.replace(/['"\\]/g, '').trim()).filter(Boolean);
  return sanitized.join(' | ');
}
