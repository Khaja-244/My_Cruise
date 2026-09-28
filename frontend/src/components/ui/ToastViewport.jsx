import { useEffect, useState } from 'react';

const ICONS = {
  success: '✓',
  error: '!',
  warning: '!',
  info: 'i',
};

// A single viewport is mounted at the application root so every route gets
// the same feedback behavior without changing page layout or duplicating UI.
export default function ToastViewport() {
  const [toasts, setToasts] = useState([]);

  useEffect(() => {
    const onToast = event => {
      const toast = event.detail;
      setToasts(current => [...current, toast]);
      window.setTimeout(() => {
        setToasts(current => current.filter(item => item.id !== toast.id));
      }, toast.duration);
    };

    window.addEventListener('my-cruise:toast', onToast);
    return () => window.removeEventListener('my-cruise:toast', onToast);
  }, []);

  const dismiss = id => setToasts(current => current.filter(item => item.id !== id));

  return (
    <div className="toast-viewport" aria-live="polite" aria-atomic="false">
      {toasts.map(toast => (
        <div key={toast.id} className={`toast toast-${toast.type}`} role={toast.type === 'error' ? 'alert' : 'status'}>
          <span className="toast-icon" aria-hidden="true">{ICONS[toast.type] || 'i'}</span>
          <p>{toast.message}</p>
          <button type="button" className="toast-close" onClick={() => dismiss(toast.id)} aria-label="Dismiss notification">×</button>
        </div>
      ))}
    </div>
  );
}
