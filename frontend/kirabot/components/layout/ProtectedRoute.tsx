import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { User } from '../../types';

interface ProtectedRouteProps {
  user: User | null;
  children: React.ReactNode;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ user, children }) => {
  const location = useLocation();
  if (!user) {
    return <Navigate to={`/?login=1&redirect=${encodeURIComponent(location.pathname)}`} replace />;
  }
  return <>{children}</>;
};

export default ProtectedRoute;
