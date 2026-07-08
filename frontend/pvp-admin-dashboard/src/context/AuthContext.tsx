import React, { createContext, useContext, useState, useEffect } from 'react';
import { jwtDecode } from 'jwt-decode';
import type { AdminTokenPayload } from '../types/auth';

interface AuthContextType {
  isAuthenticated: boolean;
  isLoading: boolean;
  adminName: string | null;
  login: (token: string) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [adminName, setAdminName] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const verifyAndHydrateToken = (token: string | null) => {
    if (!token) return logout();

    try {
      const decoded = jwtDecode<AdminTokenPayload>(token);
      const currentTime = Date.now() / 1000;

      // Verify expiration and scope requirements
      if (decoded.exp < currentTime || decoded.type !== 'admin_access' || !decoded.is_superuser) {
        return logout();
      }

      setAdminName(decoded.sub);
      setIsAuthenticated(true);
    } catch (error) {
      logout();
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    const token = localStorage.getItem('admin_token');
    verifyAndHydrateToken(token);
  }, []);

  const login = (token: string) => {
    localStorage.setItem('admin_token', token);
    verifyAndHydrateToken(token);
  };

  const logout = () => {
    localStorage.removeItem('admin_token');
    setIsAuthenticated(false);
    setAdminName(null);
    setIsLoading(false);
  };

  return (
    <AuthContext.Provider value={{ isAuthenticated, isLoading, adminName, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside an AuthProvider');
  return context;
};