import { createContext, useContext, useEffect, useState } from "react";
import { api } from "./api";
import type { AuthUser } from "./api";
import LoginPage from "./pages/LoginPage";

interface AuthContextValue {
  user: AuthUser;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null | undefined>(undefined);

  useEffect(() => {
    api
      .getMe()
      .then(setUser)
      .catch(() => setUser(null));
  }, []);

  async function logout() {
    await api.logout();
    setUser(null);
  }

  if (user === undefined) {
    return <p className="page-padding">Loading…</p>;
  }

  if (user === null) {
    return <LoginPage onLoggedIn={setUser} />;
  }

  return <AuthContext.Provider value={{ user, logout }}>{children}</AuthContext.Provider>;
}
