/**
 * Authentication Context
 * 
 * Provides authentication state and methods throughout the React application.
 * Integrates with the authService to maintain authentication state.
 */

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import authService, { JWTClaims, LoginCredentials } from '../services/authService';

interface AuthContextType {
  user: JWTClaims | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (credentials: LoginCredentials) => Promise<void>;
  logout: () => void;
  refreshAuth: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

interface AuthProviderProps {
  children: ReactNode;
}

export const AuthProvider: React.FC<AuthProviderProps> = ({ children }) => {
  const [user, setUser] = useState<JWTClaims | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Initialize authentication state on mount
  useEffect(() => {
    const initializeAuth = () => {
      try {
        if (authService.isAuthenticated()) {
          const claims = authService.getUserClaims();
          setUser(claims);
        } else {
          setUser(null);
        }
      } catch (error) {
        console.error('Error initializing auth:', error);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    };

    initializeAuth();
  }, []);

  // Check token expiration periodically
  useEffect(() => {
    const checkTokenExpiration = () => {
      if (user && !authService.isAuthenticated()) {
        // Token expired, logout user
        handleLogout();
      }
    };

    // Check every minute
    const interval = setInterval(checkTokenExpiration, 60000);
    
    return () => clearInterval(interval);
  }, [user]);

  const handleLogin = async (credentials: LoginCredentials): Promise<void> => {
    setIsLoading(true);
    try {
      const response = await authService.login(credentials);
      setUser(response.user);
    } catch (error) {
      console.error('Login failed:', error);
      throw error;
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogout = (): void => {
    authService.logout();
    setUser(null);
  };

  const refreshAuth = (): void => {
    try {
      if (authService.isAuthenticated()) {
        const claims = authService.getUserClaims();
        setUser(claims);
      } else {
        setUser(null);
      }
    } catch (error) {
      console.error('Error refreshing auth:', error);
      setUser(null);
    }
  };

  const value: AuthContextType = {
    user,
    isAuthenticated: !!user && authService.isAuthenticated(),
    isLoading,
    login: handleLogin,
    logout: handleLogout,
    refreshAuth,
  };

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
};

// Custom hook to use authentication context
export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;