import React, { useEffect, useState } from 'react';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import Features from './components/Features';
import Solutions from './components/Solutions';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import Dashboard from './components/Dashboard';
import LoginModal from './components/LoginModal';
import PrivacyPolicy from './components/PrivacyPolicy';
import TermsOfService from './components/TermsOfService';
import { AppView, User } from './types';
import {
  consumePostLoginTarget,
  getCurrentGoogleUser,
  isGoogleOAuthConfigured,
  signInWithGoogle,
  signOutGoogleUser,
} from './services/authService';

const App: React.FC = () => {
  const [currentView, setCurrentView] = useState<AppView>(AppView.LANDING);
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState('');

  useEffect(() => {
    const bootstrapAuth = async (): Promise<void> => {
      try {
        const currentUser = await getCurrentGoogleUser();
        if (!currentUser) {
          return;
        }
        setUser(currentUser);
        if (consumePostLoginTarget()) {
          setCurrentView(AppView.DASHBOARD);
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : '로그인 상태 확인 중 오류가 발생했습니다.';
        setAuthError(message);
      }
    };
    void bootstrapAuth();
  }, []);

  const handleStart = () => {
    setAuthError('');
    if (user) {
      setCurrentView(AppView.DASHBOARD);
      return;
    }
    setIsLoginModalOpen(true);
  };

  const handleLogin = async (): Promise<void> => {
    setAuthError('');
    try {
      if (!isGoogleOAuthConfigured()) {
        setAuthError('Google OAuth 환경변수가 설정되지 않았습니다. VITE_GOOGLE_LOGIN_URL을 확인해주세요.');
        return;
      }
      await signInWithGoogle();
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Google 로그인 시작에 실패했습니다.';
      setAuthError(message);
    }
  };

  const handleLogout = async (): Promise<void> => {
    setAuthError('');
    try {
      await signOutGoogleUser();
      setUser(null);
      setCurrentView(AppView.LANDING);
    } catch (error) {
      const message = error instanceof Error ? error.message : '로그아웃 중 오류가 발생했습니다.';
      setAuthError(message);
    }
  };

  const navigateToSection = (id: string): void => {
    if (currentView !== AppView.LANDING) {
      setCurrentView(AppView.LANDING);
      setTimeout(() => {
        const element = document.getElementById(id);
        if (element) {
          element.scrollIntoView({ behavior: 'smooth' });
        }
      }, 100);
      return;
    }
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar 
        currentView={currentView} 
        onNavigate={setCurrentView} 
        user={user}
        onLoginClick={() => setIsLoginModalOpen(true)}
        onLogoutClick={() => void handleLogout()}
      />
      
      <main className="flex-grow">
        {currentView === AppView.LANDING ? (
          <>
            <Hero onStart={handleStart} />
            <Features />
            <Solutions />
            <Pricing />
            <Footer onNavigate={setCurrentView} onNavigateSection={navigateToSection} />
          </>
        ) : currentView === AppView.DASHBOARD ? (
          <Dashboard user={user} />
        ) : currentView === AppView.PRIVACY ? (
          <PrivacyPolicy />
        ) : (
          <TermsOfService />
        )}
      </main>

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLogin={handleLogin}
        authError={authError}
        onOpenPrivacy={() => {
          setIsLoginModalOpen(false);
          setCurrentView(AppView.PRIVACY);
        }}
        onOpenTerms={() => {
          setIsLoginModalOpen(false);
          setCurrentView(AppView.TERMS);
        }}
      />
    </div>
  );
};

export default App;
