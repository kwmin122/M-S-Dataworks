import React from 'react';
import { Layers } from 'lucide-react';

interface FooterProps {
  onNavigate: (path: string) => void;
  onNavigateSection: (id: string) => void;
}

const Footer: React.FC<FooterProps> = ({ onNavigate, onNavigateSection }) => {
  return (
    <footer className="bg-slate-900 text-white py-12 border-t border-slate-800">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-8">
                <div className="col-span-1 md:col-span-2">
                    <div className="flex items-center gap-2 mb-4">
                        <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary-600 text-white">
                            <Layers size={20} />
                        </div>
                        <span className="text-xl font-extrabold tracking-tight">M&S KiraBot</span>
                    </div>
                    <p className="text-slate-400 max-w-xs">
                        M&S Solutions의 근거 기반 RFx 분석 도구. 문서 업로드부터 의견 확인까지 하나의 화면에서 실행하세요.
                    </p>
                </div>
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">제품</h3>
                    <ul className="space-y-3">
                        <li>
                          <button
                            type="button"
                            onClick={() => onNavigateSection('product')}
                            className="bg-transparent text-slate-300 hover:text-white"
                          >
                            기능 소개
                          </button>
                        </li>
                    </ul>
                </div>
                <div>
                    <h3 className="text-sm font-semibold uppercase tracking-wider text-slate-500 mb-4">회사</h3>
                    <ul className="space-y-3">
                        <li><a href="#" className="text-slate-300 hover:text-white">소개</a></li>
                        <li><a href="#" className="text-slate-300 hover:text-white">채용</a></li>
                        <li><a href="#" className="text-slate-300 hover:text-white">문의</a></li>
                    </ul>
                </div>
            </div>

            {/* Disclaimer Section */}
            <div className="mt-12 pt-8 border-t border-slate-800">
                <p className="text-xs text-slate-500 text-center leading-relaxed">
                    KiraBot은 AI 기반 문서 분석 도구이며, 법률·재무·의료 등 전문 분야의 판단을 대체하지 않습니다.
                    AI 응답은 참고용이며, 최종 결정은 사용자의 책임입니다.
                </p>
            </div>

            <div className="mt-6 pt-6 border-t border-slate-800 flex flex-col md:flex-row justify-between items-center text-sm text-slate-500">
                <p>&copy; 2026 M&S Solutions. All rights reserved.</p>
                <div className="flex gap-6 mt-4 md:mt-0">
                    <button
                      type="button"
                      onClick={() => onNavigate('/privacy')}
                      className="bg-transparent hover:text-slate-300"
                    >
                      개인정보처리방침
                    </button>
                    <button
                      type="button"
                      onClick={() => onNavigate('/terms')}
                      className="bg-transparent hover:text-slate-300"
                    >
                      이용약관
                    </button>
                </div>
            </div>
        </div>
    </footer>
  );
};

export default Footer;
