import { useState, useEffect, useCallback } from 'react';

const TOAST_DURATION = 4000;
let toastId = 0;

// Global toast state (simple pub-sub)
let listeners = [];
let toasts = [];

function notify() { listeners.forEach(fn => fn([...toasts])); }

export function showToast(message, type = 'info') {
  const id = ++toastId;
  toasts.push({ id, message, type });
  notify();
  setTimeout(() => {
    toasts = toasts.filter(t => t.id !== id);
    notify();
  }, TOAST_DURATION);
}

export default function Toast() {
  const [items, setItems] = useState([]);

  useEffect(() => {
    listeners.push(setItems);
    return () => { listeners = listeners.filter(fn => fn !== setItems); };
  }, []);

  if (!items.length) return null;

  return (
    <div id="toast-container">
      {items.map(t => (
        <div key={t.id} className={`toast ${t.type}`}>
          {t.message}
        </div>
      ))}
    </div>
  );
}
