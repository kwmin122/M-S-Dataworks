import React from 'react';

const TermsOfService: React.FC = () => {
  return (
    <section className="bg-slate-50 py-14">
      <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-10">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">이용약관</h1>
        <p className="mt-3 text-sm text-slate-500">시행일: 2026년 2월 19일</p>

        <div className="mt-8 space-y-8 text-sm leading-7 text-slate-700">
          <section>
            <h2 className="text-lg font-bold text-slate-900">제1조 (목적)</h2>
            <p className="mt-2">
              본 약관은 M&amp;S Solutions(이하 “회사”)가 제공하는 KiraBot 서비스(이하 “서비스”)의 이용과 관련하여 회사와 이용자의 권리,
              의무 및 책임사항을 규정함을 목적으로 합니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제2조 (정의)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>“이용자”란 본 약관에 따라 서비스를 이용하는 개인 또는 법인을 말합니다.</li>
              <li>“계정”이란 이용자 식별 및 서비스 제공을 위해 생성된 인증 단위를 말합니다.</li>
              <li>“콘텐츠”란 이용자가 업로드한 문서, 입력한 질문, 생성된 분석 결과 등을 말합니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제3조 (약관의 효력 및 변경)</h2>
            <p className="mt-2">
              회사는 관련 법령을 위반하지 않는 범위에서 본 약관을 변경할 수 있으며, 변경 시 시행일 및 변경 사유를 서비스 내 공지합니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제4조 (서비스 제공 및 변경)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>회사는 문서 업로드, 분석, 질의응답, 근거 참조 등 서비스를 제공합니다.</li>
              <li>서비스는 운영·기술상 필요에 따라 변경 또는 중단될 수 있으며, 중대한 변경은 사전 공지합니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제5조 (계정 및 인증)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>이용자는 회사가 제공하는 소셜 로그인 등 인증 수단으로 계정을 생성·이용할 수 있습니다.</li>
              <li>이용자는 계정 보안 의무를 부담하며, 계정 도용이 의심될 경우 즉시 회사에 통지해야 합니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제6조 (이용자의 의무)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>관계 법령, 본 약관, 서비스 공지사항을 준수해야 합니다.</li>
              <li>불법 정보 업로드, 타인 권리 침해, 서비스 운영 방해 행위를 해서는 안 됩니다.</li>
              <li>민감 정보 업로드 전 내부 보안정책 및 법적 의무를 확인해야 합니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제7조 (콘텐츠 및 지식재산권)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>이용자가 업로드한 콘텐츠의 권리와 책임은 이용자에게 있습니다.</li>
              <li>회사는 서비스 운영 목적 범위에서만 콘텐츠를 처리합니다.</li>
              <li>서비스 UI, 로고, 소프트웨어 등 회사가 작성한 저작물의 권리는 회사에 귀속됩니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제8조 (AI 응답 고지)</h2>
            <p className="mt-2">
              서비스의 분석·추천·요약 결과는 AI 기반 참고 정보이며, 법률·회계·세무 등 전문 자문을 대체하지 않습니다.
              최종 의사결정의 책임은 이용자에게 있습니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제9조 (서비스 이용 제한)</h2>
            <p className="mt-2">
              회사는 약관 위반, 불법 행위, 보안 침해 시도, 시스템 과부하 유발 등 운영상 중대한 사유가 확인되면 서비스 이용을 제한할 수 있습니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제10조 (책임 제한)</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>회사는 천재지변, 불가항력, 이용자 귀책 사유로 인한 손해에 대해 책임을 지지 않습니다.</li>
              <li>AI 결과의 정확성·완전성에 관한 최종 검토 책임은 이용자에게 있습니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">제11조 (분쟁 해결 및 준거법)</h2>
            <p className="mt-2">
              본 약관은 대한민국 법령을 준거법으로 하며, 서비스 이용과 관련한 분쟁은 민사소송법상 관할법원에 따릅니다.
            </p>
          </section>
        </div>
      </div>
    </section>
  );
};

export default TermsOfService;
