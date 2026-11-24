import { NavLink, Navigate, Outlet, useLocation } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { label } from "../utils/format";
import { Icon } from "./icons";
import type { IconName } from "./icons";
import { Loading } from "./ui";

const STAFF: Role[] = ["ADMIN", "BIBLIOTHECAIRE"];
const ALL: Role[] = ["ADMIN", "BIBLIOTHECAIRE", "ADHERENT"];

const LINKS: { to: string; text: string; icon: IconName; roles: Role[] }[] = [
  { to: "/dashboard", text: "Tableau de bord", icon: "dashboard", roles: STAFF },
  { to: "/catalogue", text: "Catalogue", icon: "book", roles: ALL },
  { to: "/emprunts", text: "Emprunts", icon: "loan", roles: ALL },
  { to: "/reservations", text: "Réservations", icon: "bookmark", roles: ALL },
  { to: "/penalites", text: "Pénalités", icon: "coin", roles: ALL },
  { to: "/referentiels", text: "Auteurs & catégories", icon: "tag", roles: STAFF },
  { to: "/utilisateurs", text: "Utilisateurs", icon: "users", roles: STAFF },
  { to: "/audit", text: "Journal d'audit", icon: "shield", roles: ["ADMIN"] },
];

function initials(name: string): string {
  return name
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? "")
    .join("");
}

export function Layout() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#contenu">
        Aller au contenu
      </a>
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Icon name="book" size={18} />
          </span>
          <span className="brand-name">BiblioTrack</span>
        </div>
        <nav aria-label="Navigation principale">
          <ul>
            {LINKS.filter((l) => l.roles.includes(user.role)).map((l) => (
              <li key={l.to}>
                <NavLink to={l.to}>
                  <Icon name={l.icon} />
                  <span>{l.text}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="session">
          <span className="avatar" aria-hidden="true">
            {initials(user.full_name)}
          </span>
          <span className="session-user" data-testid="current-user">
            {user.full_name} <small>({label(user.role)})</small>
          </span>
          <button type="button" className="logout" onClick={logout}>
            <Icon name="logout" size={16} />
            Se déconnecter
          </button>
        </div>
      </aside>
      <main id="contenu" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}

/** Garde de route : authentification puis rôle. */
export function RequireAuth({ roles, children }: { roles?: Role[]; children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Loading />;
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  if (roles && !roles.includes(user.role)) {
    return (
      <section className="empty-state">
        <Icon name="shield" size={40} />
        <h1>Accès refusé</h1>
        <p>Votre profil ({label(user.role)}) ne permet pas d'accéder à cette page.</p>
      </section>
    );
  }
  return <>{children}</>;
}

export function homeFor(role: Role): string {
  return STAFF.includes(role) ? "/dashboard" : "/catalogue";
}
