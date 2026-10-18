import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { api, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

type AuthStatus = "loading" | "authed" | "anon";

type AuthContextValue = {
  user: User | null;
  status: AuthStatus;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  // The session cookie is invisible to JavaScript, so we always ask the server who we are.
  const [status, setStatus] = useState<AuthStatus>("loading");

  const clearSession = useCallback(() => {
    setUser(null);
    setStatus("anon");
    queryClient.clear(); // never show one user's cached data to the next
  }, [queryClient]);

  // The API client calls this on any 401 (for example when the session expires).
  useEffect(() => {
    setUnauthorizedHandler(clearSession);
    return () => setUnauthorizedHandler(null);
  }, [clearSession]);

  useEffect(() => {
    let cancelled = false;
    api
      .me()
      .then((me) => {
        if (!cancelled) {
          setUser(me);
          setStatus("authed");
        }
      })
      .catch(() => {
        // Not signed in (a 401), or the server is unreachable.
        if (!cancelled) setStatus("anon");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    await api.login(email, password);
    const me = await api.me();
    setUser(me);
    setStatus("authed");
  }, []);

  const register = useCallback(
    async (email: string, password: string, fullName: string) => {
      await api.register({ email, password, full_name: fullName });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await api.logout(); // asks the server to clear the cookie
    } finally {
      clearSession();
    }
  }, [clearSession]);

  const value = useMemo(
    () => ({ user, status, login, register, logout }),
    [user, status, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside <AuthProvider>");
  return context;
}
