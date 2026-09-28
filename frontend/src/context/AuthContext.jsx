import { createContext, useContext, useEffect, useState } from 'react';
import { api, setAccessToken } from '../api/client';

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        // The refresh token is stored in an HttpOnly cookie, so the browser
        // can restore the short-lived access token after a page refresh.
        // Calling refresh explicitly here makes the session restoration
        // predictable before protected pages start their API requests.
        const refreshed = await api.post('/auth/refresh');
        setAccessToken(refreshed.data.access_token);

        const response = await api.get('/auth/me');
        if (!cancelled) setUser(response.data);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    restoreSession();
    return () => { cancelled = true; };
  }, []);

  const login = async (data) => {
    const response = await api.post('/auth/login', data);
    setAccessToken(response.data.access_token);
    setUser(response.data.user);
    return response.data;
  };

  const logout = async () => {
    try { await api.post('/auth/logout'); } finally {
      setAccessToken(null);
      setUser(null);
    }
  };

  return <AuthContext.Provider value={{ user, loading, login, logout, setUser }}>{children}</AuthContext.Provider>;
}
