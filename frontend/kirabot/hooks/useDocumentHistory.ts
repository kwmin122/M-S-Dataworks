import { useState, useCallback, useEffect } from 'react';

export interface DocumentHistoryEntry<T> {
  id: string;           // unique ID (timestamp-based)
  timestamp: number;    // Date.now() when created
  label: string;        // display label (e.g., bid title, filename)
  data: T;              // the actual response data
}

const MAX_ENTRIES = 10;

/**
 * Generic hook for managing document generation history in sessionStorage.
 *
 * @param storageKey - sessionStorage key (e.g., 'kira_doc_wbs')
 * @param validator - shape validator function (returns true if data is valid T)
 */
export function useDocumentHistory<T>(
  storageKey: string,
  validator: (data: unknown) => data is T,
) {
  const [entries, setEntries] = useState<DocumentHistoryEntry<T>[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  // Load from sessionStorage on mount
  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(storageKey);
      if (raw) {
        const parsed: unknown = JSON.parse(raw);
        if (Array.isArray(parsed)) {
          // New format: array of entries
          const valid = parsed.filter(
            (e): e is DocumentHistoryEntry<T> =>
              e != null &&
              typeof e === 'object' &&
              typeof (e as Record<string, unknown>).id === 'string' &&
              typeof (e as Record<string, unknown>).timestamp === 'number' &&
              typeof (e as Record<string, unknown>).label === 'string' &&
              validator((e as Record<string, unknown>).data),
          );
          setEntries(valid);
          if (valid.length > 0) setSelectedId(valid[0].id);
        } else if (validator(parsed)) {
          // Legacy format: single object — migrate to array
          const entry: DocumentHistoryEntry<T> = {
            id: `legacy_${Date.now()}`,
            timestamp: Date.now(),
            label: '이전 생성물',
            data: parsed,
          };
          setEntries([entry]);
          setSelectedId(entry.id);
          // Save migrated format
          try { sessionStorage.setItem(storageKey, JSON.stringify([entry])); } catch { /* noop */ }
        }
      }
    } catch {
      // corrupt data — ignore
    } finally {
      setLoading(false);
    }
  }, [storageKey, validator]);

  // Push a new entry (prepend, cap at MAX_ENTRIES)
  const push = useCallback((data: T, label: string) => {
    const entry: DocumentHistoryEntry<T> = {
      id: `doc_${Date.now()}`,
      timestamp: Date.now(),
      label,
      data,
    };
    setEntries(prev => {
      const next = [entry, ...prev].slice(0, MAX_ENTRIES);
      try { sessionStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* noop */ }
      return next;
    });
    setSelectedId(entry.id);
    return entry;
  }, [storageKey]);

  // Remove an entry
  const remove = useCallback((id: string) => {
    setEntries(prev => {
      const next = prev.filter(e => e.id !== id);
      try { sessionStorage.setItem(storageKey, JSON.stringify(next)); } catch { /* noop */ }

      // If the removed entry was selected, select the next available
      setSelectedId(prevId => {
        if (prevId === id) {
          return next[0]?.id ?? null;
        }
        return prevId;
      });

      return next;
    });
  }, [storageKey]);

  // Get currently selected entry
  const selected = entries.find(e => e.id === selectedId) ?? entries[0] ?? null;

  return {
    entries,
    selected,
    selectedId,
    setSelectedId,
    push,
    remove,
    loading,
  };
}
