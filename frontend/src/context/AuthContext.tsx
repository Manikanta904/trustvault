import React, { useEffect, useState, useCallback } from 'react';
import type { User } from '../types';
import { getMeApi, loginApi, registerApi, type RegisterPayload } from '../api/auth';
import { AuthContext } from './auth-context';

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('trustvault_token'));
  const [isLoading, setIsLoading] = useState<boolean>(true);

  const logout = useCallback(() => {
    localStorage.removeItem('trustvault_token');
    setToken(null);
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<User | null> => {
    const currentToken = localStorage.getItem('trustvault_token');
    if (!currentToken) {
      setUser(null);
      return null;
    }
    try {
      const userData = await getMeApi();
      setUser(userData);
      return userData;
    } catch {
      logout();
      return null;
    }
  }, [logout]);

  useEffect(() => {
    let isMounted = true;

    async function initAuth() {
      const storedToken = localStorage.getItem('trustvault_token');
      if (storedToken) {
        try {
          const userData = await getMeApi();
          if (isMounted) {
            setUser(userData);
            setToken(storedToken);
          }
        } catch {
          if (isMounted) {
            logout();
          }
        }
      }
      if (isMounted) {
        setIsLoading(false);
      }
    }

    initAuth();

    const handleUnauthorized = () => {
      logout();
    };
    window.addEventListener('auth:unauthorized', handleUnauthorized);

    return () => {
      isMounted = false;
      window.removeEventListener('auth:unauthorized', handleUnauthorized);
    };
  }, [logout]);

  const login = async (email: string, password: string): Promise<User> => {
    const data = await loginApi(email, password);
    localStorage.setItem('trustvault_token', data.access_token);
    setToken(data.access_token);
    const currentUser = await getMeApi();
    setUser(currentUser);
    return currentUser;
  };

  const register = async (payload: RegisterPayload): Promise<User> => {
    const registeredUser = await registerApi(payload);
    // After registration, automatically log in the new user
    await login(payload.email, payload.password);
    return registeredUser;
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: !!user && !!token,
        login,
        register,
        logout,
        refreshUser,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
