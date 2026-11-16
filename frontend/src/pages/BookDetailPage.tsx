import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api/client";
import type { Book, Copy, CopyStatus } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Field, Loading, StatusBadge, useAction, useAsync } from "../components/ui";
import { formatDate, formatIsbn } from "../utils/format";

type Action = ReturnType<typeof useAction>;

const MANUAL_TARGETS = new Map<CopyStatus, CopyStatus[]>([
  ["DISPONIBLE", ["EN_REPARATION", "RETIRE"]],
  ["EN_REPARATION", ["DISPONIBLE", "RETIRE"]],
]);
const TARGET_LABEL = new Map<CopyStatus, string>([
  ["DISPONIBLE", "Remettre en rayon"],
  ["RETIRE", "Retirer"],
  ["EN_REPARATION", "En réparation"],
]);

function BookInfo({ book }: { book: Book }) {
  return (
    <dl className="card details">
      <dt>Auteur(s)</dt>
      <dd>{book.authors.map((a) => a.full_name).join(", ")}</dd>
      <dt>ISBN</dt>
      <dd>{formatIsbn(book.isbn)}</dd>
      <dt>Catégorie</dt>
      <dd>{book.category.name}</dd>
      <dt>Éditeur / année</dt>
      <dd>
        {book.publisher ?? "—"} / {book.publication_year ?? "—"}
      </dd>
      <dt>Disponibilité</dt>
      <dd data-testid="availability">
        {book.available_copies} exemplaire(s) disponible(s) sur {book.total_copies}
      </dd>
      {book.summary && (
        <>
          <dt>Résumé</dt>
          <dd>{book.summary}</dd>
        </>
      )}
    </dl>
  );
}

function CopiesTable({ copies, staff, action, onChange }: { copies: Copy[]; staff: boolean; action: Action; onChange: () => void }) {
  async function changeStatus(copy: Copy, status: CopyStatus) {
    if (await action.run(() => api.patch(`/copies/${copy.id}`, { status }), `Exemplaire ${copy.barcode} : statut mis à jour.`)) onChange();
  }
  return (
    <table className="table">
      <thead>
        <tr>
          <th scope="col">Code-barres</th>
          <th scope="col">Emplacement</th>
          <th scope="col">Acquis le</th>
          <th scope="col">Statut</th>
          {staff && <th scope="col">Actions</th>}
        </tr>
      </thead>
      <tbody>
        {copies.map((c) => (
          <tr key={c.id}>
            <td>{c.barcode}</td>
            <td>{c.shelf_location ?? "—"}</td>
            <td>{formatDate(c.acquired_on)}</td>
            <td>
              <StatusBadge status={c.status} />
            </td>
            {staff && (
              <td className="actions">
                {(MANUAL_TARGETS.get(c.status) ?? []).map((target) => (
                  <button key={target} type="button" className="small secondary" onClick={() => changeStatus(c, target)}>
                    {TARGET_LABEL.get(target)}
                  </button>
                ))}
              </td>
            )}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function AddCopyForm({ bookId, action, onAdded }: { bookId: string; action: Action; onAdded: () => void }) {
  const [barcode, setBarcode] = useState("");
  const [shelf, setShelf] = useState("");

  async function submit(e: FormEvent) {
    e.preventDefault();
    const code = barcode.trim().toUpperCase();
    const ok = await action.run(
      () => api.post(`/books/${bookId}/copies`, { barcode: code, shelf_location: shelf || null }),
      `Exemplaire ${code} ajouté.`,
    );
    if (ok) {
      setBarcode("");
      setShelf("");
      onAdded();
    }
  }

  return (
    <form className="card inline-form" onSubmit={submit}>
      <h3>Ajouter un exemplaire</h3>
      <Field label="Code-barres" hint="Lettres, chiffres et tirets (4 à 32).">
        {(id, hint) => (
          <input id={id} required pattern="[A-Za-z0-9\-]{4,32}" aria-describedby={hint} value={barcode}
            onChange={(e) => setBarcode(e.target.value)} />
        )}
      </Field>
      <Field label="Emplacement">{(id) => <input id={id} value={shelf} onChange={(e) => setShelf(e.target.value)} />}</Field>
      <button type="submit" disabled={action.busy}>
        Ajouter
      </button>
    </form>
  );
}

function MemberActions({ book, action, onReserved }: { book: Book; action: Action; onReserved: () => void }) {
  async function reserve() {
    const ok = await action.run(
      () => api.post("/reservations", { book_id: book.id }),
      "Réservation enregistrée : vous serez prévenu dès qu'un exemplaire sera disponible.",
    );
    if (ok) onReserved();
  }
  if (book.available_copies > 0) {
    return <p className="muted">Un exemplaire est disponible : présentez-vous au comptoir pour l'emprunter.</p>;
  }
  return (
    <button type="button" onClick={reserve} disabled={action.busy}>
      Réserver cet ouvrage
    </button>
  );
}

export function BookDetailPage() {
  const { id = "" } = useParams();
  const { hasRole } = useAuth();
  const navigate = useNavigate();
  const staff = hasRole("ADMIN", "BIBLIOTHECAIRE");
  const book = useAsync(() => api.get<Book>(`/books/${id}`), [id]);
  const copies = useAsync(() => api.get<Copy[]>(`/books/${id}/copies`), [id]);
  const action = useAction();

  const refresh = () => {
    book.reload();
    copies.reload();
  };

  async function removeBook() {
    if (!window.confirm("Supprimer définitivement cet ouvrage ?")) return;
    if (await action.run(() => api.del(`/books/${id}`), "Ouvrage supprimé.")) navigate("/catalogue");
  }

  if (book.error) return <Alert kind="error">{book.error}</Alert>;
  if (!book.data) return <Loading />;

  return (
    <section>
      <p>
        <Link to="/catalogue">← Retour au catalogue</Link>
      </p>
      <div className="page-head">
        <h1>{book.data.title}</h1>
        {staff && (
          <div className="actions">
            <Link className="button secondary" to={`/catalogue/${id}/modifier`}>
              Modifier
            </Link>
            <button type="button" className="danger" onClick={removeBook}>
              Supprimer
            </button>
          </div>
        )}
      </div>
      <BookInfo book={book.data} />
      <Alert kind="error">{action.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
      {hasRole("ADHERENT") && <MemberActions book={book.data} action={action} onReserved={refresh} />}
      <h2>Exemplaires</h2>
      {copies.data && <CopiesTable copies={copies.data} staff={staff} action={action} onChange={refresh} />}
      {staff && <AddCopyForm bookId={id} action={action} onAdded={refresh} />}
    </section>
  );
}
