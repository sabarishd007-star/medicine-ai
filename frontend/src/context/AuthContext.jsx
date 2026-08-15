import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signOut,
} from 'firebase/auth';
import { auth, firebaseConfigured } from '../firebase';
import { authApi, tokenStore } from '../api/client';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  // Restore the session whenever Firebase confirms a signed-in user.
  useEffect(() => {
    if (!firebaseConfigured) {
      setLoading(false);
      return undefined;
    }
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (!firebaseUser) {
        tokenStore.clear();
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const token = await firebaseUser.getIdToken();
        tokenStore.set(token);
        const profile = await authApi.me();
        setUser(profile);
      } catch {
        tokenStore.clear();
        setUser(null);
      } finally {
        setLoading(false);
      }
    });
    return unsubscribe;
  }, []);

  const login = useCallback(async (email, password) => {
    if (!firebaseConfigured) {
      throw new Error('Firebase is not configured. Add your keys to frontend/.env.');
    }
    const credential = await signInWithEmailAndPassword(auth, email, password);
    const token = await credential.user.getIdToken();
    tokenStore.set(token);
    const profile = await authApi.me();
    setUser(profile);
    return profile;
  }, []);

  const register = useCallback(async ({ email, password, fullName }) => {
    if (!firebaseConfigured) {
      throw new Error('Firebase is not configured. Add your keys to frontend/.env.');
    }
    const credential = await createUserWithEmailAndPassword(auth, email, password);
    const token = await credential.user.getIdToken();
    tokenStore.set(token);
    const profile = await authApi.register({ idToken: token, fullName });
    setUser(profile);
    return profile;
  }, []);

  const logout = useCallback(async () => {
    if (firebaseConfigured) {
      await signOut(auth);
    }
    tokenStore.clear();
    setUser(null);
  }, []);

  const resetPassword = useCallback(async (email) => {
    if (!firebaseConfigured) {
      throw new Error('Firebase is not configured. Add your keys to frontend/.env.');
    }
    await sendPasswordResetEmail(auth, email);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setUser(await authApi.me());
    } catch {
      /* stale session; the interceptor handles redirect */
    }
  }, []);

  const value = useMemo(
    () => ({ user, loading, login, register, logout, refresh, resetPassword }),
    [user, loading, login, register, logout, refresh, resetPassword],
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
