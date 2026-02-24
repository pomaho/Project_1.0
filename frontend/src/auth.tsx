import { createContext, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { getMe, type MeResponse } from "./api/auth";

export type Tokens = {
  accessToken: string;
  refreshToken: string;
};

type AuthContextValue = {
  tokens: Tokens | null;
  setTokens: (tokens: Tokens | null) => void;
  logout: () => void;
  user: MeResponse | null;
};

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

const STORAGE_KEY = "photo_search_tokens";

function loadTokens(): Tokens | null {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Tokens;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [tokens, setTokensState] = useState<Tokens | null>(() => loadTokens());
  const [user, setUser] = useState<MeResponse | null>(null);

  const setTokens = (next: Tokens | null) => {
    setTokensState(next);
    if (next) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  };

  useEffect(() => {
    let active = true;
    if (!tokens) {
      setUser(null);
      return () => {
        active = false;
      };
    }
    getMe()
      .then((profile) => {
        if (active) setUser(profile);
      })
      .catch(() => {
        if (active) setUser(null);
      });
    return () => {
      active = false;
    };
  }, [tokens]);

  const logout = () => {
    setUser(null);
    setTokens(null);
  };
  const value = useMemo(() => ({ tokens, setTokens, logout, user }), [tokens, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("AuthProvider missing");
  }
  return ctx;
}
