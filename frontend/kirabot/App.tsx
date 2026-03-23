import React, { Suspense, useEffect, useState, useCallback } from 'react';
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
import PaymentModal from './components/PaymentModal';
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

// Lazy-loaded route components — split into separate chunks
const ChatPage = React.lazy(() => import('./components/chat/ChatPage'));
const DashboardPage = React.lazy(() => import('./components/dashboard/DashboardPage'));
const SettingsPage = React.lazy(() => import('./components/settings/SettingsPage'));
const SettingsGeneral = React.lazy(() => import('./components/settings/SettingsGeneral'));
const SettingsAccount = React.lazy(() => import('./components/settings/SettingsAccount'));
const SettingsCompany = React.lazy(() => import('./components/settings/SettingsCompany'));
const DocumentWorkspace = React.lazy(() => import('./components/settings/documents/DocumentWorkspace'));
const ForecastPage = React.lazy(() => import('./components/forecast/ForecastPage'));
const AdminPage = React.lazy(() => import('./components/admin/AdminPage'));
const AlertsPage = React.lazy(() => import('./components/alerts/AlertsPage'));
const StudioHome = React.lazy(() => import('./pages/StudioHome'));
const StudioProjectPage = React.lazy(() => import('./components/studio/StudioProject'));
const SubscriptionPage = React.lazy(() => import('./components/settings/SubscriptionPage'));

function LazyFallback() {
  return (
    <div className="flex items-center justify-center min-h-[200px]">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600" />
    </div>
  );
}

interface ErrorBoundaryState {
  hasError: boolean;
}

class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  ErrorBoundaryState
> {
  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(): ErrorBoundaryState {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo): void {
    console.error('[ErrorBoundary]', error, info.componentStack);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-slate-50 px-4 text-center">
          <h1 className="text-2xl font-bold text-slate-900 mb-2">
            문제가 발생했습니다
          </h1>
          <p className="text-slate-600 mb-6">
            페이지를 새로고침해주세요
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors"
          >
            새로고침
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

function AppRoutes() {
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false);
  const [isPaymentModalOpen, setIsPaymentModalOpen] = useState(false);
  const [selectedPlan, setSelectedPlan] = useState<'starter' | 'pro'>('pro');
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
              setSelectedPlan('pro');
              setIsPaymentModalOpen(true);
            } else {
              setIsLoginModalOpen(true);
            }
          }}
          onSelectStarter={() => {
            if (user) {
              setSelectedPlan('starter');
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
                <ErrorBoundary>
                  <Suspense fallback={<LazyFallback />}>
                    <AppShell user={user} onLogout={() => void handleLogout()} />
                  </Suspense>
                </ErrorBoundary>
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
        plan={selectedPlan}
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
