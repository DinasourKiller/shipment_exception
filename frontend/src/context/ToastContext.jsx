import React, { createContext, useContext, useState, useCallback } from 'react';

const ToastContext = createContext(null);

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const showToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now() + Math.random().toString(36).substring(2, 6);
    const newToast = { id, message, type };

    setToasts((prev) => [...prev, newToast]);

    if (duration > 0) {
      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, duration);
    }
  }, []);

  const removeToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  return (
    <ToastContext.Provider value={{ showToast, removeToast }}>
      {children}
      <div id="toast-container" style={{ position: 'fixed', top: 20, right: 20, zIndex: 9999, display: 'flex', flexDirection: 'column', gap: 8 }}>
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`toast toast-${toast.type}`}
            style={{
              minWidth: 280,
              maxWidth: 420,
              padding: '12px 16px',
              borderRadius: 8,
              background: toast.type === 'error' ? '#FEF2F2' : toast.type === 'success' ? '#F0FDF4' : toast.type === 'warning' ? '#FFFBEB' : '#EFF6FF',
              color: toast.type === 'error' ? '#991B1B' : toast.type === 'success' ? '#166534' : toast.type === 'warning' ? '#92400E' : '#1E40AF',
              border: `1px solid ${toast.type === 'error' ? '#FCA5A5' : toast.type === 'success' ? '#86EFAC' : toast.type === 'warning' ? '#FCD34D' : '#93C5FD'}`,
              boxShadow: '0 4px 12px rgba(0,0,0,0.08)',
              fontSize: '13px',
              fontWeight: 500,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              animation: 'fadeIn 0.2s ease',
            }}
          >
            <span>{toast.message}</span>
            <button
              onClick={() => removeToast(toast.id)}
              style={{
                background: 'none',
                border: 'none',
                cursor: 'pointer',
                marginLeft: 12,
                color: 'inherit',
                fontWeight: 'bold',
              }}
            >
              ×
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within ToastProvider');
  }
  return context;
}
