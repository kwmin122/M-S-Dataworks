import React, { useState } from 'react';
import { Menu, X, LogOut } from 'lucide-react';
import KiraBotLogo from './KiraBotLogo';
import Button from './Button';
import type { User } from '../types';
import { isStudioVisible } from '../services/studioApi';

interface NavbarProps {
  user: User | null;
  onNavigate: (path: string) => void;
  onLoginClick: () => void;
  onLogoutClick: () => void;
  onScrollToSection: (id: string) => void;
}

const Navbar: React.FC<NavbarProps> = ({ user, onNavigate, onLoginClick, onLogoutClick, onScrollToSection }) => {
  const [mobileOpen, setMobileOpen] = useState(false);

  const scrollToSection = (id: string) => {
    setMobileOpen(false);
    onScrollToSection(id);
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => onNavigate('/')}
        >
          <KiraBotLogo size={36} className="shrink-0" />
          <span className="text-xl font-extrabold tracking-tight text-slate-900">M&S SOLUTIONS</span>
        </div>

        {/* Desktop nav */}
        <div className="hidden md:flex items-center gap-8">
          {user ? (
            <>
              <button onClick={() => onNavigate('/chat')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">공고 탐색</button>
              {isStudioVisible() && (
                <button onClick={() => onNavigate('/studio')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">입찰 문서 AI 작성</button>
              )}
              <button onClick={() => onNavigate('/alerts')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">알림</button>
              <button onClick={() => onNavigate('/forecast')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">예측</button>
            </>
          ) : (
            <>
              <button onClick={() => scrollToSection('product')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">제품소개</button>
              <button onClick={() => scrollToSection('solutions')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">활용사례</button>
              <button onClick={() => scrollToSection('pricing')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">요금제</button>
            </>
          )}
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <>
              <Button onClick={() => onNavigate('/chat')} size="sm" className="hidden sm:inline-flex">
                시작하기
              </Button>
              <button
                type="button"
                onClick={onLogoutClick}
                className="hidden sm:flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-700 transition-colors"
              >
                <LogOut size={14} />
                <span>로그아웃</span>
              </button>
              {user.avatarUrl && (
                <img
                  src={user.avatarUrl}
                  alt={user.name}
                  className="hidden sm:block h-8 w-8 rounded-full ring-2 ring-slate-200"
                />
              )}
            </>
          ) : (
            <>
               <span
                 onClick={onLoginClick}
                 className="hidden sm:block text-sm font-medium text-slate-600 cursor-pointer hover:text-slate-900"
               >
                 로그인
               </span>
               <Button onClick={onLoginClick} size="sm" className="hidden sm:inline-flex">
                 Kira 시작하기
               </Button>
            </>
          )}
          {/* Hamburger (mobile) */}
          <button
            type="button"
            className="md:hidden flex items-center justify-center h-9 w-9 rounded-lg text-slate-600 hover:bg-slate-100"
            onClick={() => setMobileOpen((v) => !v)}
            aria-label="메뉴 열기"
          >
            {mobileOpen ? <X size={22} /> : <Menu size={22} />}
          </button>
        </div>
      </div>

      {/* Mobile dropdown */}
      {mobileOpen && (
        <div className="md:hidden border-t border-slate-200 bg-white/95 backdrop-blur-md px-4 pb-4 pt-3 space-y-3">
          <button onClick={() => scrollToSection('product')} className="block w-full text-left text-sm font-medium text-slate-700 py-2 hover:text-primary-700">제품소개</button>
          <button onClick={() => scrollToSection('solutions')} className="block w-full text-left text-sm font-medium text-slate-700 py-2 hover:text-primary-700">활용사례</button>
          <button onClick={() => scrollToSection('pricing')} className="block w-full text-left text-sm font-medium text-slate-700 py-2 hover:text-primary-700">요금제</button>
          <div className="border-t border-slate-100 pt-3 space-y-2">
            {user ? (
              <>
                <Button onClick={() => { setMobileOpen(false); onNavigate('/chat'); }} size="sm" className="w-full">
                  공고 탐색
                </Button>
                {isStudioVisible() && (
                  <Button onClick={() => { setMobileOpen(false); onNavigate('/studio'); }} size="sm" variant="secondary" className="w-full">
                    입찰 문서 AI 작성
                  </Button>
                )}
                <button
                  type="button"
                  onClick={() => { setMobileOpen(false); onLogoutClick(); }}
                  className="w-full flex items-center justify-center gap-1.5 py-2 text-sm text-slate-500 hover:text-slate-700"
                >
                  <LogOut size={14} />
                  로그아웃
                </button>
              </>
            ) : (
              <Button onClick={() => { setMobileOpen(false); onLoginClick(); }} size="sm" className="w-full">
                Kira 시작하기
              </Button>
            )}
          </div>
        </div>
      )}
    </nav>
  );
};

export default Navbar;
