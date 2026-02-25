/**
 * Initialize GA4 script dynamically from VITE_GA_MEASUREMENT_ID.
 * Call once at app startup (e.g., in index.tsx).
 */
export function initGA4(): void {
  const measurementId = import.meta.env.VITE_GA_MEASUREMENT_ID;
  if (!measurementId) return;

  // gtag.js loader
  const script = document.createElement('script');
  script.async = true;
  script.src = `https://www.googletagmanager.com/gtag/js?id=${measurementId}`;
  document.head.appendChild(script);

  // dataLayer + gtag init
  window.dataLayer = window.dataLayer || [];
  window.gtag = function gtag(...args: unknown[]) {
    window.dataLayer.push(args);
  };
  window.gtag('js', new Date());
  window.gtag('config', measurementId);
}

/**
 * Send a custom event to GA4.
 */
export function trackEvent(eventName: string, params?: Record<string, unknown>): void {
  if (typeof window.gtag === 'function') {
    window.gtag('event', eventName, params);
  }
}

/**
 * Track a page view (virtual navigation in SPA).
 */
export function trackPageView(pagePath: string, pageTitle?: string): void {
  if (typeof window.gtag === 'function') {
    window.gtag('event', 'page_view', {
      page_path: pagePath,
      page_title: pageTitle,
    });
  }
}
