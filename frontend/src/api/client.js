import axios from 'axios';
import { showToast } from '../lib/toast';

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  withCredentials: true,
});

let accessToken = null;
export const setAccessToken = (token) => { accessToken = token; };

api.interceptors.request.use((config) => {
  if (accessToken) config.headers.Authorization = `Bearer ${accessToken}`;
  return config;
});

// A single shared refresh promise prevents a burst of 401 responses from
// creating multiple refresh-token rotations at the same time.
let refreshPromise = null;
function isMutation(config) {
  return ['post', 'put', 'patch', 'delete'].includes((config?.method || '').toLowerCase());
}

function mutationSuccessMessage(config) {
  const url = String(config?.url || '');
  if (url.includes('/auth/login')) return 'Successfully signed in.';
  if (url.includes('/auth/register')) return 'Account created successfully.';
  if (url.includes('/auth/forgot-password')) return 'Password reset instructions sent.';
  if (url.includes('/auth/reset-password')) return 'Password updated successfully.';
  const method = (config?.method || '').toLowerCase();
  if (method === 'post') return 'Successfully added.';
  if (method === 'delete') return 'Successfully deleted.';
  return 'Successfully updated.';
}

function mutationErrorMessage(error) {
  return error?.response?.data?.error?.message
    || error?.response?.data?.detail
    || error?.message
    || 'The request could not be completed.';
}

api.interceptors.response.use(
  (response) => {
    if (isMutation(response.config) && !response.config?.skipGlobalToast) {
      showToast.success(mutationSuccessMessage(response.config));
    }
    return response;
  },
  async (error) => {
    if (isMutation(error.config) && !error.config?.skipGlobalToast && error.response?.status !== 401) {
      showToast.error(mutationErrorMessage(error));
    }
    const original = error.config;
    if (!original || error.response?.status !== 401 || original._retry || original.url?.includes('/auth/refresh')) {
      return Promise.reject(error);
    }
    original._retry = true;
    try {
      refreshPromise ||= axios.post(`${api.defaults.baseURL}/auth/refresh`, {}, { withCredentials: true });
      const refreshed = await refreshPromise;
      setAccessToken(refreshed.data.access_token);
      return api(original);
    } catch (refreshError) {
      setAccessToken(null);
      // /auth/me is used during application bootstrap. A missing/expired
      // refresh cookie means the visitor is simply anonymous; do not turn a
      // public page into a forced redirect to /login.
      const isBootstrapMe = original.url?.replace(/^https?:\/\/[^/]+/, '').includes('/auth/me');
      if (!isBootstrapMe && window.location.pathname !== '/login') {
        const target = `${window.location.pathname}${window.location.search}`;
        window.location.assign(`/login?from=${encodeURIComponent(target)}`);
      }
      return Promise.reject(refreshError);
    } finally {
      refreshPromise = null;
    }
  }
);
