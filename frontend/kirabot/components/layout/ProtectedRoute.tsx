import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { User } from '../../types';

interface ProtectedRouteProps {
  user: User | null;
  authLoading?: boolean;
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ user, authLoading, children }) => {
  const location = useLocation();
  if (authLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
      </div>
    );
  }
  if (!user) {
    return <Navigate to={`/?login=1&redirect=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <>{children}</>;
};

export default ProtectedRoute;
