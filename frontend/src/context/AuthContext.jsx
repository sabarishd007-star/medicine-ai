import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { authApi, tokenStore } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, []);

  const applySession = useCallback((data) => {
    tokenStore.set(data.token);
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback(
    async (email, password) => applySession(await authApi.login({ email, password })),
    [applySession],
  );

  const register = useCallback(
    async (payload) => applySession(await authApi.register(payload)),
    [applySession],
  );

  const logout = useCallback(() => {
    tokenStore.clear();
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setUser(await authApi.me());
    } catch {
      /* stale session; the interceptor handles redirect */
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh }),
    [user, loading, login, register, logout, refresh],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used inside AuthProvider');
  }
  return context;
}
