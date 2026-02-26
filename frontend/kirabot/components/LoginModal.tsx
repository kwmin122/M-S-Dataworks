import React from 'react';
import { X } from 'lucide-react';
import KiraBotLogo from './KiraBotLogo';

interface LoginModalProps {
  isOpen: boolean;
  onClose: () => void;
  onLogin: () => Promise<void> | void;
  onKakaoLogin?: () => Promise<void> | void;
  authError?: string;
  onOpenPrivacy: () => void;
  onOpenTerms: () => void;
}

const LoginModal: React.FC<LoginModalProps> = ({
  isOpen,
  onClose,
  onLogin,
  onKakaoLogin,
  authError,
  onOpenPrivacy,
  onOpenTerms,
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      {/* Backdrop with blur */}
      <div 
        className="absolute inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity"
        onClick={onClose}
      ></div>

      {/* Modal Content */}
      <div className="relative w-full max-w-md bg-white rounded-2xl shadow-2xl p-8 transform transition-all scale-100">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-slate-400 hover:text-slate-600 transition-colors"
        >
          <X size={24} />
        </button>

        <div className="flex flex-col items-center text-center">
          <div className="mb-6">
            <KiraBotLogo size={48} />
          </div>

          <h2 className="text-2xl font-bold text-slate-900 mb-2">Kira 시작하기</h2>
          <p className="text-slate-600 mb-8">
            로그인하고 복잡한 문서 업무를<br/>AI로 쉽고 빠르게 처리하세요.
          </p>
          <p className="text-xs text-slate-400 mb-4">Powered by M&S SOLUTIONS</p>

          <button
            onClick={onLogin}
            className="w-full flex items-center justify-center gap-3 bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium py-3 px-4 rounded-xl transition-all shadow-sm active:scale-[0.98]"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Google 계정으로 계속하기
          </button>

          {onKakaoLogin && (
            <button
              onClick={onKakaoLogin}
              className="w-full flex items-center justify-center gap-3 font-medium py-3 px-4 rounded-xl transition-all shadow-sm active:scale-[0.98] mt-3"
              style={{ backgroundColor: '#FEE500', color: '#191919' }}
            >
              <svg className="h-5 w-5" viewBox="0 0 24 24">
                <path
                  d="M12 3C6.48 3 2 6.36 2 10.44c0 2.62 1.75 4.93 4.38 6.24l-1.12 4.16c-.1.36.32.65.63.44l4.94-3.26c.38.04.77.06 1.17.06 5.52 0 10-3.36 10-7.64C22 6.36 17.52 3 12 3z"
                  fill="#191919"
                />
              </svg>
              카카오 계정으로 계속하기
            </button>
          )}

          {authError ? (
            <p className="mt-4 w-full rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-left text-xs text-rose-700">
              {authError}
            </p>
          ) : null}

          <p className="mt-8 text-xs text-slate-400 leading-relaxed max-w-xs">
            계속하면{' '}
            <a href="/terms" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">이용약관</a>
            {' '}및{' '}
            <a href="/privacy" target="_blank" rel="noopener noreferrer" className="underline hover:text-slate-600">개인정보처리방침</a>
            {' '}에 동의하는 것으로 간주합니다.
          </p>
        </div>
      </div>
    </div>
  );
};

export default LoginModal;
