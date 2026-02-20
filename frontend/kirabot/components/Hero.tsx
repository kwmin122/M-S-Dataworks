import React from 'react';
import Button from './Button';

interface HeroProps {
  onStart: () => void;
}

const Hero: React.FC<HeroProps> = ({ onStart }) => {
  return (
    <section className="relative w-full overflow-hidden bg-slate-50 lg:h-screen min-h-[800px] flex flex-col justify-center">
      
      {/* 3D Background Layer */}
      <div className="absolute inset-0 w-full h-full z-0">
         <iframe 
            src='https://my.spline.design/interactiveaiwebsite-WIBfsJZbIYpUeijSVLawHWPr/' 
            frameBorder='0' 
            width='100%' 
            height='100%'
            className="w-full h-full lg:scale-105 lg:translate-x-24 transition-transform duration-1000" 
            title="Inference Search 3D"
        ></iframe>
      </div>

      {/* Gradient Overlay */}
      <div className="absolute inset-0 bg-gradient-to-r from-slate-50 via-slate-50/95 to-transparent pointer-events-none lg:w-[65%] z-0"></div>
      
      {/* Content Layer */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full pointer-events-none h-full flex flex-col justify-center">
          
          <div className="max-w-4xl pt-20 lg:pt-0 pointer-events-auto">
            
            <h1 className="text-5xl sm:text-7xl font-extrabold tracking-tight text-slate-900 font-sans mb-6 leading-[1.15]">
              복잡한 RFx 분석,<br />
              <span className="block sm:whitespace-nowrap bg-gradient-to-r from-[#1a4df5] to-[#5e94ff] bg-clip-text text-transparent">
                KiraBot으로 빠르고 정확하게.
              </span>
            </h1>
            
            <p className="mt-6 text-xl text-slate-600 leading-relaxed max-w-xl font-sans font-medium">
              회사 문서와 분석 문서를 업로드하면 요건 매칭, GAP 분석, 근거 기반 의견까지 한 번에 제공합니다.
              입찰 공고부터 제안요청서까지 페이지 이동 없이 실무 판단을 끝내세요.
            </p>
            
            <div className="mt-10 flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <div className="flex flex-col gap-2 w-full sm:w-auto">
                <Button onClick={onStart} size="lg" className="rounded-full px-10 h-14 text-lg font-bold shadow-xl shadow-primary-900/10 w-full">
                  Kira bot 실행하기
                </Button>
              </div>
            </div>
          </div>
      </div>
    </section>
  );
};

export default Hero;
