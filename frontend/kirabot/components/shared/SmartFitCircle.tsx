import React from 'react';

interface SmartFitCircleProps {
  score: number; // 0-100
  size?: number; // default 80
}

const SmartFitCircle: React.FC<SmartFitCircleProps> = ({ score, size = 80 }) => {
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const getColor = (s: number) => {
    if (s >= 80) return { stroke: '#22c55e', text: 'text-green-600' }; // go
    if (s >= 60) return { stroke: '#f59e0b', text: 'text-amber-600' }; // warn
    return { stroke: '#ef4444', text: 'text-red-600' }; // nogo
  };

  const { stroke, text } = getColor(score);

  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={strokeWidth}
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={stroke}
          strokeWidth={strokeWidth}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          className="transition-all duration-700 ease-out"
        />
      </svg>
      <span className={`absolute text-lg font-bold ${text}`}>{score}</span>
    </div>
  );
};

export default SmartFitCircle;
