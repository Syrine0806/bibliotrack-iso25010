import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";
import type { AuditEntry, Category, Dashboard, Page, Role, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, BarChart, Field, Loading, Pagination, StatCard, StatusBadge, useAction, useAsync } from "../components/ui";
import { formatDateTime, formatMoney, label } from "../utils/format";

// ------------------------------------------------------------------ tableau de bord
export function DashboardPage() {
  const [filters, setFilters] = useState({ date_from: "", date_to: "", category_id: "" });
  const categories = useAsync(() => api.get<Category[]>("/categories"), []);
  const dash = useAsync(() => api.get<Dashboard>("/dashboard", filters), [filters]);
  const d = dash.data;

  return (
    <section>
      <h1>Tableau de bord</h1>
      <form className="filters card" aria-label="Filtres du tableau de bord" onSubmit={(e) => e.preventDefault()}>
        <Field label="Du">
          {(id) => <input id={id} type="date" value={filters.date_from} onChange={(e) => setFilters({ ...filters, date_from: e.target.value })} />}
        </Field>
        <Field label="Au">
          {(id) => <input id={id} type="date" value={filters.date_to} onChange={(e) => setFilters({ ...filters, date_to: e.target.value })} />}
        </Field>
        <Field label="Catégorie">
          {(id) => (
            <select id={id} value={filters.category_id} onChange={(e) => setFilters({ ...filters, category_id: e.target.value })}>
              <option value="">Toutes</option>
              {categories.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          )}
        </Field>
      </form>
      <Alert kind="error">{dash.error}</Alert>
      {!d ? <Loading /> : (
        <>
          <div className="stats" data-testid="kpis">
            <StatCard title="Ouvrages" value={d.total_books} icon="book" />
            <StatCard title="Exemplaires disponibles" value={`${d.available_copies} / ${d.total_copies}`} tone="success" icon="check" />
            <StatCard title="Emprunts actifs" value={d.active_loans} tone="info" icon="loan" />
            <StatCard title="Emprunts en retard" value={d.overdue_loans} tone="danger" icon="alert" />
            <StatCard title="Emprunts sur la période" value={d.loans_in_period} icon="clock" />
            <StatCard title="Adhérents actifs" value={d.active_members} icon="users" />
            <StatCard title="Réservations en attente" value={d.pending_reservations} tone="warning" icon="bookmark" />
            <StatCard title="Pénalités impayées" value={formatMoney(d.unpaid_penalties_total)} tone="danger" icon="coin" />
          </div>
          <div className="two-cols">
            <BarChart title="Emprunts par mois" data={d.loans_by_month} />
            <BarChart title="Emprunts par catégorie" data={d.loans_by_category} />
            <BarChart title="Top 5 des ouvrages empruntés" data={d.top_books} />
            <BarChart title="Exemplaires par statut" data={d.copies_by_status} />
          </div>
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ utilisateurs
const ROLES: Role[] = ["ADHERENT", "BIBLIOTHECAIRE", "ADMIN"];

function NewUserForm({ onDone }: { onDone: () => void }) {
  const [form, setForm] = useState({ email: "", full_name: "", password: "", role: "ADHERENT" });
  const action = useAction();
  async function submit(e: FormEvent) {
    e.preventDefault();
    if (await action.run(() => api.post("/users", form), `Compte ${form.email} créé.`)) {
      setForm({ email: "", full_name: "", password: "", role: "ADHERENT" });
      onDone();
    }
  }
  return (
    <form className="card inline-form" onSubmit={submit} aria-labelledby="new-user-title">
      <h2 id="new-user-title">Nouveau compte</h2>
      <Field label="Nom complet">{(id) => <input id={id} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
      <Field label="E-mail">{(id) => <input id={id} type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />}</Field>
      <Field label="Mot de passe initial">{(id) => <input id={id} type="password" required minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />}</Field>
      <Field label="Rôle">
        {(id) => (
          <select id={id} value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            {ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
        )}
      </Field>
      <button type="submit" disabled={action.busy}>Créer</button>
      <Alert kind="error">{action.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
    </form>
  );
}

function UserActions({ user: u, editable, onPatch, onUnlock, onRemove }: {
  user: User;
  editable: boolean;
  onPatch: (u: User, body: Partial<User>, message: string) => void;
  onUnlock: (u: User) => void;
  onRemove: (u: User) => void;
}) {
  return (
    <td className="actions">
      {u.locked_until && <button type="button" className="small" onClick={() => onUnlock(u)}>Déverrouiller</button>}
      {editable && (
        <button type="button" className="small secondary" onClick={() => onPatch(u, { is_active: !u.is_active }, u.is_active ? "Compte désactivé." : "Compte réactivé.")}>
          {u.is_active ? "Désactiver" : "Réactiver"}
        </button>
      )}
      {editable && <button type="button" className="small danger" onClick={() => onRemove(u)}>Supprimer</button>}
    </td>
  );
}

function UserRow({ user: u, admin, self, onPatch, onUnlock, onRemove }: {
  user: User;
  admin: boolean;
  self: boolean;
  onPatch: (u: User, body: Partial<User>, message: string) => void;
  onUnlock: (u: User) => void;
  onRemove: (u: User) => void;
}) {
  const editable = admin && !self;
  return (
    <tr>
      <td>{u.full_name}</td>
      <td>{u.email}</td>
      <td>
        {editable ? (
          <select aria-label={`Rôle de ${u.full_name}`} value={u.role} onChange={(e) => onPatch(u, { role: e.target.value as Role }, "Rôle modifié.")}>
            {ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}
          </select>
        ) : label(u.role)}
      </td>
      <td>
        <span className={u.is_active ? "badge badge-success" : "badge badge-neutral"}>{u.is_active ? "Actif" : "Inactif"}</span>{" "}
        {u.locked_until && <StatusBadge status="Verrouillé" />}
      </td>
      {admin && <UserActions user={u} editable={editable} onPatch={onPatch} onUnlock={onUnlock} onRemove={onRemove} />}
    </tr>
  );
}

export function UsersPage() {
  const { hasRole, user: me } = useAuth();
  const admin = hasRole("ADMIN");
  const [q, setQ] = useState("");
  const [role, setRole] = useState("");
  const [page, setPage] = useState(1);
  const list = useAsync(() => api.get<Page<User>>("/users", { q, role, page, size: 20 }), [q, role, page]);
  const action = useAction();

  async function patch(u: User, body: Partial<User>, message: string) {
    if (await action.run(() => api.patch(`/users/${u.id}`, body), message)) list.reload();
  }
  async function unlock(u: User) {
    if (await action.run(() => api.post(`/users/${u.id}/unlock`), `${u.full_name} déverrouillé.`)) list.reload();
  }
  async function remove(u: User) {
    if (window.confirm(`Supprimer le compte de ${u.full_name} ?`) && (await action.run(() => api.del(`/users/${u.id}`), "Compte supprimé (ou désactivé si historique).")))
      list.reload();
  }

  return (
    <section>
      <h1>Utilisateurs</h1>
      {admin && <NewUserForm onDone={list.reload} />}
      <div className="filters card">
        <Field label="Recherche (nom, e-mail)">{(id) => <input id={id} type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />}</Field>
        <Field label="Rôle">
          {(id) => (
            <select id={id} value={role} onChange={(e) => { setRole(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              {ROLES.map((r) => <option key={r} value={r}>{label(r)}</option>)}
            </select>
          )}
        </Field>
      </div>
      <Alert kind="error">{action.error || list.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
      {list.data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Nom</th>
                <th scope="col">E-mail</th>
                <th scope="col">Rôle</th>
                <th scope="col">État</th>
                {admin && <th scope="col">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((u) => (
                <UserRow key={u.id} user={u} admin={admin} self={u.id === me?.id} onPatch={patch} onUnlock={unlock} onRemove={remove} />
              ))}
            </tbody>
          </table>
          <Pagination page={page} size={20} total={list.data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ audit
export function AuditPage() {
  const [filters, setFilters] = useState({ action: "", entity_type: "", user_email: "" });
  const [page, setPage] = useState(1);
  const list = useAsync(() => api.get<Page<AuditEntry>>("/audit", { ...filters, page, size: 50 }), [filters, page]);
  const set = (key: keyof typeof filters) => (e: { target: { value: string } }) => { setFilters({ ...filters, [key]: e.target.value }); setPage(1); };

  return (
    <section>
      <h1>Journal d'audit</h1>
      <div className="filters card">
        <Field label="Action">
          {(id) => (
            <select id={id} value={filters.action} onChange={set("action")}>
              <option value="">Toutes</option>
              {["LOGIN_SUCCESS", "LOGIN_FAILED", "ACCOUNT_LOCKED", "LOAN_CREATED", "LOAN_RETURNED", "LOAN_RENEWED", "LOAN_LOST",
                "RESERVATION_CREATED", "RESERVATION_CANCELLED", "PENALTY_PAID", "PENALTY_CANCELLED", "BOOK_CREATED", "BOOK_UPDATED",
                "BOOK_DELETED", "USER_CREATED", "USER_UPDATED", "USER_DELETED"].map((a) => <option key={a}>{a}</option>)}
            </select>
          )}
        </Field>
        <Field label="Entité">
          {(id) => (
            <select id={id} value={filters.entity_type} onChange={set("entity_type")}>
              <option value="">Toutes</option>
              {["User", "Book", "Copy", "Loan", "Reservation", "Penalty", "Category", "Author", "System"].map((t) => <option key={t}>{t}</option>)}
            </select>
          )}
        </Field>
        <Field label="Utilisateur (e-mail)">{(id) => <input id={id} type="search" value={filters.user_email} onChange={set("user_email")} />}</Field>
      </div>
      <Alert kind="error">{list.error}</Alert>
      {list.data && (
        <>
          <table className="table table-compact">
            <thead>
              <tr>
                <th scope="col">Date</th>
                <th scope="col">Utilisateur</th>
                <th scope="col">Action</th>
                <th scope="col">Entité</th>
                <th scope="col">Détails</th>
                <th scope="col">IP</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((a) => (
                <tr key={a.id}>
                  <td>{formatDateTime(a.timestamp)}</td>
                  <td>{a.user_email ?? "—"}</td>
                  <td><code>{a.action}</code></td>
                  <td>{a.entity_type}{a.entity_id ? ` #${a.entity_id}` : ""}</td>
                  <td className="details-cell">{a.details ?? ""}</td>
                  <td>{a.ip_address ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <Pagination page={page} size={50} total={list.data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}
