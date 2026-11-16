import { NavLink, Navigate, Outlet, useLocation } from "react-router";
import type { ReactNode } from "react";
import { useAuth } from "../auth/AuthContext";
import type { Role } from "../api/types";
import { label } from "../utils/format";
import { Loading } from "./ui";

const STAFF: Role[] = ["ADMIN", "BIBLIOTHECAIRE"];

const LINKS: { to: string; text: string; roles: Role[] }[] = [
  { to: "/dashboard", text: "Tableau de bord", roles: STAFF },
  { to: "/catalogue", text: "Catalogue", roles: ["ADMIN", "BIBLIOTHECAIRE", "ADHERENT"] },
  { to: "/emprunts", text: "Emprunts", roles: ["ADMIN", "BIBLIOTHECAIRE", "ADHERENT"] },
  { to: "/reservations", text: "Réservations", roles: ["ADMIN", "BIBLIOTHECAIRE", "ADHERENT"] },
  { to: "/penalites", text: "Pénalités", roles: ["ADMIN", "BIBLIOTHECAIRE", "ADHERENT"] },
  { to: "/referentiels", text: "Auteurs & catégories", roles: STAFF },
  { to: "/utilisateurs", text: "Utilisateurs", roles: STAFF },
  { to: "/audit", text: "Journal d'audit", roles: ["ADMIN"] },
];

export function Layout() {
  const { user, logout } = useAuth();
  if (!user) return null;
  return (
    <>
      <a className="skip-link" href="#contenu">
        Aller au contenu
      </a>
      <header className="topbar">
        <span className="brand">📚 BiblioTrack</span>
        <nav aria-label="Navigation principale">
          <ul>
            {LINKS.filter((l) => l.roles.includes(user.role)).map((l) => (
              <li key={l.to}>
                <NavLink to={l.to}>{l.text}</NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <div className="session">
          <span data-testid="current-user">
            {user.full_name} <small>({label(user.role)})</small>
          </span>
          <button type="button" className="secondary" onClick={logout}>
            Se déconnecter
          </button>
        </div>
      </header>
      <main id="contenu" tabIndex={-1}>
        <Outlet />
      </main>
    </>
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
      <section>
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
