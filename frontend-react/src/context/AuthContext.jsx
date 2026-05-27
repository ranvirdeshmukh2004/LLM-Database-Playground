import { createContext, useContext, useState, useCallback } from 'react';
import { getAccessToken, getStoredUser, apiSignIn, apiSignUp, apiSignOut, clearTokens, setStoredUser } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(getStoredUser());
  const [isAuthenticated, setIsAuthenticated] = useState(!!getAccessToken());

  const login = useCallback(async (email, password) => {
    const data = await apiSignIn(email, password);
    setUser(data.user);
    setIsAuthenticated(true);
    return data;
  }, []);

  const signup = useCallback(async (email, password, displayName) => {
    const data = await apiSignUp(email, password, displayName);
    setUser(data.user);
    setIsAuthenticated(true);
    return data;
  }, []);

  const logout = useCallback(async () => {
    await apiSignOut();
    setUser(null);
    setIsAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ user, isAuthenticated, login, signup, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider');
  return ctx;
}
