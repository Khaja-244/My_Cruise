// Global toast event helper.
// Keeping this outside React lets API/services trigger the same notification UI
// without creating circular imports between the API client and React context.
export function showToast(type, message, options = {}) {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new CustomEvent('my-cruise:toast', {
    detail: {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      type,
      message,
      duration: options.duration ?? 3500,
    },
  }));
}

showToast.success = (message, options) => showToast('success', message, options);
showToast.error = (message, options) => showToast('error', message, options);
showToast.warning = (message, options) => showToast('warning', message, options);
showToast.info = (message, options) => showToast('info', message, options);
