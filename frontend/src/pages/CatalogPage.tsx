import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import type { Book, Category, Page } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Alert, Field, Loading, Pagination, useAsync } from "../components/ui";

const SIZE = 20;

interface Filters {
  q: string;
  category_id: string;
  year_from: string;
  year_to: string;
  available_only: boolean;
  sort: string;
}

const EMPTY: Filters = { q: "", category_id: "", year_from: "", year_to: "", available_only: false, sort: "title" };

export function CatalogPage() {
  const { hasRole } = useAuth();
  const [draft, setDraft] = useState<Filters>(EMPTY);
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [page, setPage] = useState(1);

  const categories = useAsync(() => api.get<Category[]>("/categories"), []);
  const books = useAsync(
    () => api.get<Page<Book>>("/books", { ...filters, page, size: SIZE }),
    [filters, page],
  );

  function search(e: FormEvent) {
    e.preventDefault();
    setPage(1);
    setFilters(draft);
  }

  return (
    <section>
      <div className="page-head">
        <h1>Catalogue</h1>
        {hasRole("ADMIN", "BIBLIOTHECAIRE") && (
          <Link className="button" to="/catalogue/nouveau">
            + Nouvel ouvrage
          </Link>
        )}
      </div>

      <form className="filters card" onSubmit={search} role="search" aria-label="Recherche dans le catalogue">
        <Field label="Titre, auteur ou ISBN">
          {(id) => (
            <input id={id} type="search" value={draft.q} placeholder="ex. Camus, Dune, 978…"
              onChange={(e) => setDraft({ ...draft, q: e.target.value })} />
          )}
        </Field>
        <Field label="Catégorie">
          {(id) => (
            <select id={id} value={draft.category_id} onChange={(e) => setDraft({ ...draft, category_id: e.target.value })}>
              <option value="">Toutes</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Année min.">
          {(id) => (
            <input id={id} type="number" min={1450} max={2100} value={draft.year_from}
              onChange={(e) => setDraft({ ...draft, year_from: e.target.value })} />
          )}
        </Field>
        <Field label="Année max.">
          {(id) => (
            <input id={id} type="number" min={1450} max={2100} value={draft.year_to}
              onChange={(e) => setDraft({ ...draft, year_to: e.target.value })} />
          )}
        </Field>
        <Field label="Tri">
          {(id) => (
            <select id={id} value={draft.sort} onChange={(e) => setDraft({ ...draft, sort: e.target.value })}>
              <option value="title">Titre (A→Z)</option>
              <option value="-year">Plus récents</option>
              <option value="year">Plus anciens</option>
              <option value="-created">Derniers ajouts</option>
            </select>
          )}
        </Field>
        <label className="checkbox">
          <input type="checkbox" checked={draft.available_only}
            onChange={(e) => setDraft({ ...draft, available_only: e.target.checked })} />
          Disponibles uniquement
        </label>
        <div className="actions">
          <button type="submit">Rechercher</button>
          <button type="button" className="secondary" onClick={() => { setDraft(EMPTY); setFilters(EMPTY); setPage(1); }}>
            Réinitialiser
          </button>
        </div>
      </form>

      <Alert kind="error">{books.error}</Alert>
      {books.loading && !books.data ? (
        <Loading />
      ) : (
        books.data && (
          <>
            <table className="table" aria-describedby="catalog-count">
              <caption id="catalog-count" className="sr-only">
                {books.data.total} ouvrages trouvés
              </caption>
              <thead>
                <tr>
                  <th scope="col">Titre</th>
                  <th scope="col">Auteur(s)</th>
                  <th scope="col">Catégorie</th>
                  <th scope="col">Année</th>
                  <th scope="col">Disponibilité</th>
                </tr>
              </thead>
              <tbody>
                {books.data.items.map((b) => (
                  <tr key={b.id}>
                    <td>
                      <Link to={`/catalogue/${b.id}`}>{b.title}</Link>
                    </td>
                    <td>{b.authors.map((a) => a.full_name).join(", ")}</td>
                    <td>{b.category.name}</td>
                    <td>{b.publication_year ?? "—"}</td>
                    <td>
                      <span className={b.available_copies > 0 ? "badge badge-success" : "badge badge-neutral"}>
                        {b.available_copies} / {b.total_copies}
                      </span>
                    </td>
                  </tr>
                ))}
                {books.data.items.length === 0 && (
                  <tr>
                    <td colSpan={5} className="muted">
                      Aucun ouvrage ne correspond à vos critères.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
            <Pagination page={page} size={SIZE} total={books.data.total} onChange={setPage} />
          </>
        )
      )}
    </section>
  );
}
