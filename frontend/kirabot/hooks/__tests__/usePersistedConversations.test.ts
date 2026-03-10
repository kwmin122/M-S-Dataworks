import { describe, it, expect } from 'vitest';

// Test the shape validation logic used in usePersistedConversations
// We extract the validation logic to test it in isolation without needing React rendering

function isValidConversation(c: unknown): boolean {
  return (
    c != null &&
    typeof c === 'object' &&
    typeof (c as Record<string, unknown>).id === 'string' &&
    typeof (c as Record<string, unknown>).phase === 'string' &&
    Array.isArray((c as Record<string, unknown>).messages)
  );
}

describe('usePersistedConversations shape validation', () => {
  it('accepts a valid conversation object', () => {
    const valid = { id: 'conv-1', phase: 'greeting', messages: [] };
    expect(isValidConversation(valid)).toBe(true);
  });

  it('accepts a conversation with messages', () => {
    const valid = {
      id: 'conv-2',
      phase: 'doc_chat',
      messages: [{ role: 'user', content: 'hello' }],
    };
    expect(isValidConversation(valid)).toBe(true);
  });

  it('rejects null', () => {
    expect(isValidConversation(null)).toBe(false);
  });

  it('rejects undefined', () => {
    expect(isValidConversation(undefined)).toBe(false);
  });

  it('rejects a string', () => {
    expect(isValidConversation('not-an-object')).toBe(false);
  });

  it('rejects object missing id', () => {
    expect(isValidConversation({ phase: 'greeting', messages: [] })).toBe(false);
  });

  it('rejects object missing phase', () => {
    expect(isValidConversation({ id: '1', messages: [] })).toBe(false);
  });

  it('rejects object missing messages', () => {
    expect(isValidConversation({ id: '1', phase: 'greeting' })).toBe(false);
  });

  it('rejects object with messages as non-array', () => {
    expect(isValidConversation({ id: '1', phase: 'greeting', messages: 'not-array' })).toBe(false);
  });

  it('rejects object with numeric id', () => {
    expect(isValidConversation({ id: 123, phase: 'greeting', messages: [] })).toBe(false);
  });

  it('filters corrupt entries from parsed localStorage data', () => {
    const parsed = [
      { id: 'conv-1', phase: 'greeting', messages: [] },
      null,
      'bad-entry',
      { id: 'conv-2', phase: 'doc_chat', messages: [] },
      { id: 123, phase: 'greeting', messages: [] },
    ];
    const valid = parsed.filter(isValidConversation);
    expect(valid).toHaveLength(2);
    expect((valid[0] as { id: string }).id).toBe('conv-1');
    expect((valid[1] as { id: string }).id).toBe('conv-2');
  });
});
