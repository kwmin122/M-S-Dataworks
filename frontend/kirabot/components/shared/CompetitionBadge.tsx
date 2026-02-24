import React from 'react';

interface CompetitionBadgeProps {
  level: 'high' | 'medium' | 'low';
}

const config = {
  high: { label: '경쟁 높음', bg: 'bg-red-100', text: 'text-red-700' },
  medium: { label: '경쟁 보통', bg: 'bg-amber-100', text: 'text-amber-700' },
  low: { label: '경쟁 낮음', bg: 'bg-green-100', text: 'text-green-700' },
};

const CompetitionBadge: React.FC<CompetitionBadgeProps> = ({ level }) => {
  const { label, bg, text } = config[level];
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${bg} ${text}`}>
      {label}
    </span>
  );
};

export default CompetitionBadge;
