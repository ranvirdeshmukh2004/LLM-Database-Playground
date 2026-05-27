import { createContext, useContext, useState, useCallback } from 'react';
import { getDbMode, setDbMode as persistDbMode, clearTokens } from '../api/client';

const DbModeContext = createContext(null);

const INFO = {
  supabase: 'GoTrue auth · Row-Level Security · Full Supabase stack',
  plain: 'App-managed auth (bcrypt + JWT) · No RLS · Lightweight',
};

export function DbModeProvider({ children }) {
  const [dbMode, setDbModeState] = useState(getDbMode());

  const setDbMode = useCallback((mode) => {
    persistDbMode(mode);
    clearTokens();
    setDbModeState(mode);
  }, []);

  const info = INFO[dbMode] || INFO.supabase;

  return (
    <DbModeContext.Provider value={{ dbMode, setDbMode, info }}>
      {children}
    </DbModeContext.Provider>
  );
}

export function useDbMode() {
  const ctx = useContext(DbModeContext);
  if (!ctx) throw new Error('useDbMode must be used inside DbModeProvider');
  return ctx;
}
