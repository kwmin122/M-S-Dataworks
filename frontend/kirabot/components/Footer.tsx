import React from 'react';

interface FooterProps {
  onNavigate: (path: string) => void;
  onNavigateSection: (id: string) => void;
}

const Footer: React.FC<FooterProps> = ({ onNavigate, onNavigateSection }) => {
  return (
    <footer className="bg-[#0A0A0A] text-white py-12">
      <div className="mx-auto max-w-7xl px-6 lg:px-8">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-10">
          {/* Logo & Description */}
          <div className="lg:col-span-2">
            <h2 className="text-2xl font-black leading-tight mb-4">
              M&S
              <br />
              SOLUTIONS
            </h2>
            <p className="text-xs text-gray-500 leading-relaxed">
              공공조달 입찰 자동화 AI 플랫폼
              <br />
              Powered by Kira Bot
            </p>
          </div>

          {/* Product */}
          <div>
            <h3 className="text-[10px] font-bold tracking-[0.2em] text-gray-500 mb-4">
              PRODUCT
            </h3>
            <ul className="space-y-2.5">
              <li>
                <button
                  type="button"
                  onClick={() => onNavigateSection('solutions')}
                  className="bg-transparent text-gray-300 hover:text-white text-sm"
                >
                  공고 검색
                </button>
              </li>
              <li>
                <button
                  type="button"
                  onClick={() => onNavigateSection('product')}
                  className="bg-transparent text-gray-300 hover:text-white text-sm"
                >
                  RFP 분석
                </button>
              </li>
              <li><span className="text-gray-300 text-sm">제안서 생성</span></li>
              <li><span className="text-gray-300 text-sm">PPT · WBS</span></li>
            </ul>
          </div>

          {/* Company */}
          <div>
            <h3 className="text-[10px] font-bold tracking-[0.2em] text-gray-500 mb-4">
              COMPANY
            </h3>
            <ul className="space-y-2.5">
              <li><span className="text-gray-300 text-sm">소개</span></li>
              <li><span className="text-gray-300 text-sm">블로그</span></li>
              <li>
                <a
                  href="mailto:contact@mssolutions.kr"
                  className="text-gray-300 hover:text-white text-sm"
                >
                  문의하기
                </a>
              </li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-[10px] font-bold tracking-[0.2em] text-gray-500 mb-4">
              LEGAL
            </h3>
            <ul className="space-y-2.5">
              <li>
                <a href="/terms" className="text-gray-300 hover:text-white text-sm">
                  이용약관
                </a>
              </li>
              <li>
                <a href="/privacy" className="text-gray-300 hover:text-white text-sm">
                  개인정보처리방침
                </a>
              </li>
            </ul>
          </div>
        </div>

        {/* Divider + Copyright */}
        <div className="h-px bg-gray-800 mt-12 mb-6" />
        <div className="flex flex-col md:flex-row justify-between items-center text-[11px] text-gray-600">
          <p>&copy; 2026 M&S Solutions. All rights reserved.</p>
          <p className="mt-2 md:mt-0">bill.min122@gmail.com</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
