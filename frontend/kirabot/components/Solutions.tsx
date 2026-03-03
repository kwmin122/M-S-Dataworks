import React from 'react';

const cards = [
  {
    title: '나라장터 실시간 검색',
    desc: '키워드, 업무구분, 기간, 지역, 금액\n필터로 공고를 실시간 검색합니다.',
    img: 'https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&h=240&fit=crop',
  },
  {
    title: '제안서 자동 생성',
    desc: 'RFP 분석 → 평가항목별 섹션 생성.\n모든것은 원클릭으로.',
    img: 'https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=600&h=240&fit=crop',
  },
  {
    title: '맞춤 공고 알림',
    desc: '관심 분야·지역·금액 조건 설정,\n매칭 공고를 자동으로 알려드립니다.',
    img: 'https://images.unsplash.com/photo-1596526131083-e8c633c948d2?w=600&h=240&fit=crop',
  },
  {
    title: '공고서 자유 질문',
    desc: '업로드한 공고서에 대해 자유롭게\n질문하고 AI가 근거와 함께 답합니다.',
    img: 'https://images.unsplash.com/photo-1488590528505-98d2b5aba04b?w=600&h=240&fit=crop',
  },
];

const Solutions: React.FC = () => {
  return (
    <section id="solutions" className="bg-[#0000FF] relative overflow-hidden">
      <div className="mx-auto max-w-7xl px-6 lg:px-8 py-8 lg:py-0">
        <div className="flex flex-col lg:flex-row items-start gap-8 lg:gap-12">
          {/* Cards Grid — 2x2 */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 lg:py-8 flex-1 max-w-[660px]">
            {cards.map((card) => (
              <div
                key={card.title}
                className="bg-white rounded overflow-hidden"
              >
                <div className="p-4 pb-2">
                  <h3 className="text-sm font-bold text-black mb-1">{card.title}</h3>
                  <p className="text-[10px] text-gray-600 leading-relaxed whitespace-pre-line">
                    {card.desc}
                  </p>
                </div>
                <div className="px-4 pb-4">
                  <img
                    src={card.img}
                    alt={card.title}
                    className="w-full h-[100px] object-cover rounded-sm"
                    loading="lazy"
                  />
                </div>
              </div>
            ))}
          </div>

          {/* Right — Title + KIRA */}
          <div className="hidden lg:flex flex-col justify-start py-10 flex-shrink-0">
            <h2 className="text-5xl font-black text-black leading-tight tracking-tight mb-6">
              입찰의 시작부터 끝까지,
            </h2>
            <span className="text-[110px] font-black text-white leading-[0.9] tracking-[-3px] font-[Inter]">
              KIRA
            </span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Solutions;
