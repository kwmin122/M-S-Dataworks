import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import HowItWorks from './components/HowItWorks';
import Features from './components/Features';
import Solutions from './components/Solutions';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import LoginModal from './components/LoginModal';
import PrivacyPolicy from './components/PrivacyPolicy';
import TermsOfService from './components/TermsOfService';
import { ChatProvider } from './context/ChatContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import AppShell from './components/layout/AppShell';
import ChatPage from './components/chat/ChatPage';
import DashboardPage from './components/dashboard/DashboardPage';
import AlertSettingsPage from './components/settings/AlertSettingsPage';
import SettingsPage from './components/settings/SettingsPage';
import SettingsGeneral from './components/settings/SettingsGeneral';
import SettingsAccount from './components/settings/SettingsAccount';
import ForecastPage from './components/forecast/ForecastPage';
import type { User } from './types';
import { trackPageView } from './utils/analytics';
import {
  consumePostLoginTarget,
  getCurrentGoogleUser,
  isGoogleOAuthConfigured,
  signInWithGoogle,
  signOutGoogleUser,
} from './services/authService';

function SettingsCompanyPlaceholder() {
  return <div className="text-slate-500 text-sm">회사 정보 (준비 중)</div>;
}

function AppRoutes() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [authError, setAuthError] = useState('');
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();

  // ?login=1 query param -> auto open login modal
  useEffect(() => {
    if (searchParams.get('login') === '1') {
      setIsLoginModalOpen(true);
      // Clean up the query param
      const newParams = new URLSearchParams(searchParams);
      newParams.delete('login');
      setSearchParams(newParams, { replace: true });
    }
  }, [searchParams, setSearchParams]);

  // Track page views on route change
  useEffect(() => {
    trackPageView(window.location.pathname);
  }, [searchParams]); // triggers on navigation since searchParams changes

  // Bootstrap auth
  useEffect(() => {
    const bootstrapAuth = async (): Promise<void> => {
      try {
        const currentUser = await getCurrentGoogleUser();
        if (!currentUser) return;
        setUser(currentUser);
        if (consumePostLoginTarget()) {
          const redirect = searchParams.get('redirect') || '/chat';
          navigate(redirect, { replace: true });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : '로그인 상태 확인 중 오류가 발생했습니다.';
        setAuthError(message);
      }
    };
    void bootstrapAuth();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const handleStart = useCallback(() => {
    setAuthError('');
    if (user) {
      navigate('/chat');
      return;
    }
    setIsLoginModalOpen(true);
  }, [user, navigate]);

  const handleAlertSetup = useCallback(() => {
    setAuthError('');
    if (user) {
      navigate('/settings/alerts');
      return;
    }
    setIsLoginModalOpen(true);
  }, [user, navigate]);

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
    } catch (error) {
      const message = error instanceof Error ? error.message : '로그아웃 중 오류가 발생했습니다.';
      setAuthError(message);
    }
    // Security: clear session/local storage and full reload
    try {
      localStorage.removeItem('kirabot_conversations');
    } catch { /* ignore */ }
    setUser(null);
    navigate('/');
    window.location.replace('/');
  };

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) element.scrollIntoView({ behavior: 'smooth' });
  }, []);

  // Landing page component
  const LandingPage = (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
      <Navbar
        user={user}
        onNavigate={(path: string) => navigate(path)}
        onLoginClick={() => setIsLoginModalOpen(true)}
        onLogoutClick={() => void handleLogout()}
        onScrollToSection={scrollToSection}
      />
      <main className="flex-grow">
        <Hero onStart={handleStart} onAlertSetup={handleAlertSetup} />
        <HowItWorks />
        <Features />
        <Solutions />
        <Pricing />
      </main>
      <Footer onNavigate={(path: string) => navigate(path)} onNavigateSection={scrollToSection} />
    </div>
  );

  return (
    <>
      <Routes>
        {/* Landing */}
        <Route path="/" element={LandingPage} />

        {/* Legal pages */}
        <Route path="/privacy" element={
          <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
            <Navbar user={user} onNavigate={(path) => navigate(path)} onLoginClick={() => setIsLoginModalOpen(true)} onLogoutClick={() => void handleLogout()} onScrollToSection={scrollToSection} />
            <main className="flex-grow"><PrivacyPolicy /></main>
            <Footer onNavigate={(path) => navigate(path)} onNavigateSection={scrollToSection} />
          </div>
        } />
        <Route path="/terms" element={
          <div className="min-h-screen bg-slate-50 flex flex-col font-sans">
            <Navbar user={user} onNavigate={(path) => navigate(path)} onLoginClick={() => setIsLoginModalOpen(true)} onLogoutClick={() => void handleLogout()} onScrollToSection={scrollToSection} />
            <main className="flex-grow"><TermsOfService /></main>
            <Footer onNavigate={(path) => navigate(path)} onNavigateSection={scrollToSection} />
          </div>
        } />

        {/* Protected app routes */}
        <Route element={
          <ProtectedRoute user={user}>
            <ChatProvider>
              <AppShell user={user} onLogout={() => void handleLogout()} />
            </ChatProvider>
          </ProtectedRoute>
        }>
          <Route path="/chat" element={<ChatPage user={user} />} />
          <Route path="/settings/alerts" element={<AlertSettingsPage />} />
          <Route path="/forecast" element={<ForecastPage />} />

          {/* Settings nested routes */}
          <Route path="/settings" element={<SettingsPage />}>
            <Route index element={<Navigate to="general" replace />} />
            <Route path="general" element={<SettingsGeneral user={user} />} />
            <Route path="company" element={<SettingsCompanyPlaceholder />} />
            <Route path="usage" element={<DashboardPage />} />
            <Route path="account" element={<SettingsAccount user={user} onLogout={() => void handleLogout()} />} />
          </Route>

          {/* Legacy redirect */}
          <Route path="/dashboard" element={<Navigate to="/settings/usage" replace />} />
        </Route>

        {/* 404 -> redirect to landing */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>

      <LoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onLogin={handleLogin}
        authError={authError}
        onOpenPrivacy={() => { setIsLoginModalOpen(false); navigate('/privacy'); }}
        onOpenTerms={() => { setIsLoginModalOpen(false); navigate('/terms'); }}
      />
    </>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppRoutes />
    </BrowserRouter>
  );
}
