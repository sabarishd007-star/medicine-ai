import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  createUserWithEmailAndPassword,
  GoogleAuthProvider,
  onAuthStateChanged,
  sendPasswordResetEmail,
  signInWithEmailAndPassword,
  signInWithPopup,
  signInWithRedirect,
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
        // Existing users load their profile. A user who never completed
        // registration (e.g. first-time Google sign-in) is auto-created by
        // the backend login endpoint instead.
        let profile;
        try {
          profile = await authApi.me();
        } catch {
          profile = await authApi.login({ idToken: token });
        }
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

  const loginWithGoogle = useCallback(async () => {
    if (!firebaseConfigured) {
      throw new Error('Firebase is not configured. Add your keys to frontend/.env.');
    }
    const provider = new GoogleAuthProvider();
    let credential;
    try {
      credential = await signInWithPopup(auth, provider);
    } catch (error) {
      // Popup blockers hide the sign-in window. Fall back to a full-page
      // redirect; when the user returns, onAuthStateChanged completes sign-in.
      if (error?.code === 'auth/popup-blocked' || error?.code === 'auth/popup-closed-by-user') {
        await signInWithRedirect(auth, provider);
        return null;
      }
      throw error;
    }
    const token = await credential.user.getIdToken();
    tokenStore.set(token);
    // The backend login endpoint auto-creates the local account when missing.
    const profile = await authApi.login({ idToken: token });
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
    () => ({ user, loading, login, register, loginWithGoogle, logout, refresh, resetPassword }),
    [user, loading, login, register, loginWithGoogle, logout, refresh, resetPassword],
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
