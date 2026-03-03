import React from 'react';

const docs = [
  {
    tag: 'DOCX',
    title: '기술제안서',
    lines: [
      '평가항목별 섹션 자동 생성',
      '100+ 페이지 분량',
      'Layer 1+2 지식 주입',
      '블라인드 위반 자동 검증',
    ],
    num: '01',
    featured: false,
  },
  {
    tag: 'XLSX',
    title: '수행계획서\n& WBS',
    lines: [
      '과업 → WBS 태스크 분해',
      '간트차트 자동 생성',
      '인력배치표 연동',
      '방법론 자동 감지',
    ],
    num: '02',
    featured: false,
  },
  {
    tag: 'PPTX',
    title: 'PPT\n발표자료',
    lines: [
      '제안서 → 핵심 추출',
      '25장 슬라이드 구성',
      '발표 노트 자동 생성',
      '예상질문 10개 + 답변',
    ],
    num: '03',
    featured: false,
  },
  {
    tag: 'DOCX',
    title: '실적/경력\n기술서',
    lines: [
      '회사 DB에서 유사 실적 매칭',
      'RFP 연관성 자동 서술',
      '투입인력 최적 배치',
      '평가 점수 극대화',
    ],
    num: '04',
    featured: false,
  },
  {
    tag: 'CHECK',
    title: '제출\n체크리스트',
    lines: [
      '필수 제출서류 자동 추출',
      '누락 항목 실시간 알림',
      '마감일 관리',
      '서류 완성도 체크',
    ],
    num: '05',
    featured: true,
  },
];

const PackageSection: React.FC = () => {
  return (
    <section className="bg-white py-20 lg:py-28">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        {/* Header */}
        <div className="mb-16">
          <p className="text-xs font-bold tracking-[0.2em] text-[#0000FF] mb-4">
            ONE-CLICK PACKAGE
          </p>
          <h2 className="text-3xl sm:text-4xl lg:text-[42px] font-black text-black tracking-tight leading-tight mb-6">
            GO 판정 후,
            <br />
            전체 패키지를 만듭니다.
          </h2>
          <p className="text-sm text-gray-400 leading-relaxed max-w-2xl">
            제안서부터 발표자료까지 — 원클릭으로 입찰 패키지 전체를 생성합니다.
            <br />
            외주 비용 300~1,000만원, 2~4주 소요되던 작업을 AI가 수 분 만에.
          </p>
        </div>

        {/* 5 Document Cards */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
          {docs.map((doc) => (
            <div
              key={doc.num}
              className={`rounded p-5 relative overflow-hidden ${
                doc.featured
                  ? 'bg-[#0000FF] text-white'
                  : 'bg-gray-100 text-black'
              }`}
            >
              <p
                className={`text-[10px] font-bold tracking-[0.1em] mb-2 ${
                  doc.featured ? 'text-white/60' : 'text-[#0000FF]'
                }`}
              >
                {doc.tag}
              </p>
              <h3 className="text-lg font-black leading-tight whitespace-pre-line mb-4">
                {doc.title}
              </h3>
              <ul className="space-y-1.5">
                {doc.lines.map((line) => (
                  <li
                    key={line}
                    className={`text-[11px] leading-relaxed ${
                      doc.featured ? 'text-white/80' : 'text-gray-400'
                    }`}
                  >
                    {line}
                  </li>
                ))}
              </ul>
              <span
                className={`absolute bottom-2 right-3 text-5xl font-black leading-none ${
                  doc.featured ? 'text-white/10' : 'text-gray-200'
                }`}
              >
                {doc.num}
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

export default PackageSection;
