import React, { useEffect, useState, useCallback } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useNavigate, useSearchParams } from 'react-router-dom';
import Navbar from './components/Navbar';
import Hero from './components/Hero';
import HowItWorks from './components/HowItWorks';
import Features from './components/Features';
import Solutions from './components/Solutions';
import PackageSection from './components/PackageSection';
import Marquee from './components/Marquee';
import { isStudioVisible } from './services/studioApi';
import Pricing from './components/Pricing';
import Footer from './components/Footer';
import ProductHub from './components/landing/ProductHub';
import LoginModal from './components/LoginModal';
import PrivacyPolicy from './components/PrivacyPolicy';
import TermsOfService from './components/TermsOfService';
import { ChatProvider } from './context/ChatContext';
import { UserProvider } from './context/UserContext';
import ProtectedRoute from './components/layout/ProtectedRoute';
import AppShell from './components/layout/AppShell';
import ChatPage from './components/chat/ChatPage';
import DashboardPage from './components/dashboard/DashboardPage';
import SettingsPage from './components/settings/SettingsPage';
import SettingsGeneral from './components/settings/SettingsGeneral';
import SettingsAccount from './components/settings/SettingsAccount';
import SettingsCompany from './components/settings/SettingsCompany';
import DocumentWorkspace from './components/settings/documents/DocumentWorkspace';
import ForecastPage from './components/forecast/ForecastPage';
import AdminPage from './components/admin/AdminPage';
import AlertsPage from './components/alerts/AlertsPage';
import StudioHome from './pages/StudioHome';
import StudioProjectPage from './components/studio/StudioProject';
import PaymentModal from './components/PaymentModal';
import SubscriptionPage from './components/settings/SubscriptionPage';
import type { User } from './types';
import { trackPageView } from './utils/analytics';
import {
  consumePostLoginTarget,
  getCurrentGoogleUser,
  isGoogleOAuthConfigured,
  signInWithGoogle,
  signInWithKakao,
  signOutGoogleUser,
} from './services/authService';

function AppRoutes() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [user, setUser] = useState<User | null>(null);
  const [authLoading, setAuthLoading] = useState(true);
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
        const postLoginTarget = consumePostLoginTarget();
        if (postLoginTarget) {
          navigate(postLoginTarget, { replace: true });
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : '로그인 상태 확인 중 오류가 발생했습니다.';
        setAuthError(message);
      } finally {
        setAuthLoading(false);
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

  const handleStartStudio = useCallback(() => {
    setAuthError('');
    if (user) {
      navigate('/studio');
      return;
    }
    // Store redirect target for post-login
    sessionStorage.setItem('kira_post_login_target', '/studio');
    setIsLoginModalOpen(true);
  }, [user, navigate]);

  const handleAlertSetup = useCallback(() => {
    setAuthError('');
    if (user) {
      navigate('/alerts');
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

  const handleKakaoLogin = async (): Promise<void> => {
    setAuthError('');
    try {
      await signInWithKakao();
    } catch (error) {
      const message = error instanceof Error ? error.message : '카카오 로그인 시작에 실패했습니다.';
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
      return; // 로그아웃 실패 시 정리/리디렉션 하지 않음
    }
    // Security: clear user-scoped storage (keep legacy keys for migration on next login)
    try {
      const uid = user?.id;
      if (uid) {
        localStorage.removeItem(`kira_conversations_${uid}`);
        localStorage.removeItem(`kira_active_conversation_${uid}`);
      }
      // NOTE: Do NOT clear legacy keys (kira_conversations, kirabot_alert_session_id)
      // They are needed for migration to user-scoped keys on next login.
    } catch { /* ignore */ }
    window.location.replace('/');
  };

  const scrollToSection = useCallback((id: string) => {
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    } else if (window.location.pathname !== '/') {
      navigate('/');
      requestAnimationFrame(() => {
        setTimeout(() => {
          document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
      });
    }
  }, [navigate]);

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
        <Hero onStart={handleStart} onStartStudio={isStudioVisible() ? handleStartStudio : undefined} onAlertSetup={handleAlertSetup} />
        <ProductHub
          onNavigateChat={handleStart}
          onNavigateStudio={handleStartStudio}
          onNavigateForecast={() => { if (user) navigate('/forecast'); else setIsLoginModalOpen(true); }}
          onNavigateCompany={() => { if (user) navigate('/settings/company'); else setIsLoginModalOpen(true); }}
          studioEnabled={isStudioVisible()}
        />
        <HowItWorks />
        <Marquee text="/ 검색 / 분석 / 판단 / 생성 / 학습 /" />
        <Solutions />
        <Marquee text="FULL LIFECYCLE / FULL LIFECYCLE / FULL LIFECYCLE / FULL LIFECYCLE /" bg="bg-gray-100" duration={60} />
        <PackageSection />
        <Marquee text="/ 생성 / 학습 / 진화 / 반복 /" bg="bg-[#0000FF]" textColor="text-white" />
        <Features />
        <Pricing
          onSelectPro={() => {
            if (user) {
              setIsPaymentModalOpen(true);
            } else {
              setIsLoginModalOpen(true);
            }
          }}
          onStart={handleStart}
        />
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
          <ProtectedRoute user={user} authLoading={authLoading}>
            <UserProvider value={user}>
              <ChatProvider>
                <AppShell user={user} onLogout={() => void handleLogout()} />
              </ChatProvider>
            </UserProvider>
          </ProtectedRoute>
        }>
          <Route path="/chat" element={<ChatPage user={user} />} />
          <Route path="/studio" element={<StudioHome />} />
          <Route path="/studio/projects/:projectId" element={<StudioProjectPage />} />
          <Route path="/alerts" element={<AlertsPage />} />
          <Route path="/forecast" element={<ForecastPage />} />
          <Route path="/admin" element={user?.isAdmin ? <AdminPage /> : <Navigate to="/chat" replace />} />

          {/* Settings nested routes */}
          <Route path="/settings" element={<SettingsPage />}>
            <Route index element={<Navigate to="general" replace />} />
            <Route path="general" element={<SettingsGeneral user={user} />} />
            <Route path="company" element={<SettingsCompany />} />
            <Route path="usage" element={<DashboardPage />} />
            <Route path="subscription" element={<SubscriptionPage />} />
            <Route path="account" element={<SettingsAccount user={user} onLogout={() => void handleLogout()} />} />
            <Route path="documents" element={<DocumentWorkspace />} />
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
        onKakaoLogin={handleKakaoLogin}
        authError={authError}
        onOpenPrivacy={() => { setIsLoginModalOpen(false); navigate('/privacy'); }}
        onOpenTerms={() => { setIsLoginModalOpen(false); navigate('/terms'); }}
      />

      <PaymentModal
        isOpen={isPaymentModalOpen}
        onClose={() => setIsPaymentModalOpen(false)}
        onSuccess={() => {
          setIsPaymentModalOpen(false);
          navigate('/settings/subscription');
        }}
        plan="pro"
        username={user?.email}
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
