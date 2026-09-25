import { useEffect, useRef, useState } from "react";
import { useAuth } from "../AuthContext";

// Compact avatar + name trigger with a small popover for role and log out.
// `placement` lets the sidebar footer open it upwards.
export default function UserMenu({ placement = "down" }: { placement?: "down" | "up" }) {
  const { user, logout } = useAuth();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: PointerEvent) {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    }
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="user-menu" ref={rootRef}>
      <button
        type="button"
        className="user-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
      >
        <span className="avatar" aria-hidden="true">
          {user.username.charAt(0).toUpperCase()}
        </span>
        <span className="user-menu-name">{user.username}</span>
      </button>
      {open && (
        <div className={`popover-menu user-menu-popover ${placement === "up" ? "open-up" : ""}`} role="menu">
          <div className="popover-menu-header">
            <strong>{user.username}</strong>
            <span className="badge">{user.role}</span>
          </div>
          <button type="button" role="menuitem" className="popover-menu-item" onClick={() => logout()}>
            Log out
          </button>
        </div>
      )}
    </div>
  );
}
