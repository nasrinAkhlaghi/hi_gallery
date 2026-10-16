import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { apiRequest, clearCsrfToken, logout as logoutRequest, type AuthUser } from "./api";

type AuthContextValue = {
  user: AuthUser | null;
  loading: boolean;
  setUser: (user: AuthUser | null) => void;
  reloadUser: () => Promise<AuthUser | null>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const reloadUser = useCallback(async () => {
    try {
      const current = await apiRequest<AuthUser>("/auth/me");
      setUser(current);
      return current;
    } catch {
      setUser(null);
      return null;
    }
  }, []);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        await apiRequest<{ csrf_token: string }>("/auth/csrf");
        const current = await apiRequest<AuthUser>("/auth/me");
        if (active) setUser(current);
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    const handleUnauthorized = () => setUser(null);
    window.addEventListener("hi-gallery:unauthorized", handleUnauthorized);
    return () => {
      active = false;
      window.removeEventListener("hi-gallery:unauthorized", handleUnauthorized);
    };
  }, []);

  const logout = useCallback(async () => {
    try {
      await logoutRequest();
    } finally {
      clearCsrfToken();
      setUser(null);
    }
  }, []);

  const value = useMemo(() => ({ user, loading, setUser, reloadUser, logout }), [user, loading, reloadUser, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used within AuthProvider");
  return context;
}
