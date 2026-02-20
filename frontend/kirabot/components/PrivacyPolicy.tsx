import React from 'react';

const PrivacyPolicy: React.FC = () => {
  return (
    <section className="bg-slate-50 py-14">
      <div className="mx-auto max-w-4xl rounded-2xl border border-slate-200 bg-white px-6 py-8 shadow-sm sm:px-10">
        <h1 className="text-3xl font-extrabold tracking-tight text-slate-900">개인정보처리방침</h1>
        <p className="mt-3 text-sm text-slate-500">시행일: 2026년 2월 19일</p>

        <div className="mt-8 space-y-8 text-sm leading-7 text-slate-700">
          <section>
            <h2 className="text-lg font-bold text-slate-900">1. 총칙</h2>
            <p className="mt-2">
              M&amp;S Solutions(이하 “회사”)는 개인정보 보호법 제30조에 따라 정보주체의 개인정보를 보호하고 관련 고충을
              신속하고 원활하게 처리하기 위하여 다음과 같이 개인정보처리방침을 수립·공개합니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">2. 처리하는 개인정보 항목</h2>
            <p className="mt-2">회사는 서비스 제공을 위해 아래 정보를 처리할 수 있습니다.</p>
            <ul className="mt-2 list-disc pl-5">
              <li>필수: 이름, 이메일, 소셜 로그인 식별자, 서비스 이용기록, 접속 로그, 쿠키</li>
              <li>선택: 회사명, 직무, 문의 내용, 업로드 문서 메타데이터</li>
              <li>민감/고유식별정보: 원칙적으로 수집하지 않으며, 법령상 필요한 경우 별도 고지·동의를 받습니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">3. 개인정보의 처리 목적</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>회원 식별, 로그인/인증, 계정 관리</li>
              <li>문서 분석 서비스 제공, 결과 제공, 고객지원</li>
              <li>보안, 부정이용 방지, 서비스 품질 개선 및 운영 통계</li>
              <li>법령 준수 및 분쟁 대응</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">4. 보유 및 이용기간</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>원칙적으로 목적 달성 시 지체 없이 파기합니다.</li>
              <li>회원정보: 회원 탈퇴 시까지 (법령상 보관 의무가 있는 경우 해당 기간 동안 별도 보관)</li>
              <li>접속기록: 통신비밀보호법 등 관련 법령에서 정한 기간</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">5. 개인정보의 제3자 제공</h2>
            <p className="mt-2">
              회사는 원칙적으로 정보주체의 개인정보를 외부에 제공하지 않습니다. 다만, 정보주체 동의 또는 법령상 근거가 있는 경우에 한해 제공합니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">6. 처리위탁</h2>
            <p className="mt-2">
              회사는 서비스 운영을 위해 일부 업무를 외부에 위탁할 수 있으며, 위탁 시 관련 법령에 따라 안전하게 관리·감독합니다.
            </p>
            <ul className="mt-2 list-disc pl-5">
              <li>예시 수탁자: 클라우드 인프라, 인증 서비스, 로그/모니터링 서비스 제공사</li>
              <li>위탁업무: 서비스 호스팅, 사용자 인증, 장애 대응 및 운영</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">7. 개인정보 파기절차 및 방법</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>전자적 파일: 복구 불가능한 방식으로 영구 삭제</li>
              <li>출력물: 분쇄 또는 소각</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">8. 정보주체와 법정대리인의 권리·의무 및 행사방법</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>정보주체는 개인정보 열람·정정·삭제·처리정지를 요구할 수 있습니다.</li>
              <li>권리 행사는 이메일 또는 서면을 통해 요청할 수 있으며 회사는 지체 없이 조치합니다.</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">9. 개인정보 안전성 확보조치</h2>
            <ul className="mt-2 list-disc pl-5">
              <li>접근권한 관리, 최소권한 원칙 적용</li>
              <li>전송구간 암호화(HTTPS) 및 세션 보안 설정</li>
              <li>접속기록 보관, 침해사고 대응 절차 운영</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">10. 쿠키 정책</h2>
            <p className="mt-2">
              회사는 로그인 유지 및 서비스 품질 개선을 위해 쿠키를 사용할 수 있습니다. 브라우저 설정을 통해 쿠키 저장을 거부할 수 있으나 일부 기능 이용이 제한될 수 있습니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">11. 개인정보 보호책임자</h2>
            <p className="mt-2">개인정보 관련 문의는 아래 연락처로 접수할 수 있습니다.</p>
            <ul className="mt-2 list-disc pl-5">
              <li>담당부서: 보안/개인정보보호팀</li>
              <li>이메일: privacy@ms-solutions.co.kr</li>
            </ul>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">12. 권익침해 구제방법</h2>
            <p className="mt-2">
              개인정보 침해 관련 상담은 개인정보분쟁조정위원회, 개인정보침해신고센터(국번없이 118) 등을 통해 받을 수 있습니다.
            </p>
          </section>

          <section>
            <h2 className="text-lg font-bold text-slate-900">13. 방침 변경</h2>
            <p className="mt-2">
              본 방침의 내용 추가·삭제·수정이 있을 경우 시행 최소 7일 전(중요 변경은 30일 전) 서비스 내 공지합니다.
            </p>
          </section>
        </div>
      </div>
    </section>
  );
};

export default PrivacyPolicy;
