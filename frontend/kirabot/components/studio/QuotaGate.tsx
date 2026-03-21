/**
 * QuotaGate — displays a plan upgrade prompt when a 402 quota error occurs.
 *
 * Drop into any stage's error display. Shows only when the error message
 * indicates a quota/upgrade condition; renders nothing otherwise.
 */

interface QuotaGateProps {
  error: string;
}

export default function QuotaGate({ error }: QuotaGateProps) {
  const isQuotaError =
    error.includes('402') ||
    error.includes('업그레이드') ||
    error.includes('초과했습니다') ||
    error.includes('사용할 수 없습니다');

  if (!isQuotaError) return null;

  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-center mb-4">
      <p className="text-sm font-medium text-amber-800">{error}</p>
      <a
        href="/settings/subscription"
        className="text-xs text-kira-600 hover:underline mt-2 inline-block"
      >
        플랜 업그레이드 &rarr;
      </a>
    </div>
  );
}
