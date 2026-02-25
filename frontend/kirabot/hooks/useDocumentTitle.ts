import { useEffect } from 'react';

export function useDocumentTitle(title: string) {
  useEffect(() => {
    const suffix = 'Kira';
    document.title = title ? `${title} — ${suffix}` : suffix;
    return () => { document.title = suffix; };
  }, [title]);
}
