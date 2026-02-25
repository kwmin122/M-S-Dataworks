import React from 'react';
import { Search, FileCheck, BarChart3, MessageSquareText } from 'lucide-react';

const workflows = [
  {
    icon: Search,
    label: '공고 검색',
    title: '나라장터 공고를\n실시간으로 검색합니다',
    desc: '키워드, 업무구분, 지역, 금액 조건으로 나라장터 입찰 공고를 검색하고 관심 공고를 빠르게 선별하세요. 최근 6개월까지 조회 가능합니다.',
    image: '/images/sol-1-search.png',
    alt: '다중 모니터에서 공고를 검색하는 모습',
  },
  {
    icon: FileCheck,
    label: '자격요건 추출',
    title: '수백 페이지에서\n핵심 요건만 뽑아냅니다',
    desc: '참가 자격, 기술 인력, 실적 조건, 결격사유를 AI가 자동으로 추출합니다. 놓치기 쉬운 세부 조건까지 꼼꼼하게 확인해 드립니다.',
    image: '/images/sol-2-requirements.png',
    alt: '공고 문서에서 핵심 요건을 하이라이팅하는 모습',
  },
  {
    icon: BarChart3,
    label: 'GO/NO-GO 판단',
    title: '입찰 참여 여부를\n근거와 함께 판단합니다',
    desc: '회사 문서를 등록하면 공고 요건과 자동 매칭하여 GO/NO-GO를 추천합니다. 부족한 요건은 준비 가이드를 함께 제공합니다.',
    image: '/images/sol-3-gonogo.jpg',
    alt: '회의실에서 입찰 참여를 판단하는 비즈니스 미팅',
  },
  {
    icon: MessageSquareText,
    label: '문서 Q&A',
    title: '공고서에 대해\n자유롭게 질문하세요',
    desc: '분석된 문서의 어떤 내용이든 대화로 물어볼 수 있습니다. 원문 페이지와 근거를 함께 표시하여 신뢰할 수 있는 답변을 드립니다.',
    image: '/images/sol-4-qa.png',
    alt: '카페에서 태블릿으로 문서 Q&A를 하는 모습',
  },
];

const galleryItems = [
  {
    image: '/images/gallery-1-search.png',
    alt: '대형 디스플레이 앞에서 공고를 검색하는 전문가',
    title: '공고 검색 & 필터링',
  },
  {
    image: '/images/gallery-2-analysis.png',
    alt: '다양한 문서와 체크리스트가 펼쳐진 분석 작업 공간',
    title: '자격요건 자동 분석',
  },
  {
    image: '/images/gallery-3-evaluation.png',
    alt: '두 명의 전문가가 문서를 함께 검토하는 모습',
    title: '회사 역량 비교 평가',
  },
  {
    image: '/images/gallery-4-report.png',
    alt: '노트북과 인쇄된 리포트가 나란히 놓인 업무 환경',
    title: '일괄 평가 & 리포트',
  },
];

const Solutions: React.FC = () => {
  return (
    <div id="solutions">
      {workflows.map((item, index) => (
        <section key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-slate-50'} style={{ paddingTop: '7rem', paddingBottom: '7rem' }}>
          <div className="mx-auto max-w-7xl px-6 lg:px-8">
            <div className={`flex flex-col lg:flex-row items-center gap-12 lg:gap-20 ${index % 2 === 1 ? 'lg:flex-row-reverse' : ''}`}>

              {/* Text Side */}
              <div className="flex-1 max-w-xl">
                <div className="flex items-center gap-3 mb-6">
                  <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-900 text-white">
                    <item.icon size={20} />
                  </div>
                  <span className="text-sm font-semibold text-slate-500 tracking-wide">{item.label}</span>
                </div>

                <h3 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold text-slate-900 leading-tight tracking-tight whitespace-pre-line font-sans">
                  {item.title}
                </h3>

                <p className="mt-8 text-lg text-slate-500 leading-relaxed">
                  {item.desc}
                </p>
              </div>

              {/* Image Side */}
              <div className="flex-1 w-full">
                <div className="overflow-hidden rounded-2xl shadow-2xl">
                  <img
                    src={item.image}
                    alt={item.alt}
                    loading="lazy"
                    className="w-full h-auto object-cover"
                  />
                </div>
              </div>

            </div>
          </div>
        </section>
      ))}

      {/* 이미지 갤러리 */}
      <section className="bg-slate-900 py-28 sm:py-36">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mb-16">
            <p className="text-sm font-semibold text-slate-400 tracking-wide mb-4">활용 사례</p>
            <h2 className="text-4xl sm:text-5xl font-extrabold text-white tracking-tight leading-tight font-sans">
              입찰의 시작부터 끝까지,<br />
              <span className="font-serif italic">Kira.</span>
            </h2>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {galleryItems.map((item, idx) => (
              <div key={idx} className="group">
                <div className="relative overflow-hidden rounded-2xl aspect-[4/5] mb-4">
                  <img
                    src={item.image}
                    alt={item.alt}
                    loading="lazy"
                    className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-700 ease-in-out"
                  />
                  <div className="absolute inset-0 bg-black/0 group-hover:bg-black/10 transition-colors duration-300" />
                </div>
                <h3 className="text-lg font-bold text-white">{item.title}</h3>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
};

export default Solutions;
