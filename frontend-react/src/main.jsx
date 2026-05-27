import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { AuthProvider } from './context/AuthContext';
import { DbModeProvider } from './context/DbModeContext';
import App from './App';
import './styles/index.css';

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <DbModeProvider>
      <AuthProvider>
        <App />
      </AuthProvider>
    </DbModeProvider>
  </StrictMode>
);
