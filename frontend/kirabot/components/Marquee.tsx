import React from 'react';

interface MarqueeProps {
  text: string;
  bg?: string;
  textColor?: string;
}

const Marquee: React.FC<MarqueeProps> = ({
  text,
  bg = 'bg-white',
  textColor = 'text-black',
}) => {
  return (
    <div className={`${bg} overflow-hidden py-2.5 border-y border-black/5`} aria-hidden="true">
      <div className="flex">
        <div className="animate-marquee whitespace-nowrap flex gap-8">
          {Array.from({ length: 10 }).map((_, i) => (
            <span
              key={i}
              className={`${textColor} text-xs font-semibold tracking-[0.15em] uppercase`}
            >
              {text}
            </span>
          ))}
        </div>
        <div className="animate-marquee whitespace-nowrap flex gap-8">
          {Array.from({ length: 10 }).map((_, i) => (
            <span
              key={`dup-${i}`}
              className={`${textColor} text-xs font-semibold tracking-[0.15em] uppercase`}
            >
              {text}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Marquee;
