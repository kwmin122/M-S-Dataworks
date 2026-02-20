import React from 'react';
import { Layers } from 'lucide-react';
import Button from './Button';
import { AppView, User } from '../types';

interface NavbarProps {
  currentView: AppView;
  onNavigate: (view: AppView) => void;
  user: User | null;
  onLoginClick: () => void;
  onLogoutClick: () => void;
}

const Navbar: React.FC<NavbarProps> = ({ currentView, onNavigate, user, onLoginClick, onLogoutClick }) => {
  const scrollToSection = (id: string) => {
    if (currentView !== AppView.LANDING) {
      onNavigate(AppView.LANDING);
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) element.scrollIntoView({ behavior: 'smooth' });
      }, 100);
    } else {
      const element = document.getElementById(id);
      if (element) element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <nav className="sticky top-0 z-50 w-full border-b border-slate-200 bg-white/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div 
          className="flex items-center gap-2 cursor-pointer"
          onClick={() => onNavigate(AppView.LANDING)}
        >
          <div className="flex h-8 min-w-[42px] items-center justify-center rounded-lg bg-primary-700 px-2 text-white">
            <Layers size={20} />
          </div>
          <span className="text-xl font-extrabold tracking-tight text-slate-900">M&S Solutions</span>
        </div>

        <div className="hidden md:flex items-center gap-8">
          <button onClick={() => scrollToSection('product')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">Product</button>
          <button onClick={() => scrollToSection('solutions')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">Solutions</button>
          <button onClick={() => scrollToSection('pricing')} className="text-sm font-medium text-slate-600 hover:text-primary-700 transition-colors">Pricing</button>
        </div>

        <div className="flex items-center gap-4">
          {user ? (
            <Button onClick={onLogoutClick} size="sm" variant="outline">
              로그아웃
            </Button>
          ) : (
            <>
               <span 
                 onClick={onLoginClick}
                 className="hidden sm:block text-sm font-medium text-slate-600 cursor-pointer hover:text-slate-900"
               >
                 로그인
               </span>
               <Button onClick={onLoginClick} size="sm">
                 Kira bot 실행하기
               </Button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
};

export default Navbar;
