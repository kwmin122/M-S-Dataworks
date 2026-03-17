import React, { useState, useCallback } from 'react';
import Button from './Button';
import { trackEvent } from '../utils/analytics';

interface HeroProps {
  onStart: () => void;
  onStartStudio?: () => void;
  onAlertSetup?: () => void;
}

const SPLINE_URL = 'https://my.spline.design/interactiveaiwebsite-WIBfsJZbIYpUeijSVLawHWPr/';

const Hero: React.FC<HeroProps> = ({ onStart, onStartStudio, onAlertSetup }) => {
  const [splineLoaded, setSplineLoaded] = useState(false);

  const handleIframeLoad = useCallback(() => {
    setSplineLoaded(true);
  }, []);

  return (
    <section className="relative w-full overflow-hidden bg-slate-50 lg:h-screen min-h-[800px] flex flex-col justify-center">

      {/* Animated CSS Fallback — always present behind iframe */}
      <div className="absolute inset-0 w-full h-full z-0 overflow-hidden">
        <div className="hero-mesh absolute inset-0" />
      </div>

      {/* 3D Spline Layer — overlays the CSS fallback when loaded */}
      <div
        className="absolute inset-0 w-full h-full z-0 transition-opacity duration-1000"
        style={{ opacity: splineLoaded ? 1 : 0 }}
      >
        <iframe
          src={SPLINE_URL}
          frameBorder="0"
          width="100%"
          height="100%"
          allow="autoplay; fullscreen; xr-spatial-tracking"
          loading="lazy"
          onLoad={handleIframeLoad}
          className="w-full h-full lg:scale-105 lg:translate-x-24 transition-transform duration-1000"
          title="Inference Search 3D"
        />
      </div>

      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-slate-50 via-slate-50/95 to-transparent pointer-events-none lg:w-[65%] z-0"></div>

      {/* Content Layer */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full pointer-events-none h-full flex flex-col justify-center">

          <div className="max-w-4xl pt-20 lg:pt-0 pointer-events-auto">

            <p className="text-sm font-semibold text-primary-600 tracking-wide mb-4">공공조달 입찰 AI 분석</p>

            <h1 className="text-3xl sm:text-5xl lg:text-7xl font-extrabold tracking-tight text-slate-900 font-sans mb-6 leading-[1.15]">
              100페이지 공고서,<br />
              <span className="block bg-gradient-to-r from-[#1a4df5] to-[#5e94ff] bg-clip-text text-transparent">
                AI가 3분 만에 읽어줍니다.
              </span>
            </h1>

            <p className="mt-6 text-xl text-slate-500 leading-relaxed max-w-lg font-sans">
              공고서를 올리면 자격요건 추출부터 GO/NO-GO 판단까지.<br />
              더 이상 공고서를 직접 읽을 필요가 없습니다.
            </p>

            <div className="mt-10 flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <Button onClick={() => { trackEvent('landing_cta_clicked', { button: 'bid_search' }); onStart(); }} size="lg" className="rounded-full px-10 h-14 text-lg font-bold shadow-xl shadow-primary-900/10">
                공고 탐색하기
              </Button>
              {onStartStudio && (
                <Button onClick={() => { trackEvent('landing_cta_clicked', { button: 'bid_studio' }); onStartStudio(); }} size="lg" variant="secondary" className="rounded-full px-10 h-14 text-lg font-bold border-2 border-slate-300 hover:border-kira-500 shadow-lg">
                  입찰 문서 AI 작성
                </Button>
              )}
            </div>
            {onAlertSetup && (
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => { trackEvent('landing_cta_clicked', { button: 'alert_setup' }); onAlertSetup?.(); }}
                  className="group flex items-center gap-2 text-base font-medium text-slate-500 hover:text-slate-900 transition-colors duration-200"
                >
                  맞춤 공고 알림 설정
                  <span className="inline-block transition-transform duration-200 group-hover:translate-x-1">&rarr;</span>
                </button>
              </div>
            )}
          </div>
      </div>
    </section>
  );
};

export default Hero;
