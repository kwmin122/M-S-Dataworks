import React from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import { ArrowLeft, User as UserIcon, Building2, BarChart3, Shield, CreditCard, FileText } from 'lucide-react';
import { pageTransition } from '../../utils/animations';
import { useDocumentTitle } from '../../hooks/useDocumentTitle';

const tabs = [
  { path: 'general', label: '일반', icon: UserIcon },
  { path: 'company', label: '회사 정보', icon: Building2 },
  { path: 'usage', label: '사용량', icon: BarChart3 },
  { path: 'documents', label: '문서 관리', icon: FileText },
  { path: 'subscription', label: '구독', icon: CreditCard },
  { path: 'account', label: '계정', icon: Shield },
];

const SettingsPage: React.FC = () => {
  useDocumentTitle('설정');
  const navigate = useNavigate();

  return (
    <motion.div
      className="flex-1 flex flex-col h-full bg-white overflow-hidden"
      variants={pageTransition}
      initial="initial"
      animate="animate"
      exit="exit"
    >
      {/* Header */}
      <div className="flex items-center gap-3 px-6 py-4 border-b border-slate-200">
        <button
          type="button"
          onClick={() => navigate('/chat')}
          className="flex items-center gap-1.5 text-sm text-slate-600 hover:text-slate-900 transition-colors"
        >
          <ArrowLeft size={16} />
          설정
        </button>
      </div>

      {/* Body: left tabs + right content */}
      <div className="flex flex-1 min-h-0">
        {/* Left tab nav */}
        <nav className="w-48 shrink-0 border-r border-slate-200 py-4 px-3 space-y-0.5">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <NavLink
                key={tab.path}
                to={tab.path}
                className={({ isActive }) =>
                  `flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                    isActive
                      ? 'bg-kira-50 text-kira-700 font-semibold border-l-2 border-kira-500 -ml-px'
                      : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
                  }`
                }
              >
                <Icon size={16} className="shrink-0" />
                {tab.label}
              </NavLink>
            );
          })}
        </nav>

        {/* Right content */}
        <div className="flex-1 overflow-y-auto p-6 lg:p-8">
          <div className="max-w-2xl mx-auto">
            <Outlet />
          </div>
        </div>
      </div>
    </motion.div>
  );
};

export default SettingsPage;
