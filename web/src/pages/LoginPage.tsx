import { useState } from "react";
import { api } from "../api";
import type { AuthUser, UserRole } from "../api";

interface Props {
  onLoggedIn: (user: AuthUser) => void;
}

const ROLES: { value: UserRole; label: string }[] = [
  { value: "analyst", label: "Analyst" },
  { value: "validator", label: "Validator" },
  { value: "approver", label: "Approver" },
];

export default function LoginPage({ onLoggedIn }: Props) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("analyst");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const user = mode === "login" ? await api.login(username, password) : await api.register(username, password, role);
      onLoggedIn(user);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="home-shell" style={{ maxWidth: 420 }}>
      <header className="home-header">
        <h1 className="page-title">ScoreX</h1>
        <p className="muted">Sign in to build, validate, and export credit risk scorecards.</p>
      </header>

      <section className="card home-module">
        <div className="button-row" style={{ marginBottom: 16 }}>
          <button type="button" className={mode === "login" ? "mode-active" : ""} onClick={() => setMode("login")}>
            Log in
          </button>
          <button type="button" className={mode === "register" ? "mode-active" : ""} onClick={() => setMode("register")}>
            Register
          </button>
        </div>

        <form onSubmit={handleSubmit} className="new-project-form">
          <label>
            Username
            <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
          </label>
          <label>
            Password
            <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </label>

          {mode === "register" && (
            <div className="radio-field">
              <span className="radio-field-label">Role</span>
              <div className="radio-group">
                {ROLES.map((r) => (
                  <label key={r.value} className={`radio-card ${role === r.value ? "selected" : ""}`}>
                    <input type="radio" name="role" value={r.value} checked={role === r.value} onChange={() => setRole(r.value)} />
                    <span className="radio-card-title">{r.label}</span>
                  </label>
                ))}
              </div>
            </div>
          )}

          {error && <p className="error">{error}</p>}

          <button type="submit" disabled={busy || !username || !password}>
            {mode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </section>
    </div>
  );
}
