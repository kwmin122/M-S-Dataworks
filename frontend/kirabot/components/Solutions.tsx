import React from 'react';

const useCases = [
  {
    title: "공공 입찰 (RFP)",
    description: "제안요청서를 분석하여 필수 요건과 평가 항목을 놓치지 마세요.",
    image: "https://images.unsplash.com/photo-1454165804606-c3d57bc86b40?auto=format&fit=crop&q=80&w=800",
    alt: "노트북으로 문서를 검토하는 모습"
  },
  {
    title: "계약 관리",
    description: "수많은 계약서 조항 중 독소 조항이나 특약 사항을 빠르게 검색하세요.",
    image: "https://images.unsplash.com/photo-1554224155-8d04cb21cd6c?auto=format&fit=crop&q=80&w=800",
    alt: "계약서와 계산기가 있는 책상"
  },
  {
    title: "현장 / 안전",
    description: "시방서, 안전 지침서 등 현장에서 필요한 매뉴얼을 즉시 확인하세요.",
    image: "https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?auto=format&fit=crop&q=80&w=800",
    alt: "용접 작업을 하는 산업 현장 근로자"
  },
  {
    title: "사내 보고서",
    description: "과거 보고서나 회의록에서 필요한 히스토리를 대화하듯 찾아보세요.",
    image: "https://images.unsplash.com/photo-1551288049-bebda4e38f71?auto=format&fit=crop&q=80&w=800",
    alt: "데이터 대시보드 화면"
  }
];

const Solutions: React.FC = () => {
  return (
    <div id="solutions" className="py-24 bg-white">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        
        {/* Header Section */}
        <div className="flex flex-col lg:flex-row justify-between items-start lg:items-end mb-20 gap-8">
          <div className="max-w-md">
            <p className="text-lg text-slate-600 leading-relaxed font-medium">
              중소기업부터 대기업까지.<br/>
              KiraBot은 모든 산업군의 문서 업무에 최적화되어 있습니다.
            </p>
          </div>
          <div className="text-right w-full lg:w-auto">
            <h2 className="text-4xl sm:text-5xl lg:text-6xl font-medium tracking-tight text-slate-900 leading-tight">
              문서가 있는 곳 어디서나,<br/>
              <span className="font-serif italic font-bold">KiraBot.</span>
            </h2>
          </div>
        </div>
        
        {/* Grid Section */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 lg:gap-8">
          {useCases.map((item, index) => (
            <div key={index} className="flex flex-col group cursor-default">
              <div className="relative overflow-hidden rounded-2xl aspect-[4/5] mb-6 bg-slate-100">
                <img 
                  src={item.image} 
                  alt={item.alt} 
                  className="object-cover w-full h-full group-hover:scale-105 transition-transform duration-700 ease-in-out"
                />
                <div className="absolute inset-0 bg-black/0 group-hover:bg-black/5 transition-colors duration-300"></div>
              </div>
              
              <h3 className="text-xl font-bold text-slate-900 mb-2">{item.title}</h3>
              <p className="text-sm text-slate-500 leading-relaxed font-medium">
                {item.description}
              </p>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
};

export default Solutions;