import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";
import type { Loan, Page, Penalty, Reservation, ReturnResult, User } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Field, Loading, Pagination, StatusBadge, useAction, useAsync } from "../components/ui";
import { daysUntil, formatDate, formatDateTime, formatMoney } from "../utils/format";

const SIZE = 20;

// ------------------------------------------------------------------ emprunts
function NewLoanForm({ onDone }: { onDone: () => void }) {
  const [memberQuery, setMemberQuery] = useState("");
  const [userId, setUserId] = useState("");
  const [barcode, setBarcode] = useState("");
  const action = useAction();
  const members = useAsync(
    () => (memberQuery.length >= 2 ? api.get<Page<User>>("/users", { q: memberQuery, role: "ADHERENT", size: 10 }) : Promise.resolve(null)),
    [memberQuery],
  );

  async function submit(e: FormEvent) {
    e.preventDefault();
    const ok = await action.run(
      () => api.post<Loan>("/loans", { user_id: Number(userId), barcode: barcode.trim().toUpperCase() }),
      `Emprunt enregistré pour l'exemplaire ${barcode.toUpperCase()}.`,
    );
    if (ok) {
      setBarcode("");
      onDone();
    }
  }

  return (
    <form className="card inline-form" onSubmit={submit} aria-labelledby="new-loan-title">
      <h2 id="new-loan-title">Nouvel emprunt</h2>
      <Field label="Rechercher l'adhérent (nom ou e-mail)">
        {(id) => <input id={id} type="search" value={memberQuery} onChange={(e) => setMemberQuery(e.target.value)} />}
      </Field>
      <Field label="Adhérent">
        {(id) => (
          <select id={id} required value={userId} onChange={(e) => setUserId(e.target.value)}>
            <option value="">— Choisir —</option>
            {members.data?.items.map((m) => (
              <option key={m.id} value={m.id}>
                {m.full_name} ({m.email})
              </option>
            ))}
          </select>
        )}
      </Field>
      <Field label="Code-barres de l'exemplaire">
        {(id) => <input id={id} required value={barcode} onChange={(e) => setBarcode(e.target.value)} />}
      </Field>
      <button type="submit" disabled={action.busy || !userId || !barcode}>
        Enregistrer l'emprunt
      </button>
      <Alert kind="error">{action.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
    </form>
  );
}

function DueCell({ loan }: { loan: Loan }) {
  if (loan.status !== "EN_COURS" && loan.status !== "EN_RETARD") return <>{formatDate(loan.due_date)}</>;
  const days = daysUntil(loan.due_date);
  return (
    <>
      {formatDate(loan.due_date)}{" "}
      <small className={days < 0 ? "text-danger" : "muted"}>
        ({days < 0 ? `${-days} j de retard` : `J-${days}`})
      </small>
    </>
  );
}

export function LoansPage() {
  const { hasRole } = useAuth();
  const staff = hasRole("ADMIN", "BIBLIOTHECAIRE");
  const [status, setStatus] = useState("");
  const [q, setQ] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const loans = useAsync(() => api.get<Page<Loan>>("/loans", { status, q, overdue_only: overdue || undefined, page, size: SIZE }), [status, q, overdue, page]);
  const action = useAction();

  async function giveBack(loan: Loan) {
    let result: ReturnResult | undefined;
    const ok = await action.run(async () => {
      result = await api.post<ReturnResult>(`/loans/${loan.id}/return`);
    }, "Retour enregistré.");
    if (ok && result) {
      const parts = [`Retour de « ${loan.item.book.title} » enregistré.`];
      if (result.days_late > 0) parts.push(`Retard de ${result.days_late} jour(s) : pénalité de ${formatMoney(result.penalty_amount)}.`);
      if (result.reserved_for_user_id) parts.push("L'exemplaire est mis de côté pour une réservation.");
      action.setSuccess(parts.join(" "));
      loans.reload();
    }
  }

  async function renew(loan: Loan) {
    if (await action.run(() => api.post(`/loans/${loan.id}/renew`), `Emprunt prolongé.`)) loans.reload();
  }

  async function lost(loan: Loan) {
    if (window.confirm("Déclarer cet exemplaire perdu ? Une pénalité de remplacement sera appliquée.") && (await action.run(() => api.post(`/loans/${loan.id}/lost`), "Perte déclarée.")))
      loans.reload();
  }

  return (
    <section>
      <h1>{staff ? "Emprunts" : "Mes emprunts"}</h1>
      {staff && <NewLoanForm onDone={loans.reload} />}
      <div className="filters card">
        {staff && (
          <Field label="Recherche (adhérent, titre, code-barres)">
            {(id) => <input id={id} type="search" value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />}
          </Field>
        )}
        <Field label="Statut">
          {(id) => (
            <select id={id} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              <option value="EN_COURS">En cours</option>
              <option value="EN_RETARD">En retard</option>
              <option value="RENDU">Rendus</option>
              <option value="PERDU">Perdus</option>
            </select>
          )}
        </Field>
        <label className="checkbox">
          <input type="checkbox" checked={overdue} onChange={(e) => { setOverdue(e.target.checked); setPage(1); }} />
          Échéance dépassée uniquement
        </label>
      </div>
      <Alert kind="error">{action.error || loans.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
      {loans.loading && !loans.data ? <Loading /> : loans.data && (
        <>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Ouvrage</th>
                <th scope="col">Exemplaire</th>
                {staff && <th scope="col">Adhérent</th>}
                <th scope="col">Emprunté le</th>
                <th scope="col">Échéance</th>
                <th scope="col">Statut</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {loans.data.items.map((l) => {
                const active = l.status === "EN_COURS" || l.status === "EN_RETARD";
                return (
                  <tr key={l.id}>
                    <td>{l.item.book.title}</td>
                    <td>{l.item.barcode}</td>
                    {staff && <td>{l.user.full_name}</td>}
                    <td>{formatDate(l.loaned_at)}</td>
                    <td><DueCell loan={l} /></td>
                    <td><StatusBadge status={l.status} /></td>
                    <td className="actions">
                      {staff && active && <button type="button" className="small" onClick={() => giveBack(l)}>Retour</button>}
                      {l.status === "EN_COURS" && l.renewals_count === 0 && (
                        <button type="button" className="small secondary" onClick={() => renew(l)}>Prolonger</button>
                      )}
                      {staff && active && <button type="button" className="small danger" onClick={() => lost(l)}>Perdu</button>}
                    </td>
                  </tr>
                );
              })}
              {loans.data.items.length === 0 && (
                <tr><td colSpan={7} className="muted">Aucun emprunt.</td></tr>
              )}
            </tbody>
          </table>
          <Pagination page={page} size={SIZE} total={loans.data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ réservations
export function ReservationsPage() {
  const { hasRole } = useAuth();
  const staff = hasRole("ADMIN", "BIBLIOTHECAIRE");
  const [status, setStatus] = useState("");
  const [page, setPage] = useState(1);
  const list = useAsync(() => api.get<Page<Reservation>>("/reservations", { status, page, size: SIZE }), [status, page]);
  const action = useAction();

  async function cancel(r: Reservation) {
    if (await action.run(() => api.post(`/reservations/${r.id}/cancel`), "Réservation annulée.")) list.reload();
  }

  return (
    <section>
      <h1>{staff ? "Réservations" : "Mes réservations"}</h1>
      <div className="filters card">
        <Field label="Statut">
          {(id) => (
            <select id={id} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              <option value="EN_ATTENTE">En attente</option>
              <option value="DISPONIBLE">Disponible (à retirer)</option>
              <option value="HONOREE">Honorée</option>
              <option value="ANNULEE">Annulée</option>
              <option value="EXPIREE">Expirée</option>
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
                <th scope="col">Ouvrage</th>
                {staff && <th scope="col">Adhérent</th>}
                <th scope="col">Demandée le</th>
                <th scope="col">Statut</th>
                <th scope="col">Position / retrait avant</th>
                <th scope="col">Actions</th>
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((r) => (
                <tr key={r.id}>
                  <td>{r.book.title}</td>
                  {staff && <td>{r.user.full_name}</td>}
                  <td>{formatDateTime(r.created_at)}</td>
                  <td><StatusBadge status={r.status} /></td>
                  <td>
                    {r.status === "EN_ATTENTE" && `n° ${r.queue_position} dans la file`}
                    {r.status === "DISPONIBLE" && `à retirer avant le ${formatDateTime(r.available_until)}`}
                  </td>
                  <td>
                    {(r.status === "EN_ATTENTE" || r.status === "DISPONIBLE") && (
                      <button type="button" className="small danger" onClick={() => cancel(r)}>Annuler</button>
                    )}
                  </td>
                </tr>
              ))}
              {list.data.items.length === 0 && <tr><td colSpan={6} className="muted">Aucune réservation.</td></tr>}
            </tbody>
          </table>
          <Pagination page={page} size={SIZE} total={list.data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}

// ------------------------------------------------------------------ pénalités
function unpaidTotal(items: Penalty[]): number {
  return items.filter((p) => p.status === "IMPAYEE").reduce((sum, p) => sum + Number(p.amount), 0);
}

function UnpaidNotice({ amount }: { amount: number }) {
  if (amount <= 0) return null;
  return (
    <Alert kind="info">
      Vous avez {formatMoney(amount)} de pénalités impayées : les nouveaux emprunts sont bloqués jusqu'à régularisation.
    </Alert>
  );
}

function PenaltyRow({ penalty: p, staff, admin, onSettle }: {
  penalty: Penalty;
  staff: boolean;
  admin: boolean;
  onSettle: (p: Penalty, verb: "pay" | "cancel") => void;
}) {
  const unpaid = p.status === "IMPAYEE";
  return (
    <tr>
      {staff && <td>{p.user.full_name}</td>}
      <td>{p.reason}</td>
      <td>{formatMoney(p.amount)}</td>
      <td>{formatDate(p.created_at)}</td>
      <td><StatusBadge status={p.status} /></td>
      {staff && (
        <td className="actions">
          {unpaid && <button type="button" className="small" onClick={() => onSettle(p, "pay")}>Encaisser</button>}
          {unpaid && admin && <button type="button" className="small secondary" onClick={() => onSettle(p, "cancel")}>Annuler</button>}
        </td>
      )}
    </tr>
  );
}

export function PenaltiesPage() {
  const { hasRole } = useAuth();
  const staff = hasRole("ADMIN", "BIBLIOTHECAIRE");
  const [status, setStatus] = useState("IMPAYEE");
  const [page, setPage] = useState(1);
  const list = useAsync(() => api.get<Page<Penalty>>("/penalties", { status, page, size: SIZE }), [status, page]);
  const action = useAction();

  async function settle(p: Penalty, verb: "pay" | "cancel") {
    if (await action.run(() => api.post(`/penalties/${p.id}/${verb}`), verb === "pay" ? "Paiement enregistré." : "Pénalité annulée.")) list.reload();
  }

  const unpaid = unpaidTotal(list.data?.items ?? []);

  return (
    <section>
      <h1>{staff ? "Pénalités" : "Mes pénalités"}</h1>
      {!staff && <UnpaidNotice amount={unpaid} />}
      <div className="filters card">
        <Field label="Statut">
          {(id) => (
            <select id={id} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>
              <option value="">Tous</option>
              <option value="IMPAYEE">Impayées</option>
              <option value="PAYEE">Payées</option>
              <option value="ANNULEE">Annulées</option>
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
                {staff && <th scope="col">Adhérent</th>}
                <th scope="col">Motif</th>
                <th scope="col">Montant</th>
                <th scope="col">Date</th>
                <th scope="col">Statut</th>
                {staff && <th scope="col">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {list.data.items.map((p) => (
                <PenaltyRow key={p.id} penalty={p} staff={staff} admin={hasRole("ADMIN")} onSettle={settle} />
              ))}
              {list.data.items.length === 0 && <tr><td colSpan={6} className="muted">Aucune pénalité.</td></tr>}
            </tbody>
          </table>
          <Pagination page={page} size={SIZE} total={list.data.total} onChange={setPage} />
        </>
      )}
    </section>
  );
}
