/**
 * Deterministic alert session ID from user ID.
 * Strips non-URL-safe chars to match backend _sanitize_alert_session_id regex.
 */
export function getAlertSessionId(userId: string): string {
  const safe = userId.replace(/[^a-zA-Z0-9_-]/g, '_').slice(0, 100);
  return `user_${safe}`;
}
