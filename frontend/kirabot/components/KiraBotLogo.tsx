import React from 'react';

interface KiraBotLogoProps {
  size?: number;
  className?: string;
}

const KiraBotLogo: React.FC<KiraBotLogoProps> = ({ size = 24, className = '' }) => {
  return (
    <img
      src="/kirabot-logo.svg"
      alt="Kira"
      width={size}
      height={size}
      className={className}
      style={{ objectFit: 'contain' }}
    />
  );
};

export default KiraBotLogo;
