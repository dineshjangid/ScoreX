import { useAuth } from "../AuthContext";

export default function UserMenu() {
  const { user, logout } = useAuth();

  return (
    <div className="user-menu">
      <span className="muted">
        {user.username} <span className="badge">{user.role}</span>
      </span>
      <button type="button" onClick={() => logout()}>
        Log out
      </button>
    </div>
  );
}
