import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { login as loginRequest } from "@/api/auth";
import { clearStoredToken, getStoredToken, setStoredToken, UNAUTHORIZED_EVENT } from "@/api/client";

interface AuthContextValue {
  isAuthenticated: boolean;
  token: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setToken] = useState<string | null>(() => getStoredToken());

  const logout = useCallback(() => {
    clearStoredToken();
    setToken(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await loginRequest(username, password);
    setStoredToken(response.access_token);
    setToken(response.access_token);
  }, []);

  useEffect(() => {
    window.addEventListener(UNAUTHORIZED_EVENT, logout);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, logout);
  }, [logout]);

  return (
    <AuthContext.Provider value={{ isAuthenticated: token !== null, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (ctx === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return ctx;
}
