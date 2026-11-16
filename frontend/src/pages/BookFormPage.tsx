import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { api } from "../api/client";
import type { Author, Book, Category, IsbnLookup } from "../api/types";
import { Alert, Field, useAction, useAsync } from "../components/ui";
import { isValidIsbn } from "../utils/format";

interface BookForm {
  isbn: string;
  title: string;
  publisher: string;
  publication_year: string;
  summary: string;
  category_id: string;
  author_ids: string[];
}

const EMPTY: BookForm = { isbn: "", title: "", publisher: "", publication_year: "", summary: "", category_id: "", author_ids: [] };

export function BookFormPage() {
  const { id } = useParams();
  const editing = Boolean(id);
  const navigate = useNavigate();
  const [form, setForm] = useState<BookForm>(EMPTY);
  const [lookupInfo, setLookupInfo] = useState("");
  const action = useAction();
  const categories = useAsync(() => api.get<Category[]>("/categories"), []);
  const authors = useAsync(() => api.get<Author[]>("/authors"), []);

  useEffect(() => {
    if (!id) return;
    api.get<Book>(`/books/${id}`).then((b) =>
      setForm({
        isbn: b.isbn,
        title: b.title,
        publisher: b.publisher ?? "",
        publication_year: b.publication_year?.toString() ?? "",
        summary: b.summary ?? "",
        category_id: String(b.category.id),
        author_ids: b.authors.map((a) => String(a.id)),
      }),
    );
  }, [id]);

  const isbnOk = form.isbn === "" || isValidIsbn(form.isbn);

  async function lookup() {
    setLookupInfo("Interrogation d'Open Library…");
    try {
      const r = await api.get<IsbnLookup>(`/books/lookup/${encodeURIComponent(form.isbn)}`);
      if (r.found) {
        setForm((f) => ({
          ...f,
          title: r.title ?? f.title,
          publisher: r.publisher ?? f.publisher,
          publication_year: r.publication_year?.toString() ?? f.publication_year,
        }));
        setLookupInfo(`Trouvé sur Open Library${r.authors.length ? ` — auteur(s) : ${r.authors.join(", ")}` : ""}.`);
      } else {
        setLookupInfo(r.message ?? "Aucune donnée trouvée.");
      }
    } catch (e) {
      setLookupInfo(e instanceof Error ? e.message : "Recherche impossible.");
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    const payload = {
      ...form,
      publication_year: form.publication_year ? Number(form.publication_year) : null,
      publisher: form.publisher || null,
      summary: form.summary || null,
      category_id: Number(form.category_id),
      author_ids: form.author_ids.map(Number),
    };
    let saved: Book | undefined;
    const ok = await action.run(async () => {
      saved = editing ? await api.put<Book>(`/books/${id}`, payload) : await api.post<Book>("/books", payload);
    }, "Ouvrage enregistré.");
    if (ok && saved) navigate(`/catalogue/${saved.id}`);
  }

  const set = (key: keyof BookForm) => (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value });

  return (
    <section>
      <p>
        <Link to="/catalogue">← Retour au catalogue</Link>
      </p>
      <h1>{editing ? "Modifier l'ouvrage" : "Nouvel ouvrage"}</h1>
      <form className="card form-grid" onSubmit={submit}>
        <Field label="ISBN" hint={isbnOk ? "ISBN-10 ou ISBN-13, tirets acceptés." : "Clé de contrôle ISBN invalide."}>
          {(fid, hint) => (
            <div className="input-group">
              <input id={fid} required value={form.isbn} aria-invalid={!isbnOk} aria-describedby={hint} onChange={set("isbn")} />
              <button type="button" className="secondary" onClick={lookup} disabled={!form.isbn || !isbnOk}>
                Rechercher (Open Library)
              </button>
            </div>
          )}
        </Field>
        {lookupInfo && <p className="muted" role="status">{lookupInfo}</p>}
        <Field label="Titre">{(fid) => <input id={fid} required maxLength={255} value={form.title} onChange={set("title")} />}</Field>
        <Field label="Éditeur">{(fid) => <input id={fid} value={form.publisher} onChange={set("publisher")} />}</Field>
        <Field label="Année de publication">
          {(fid) => <input id={fid} type="number" min={1450} max={2100} value={form.publication_year} onChange={set("publication_year")} />}
        </Field>
        <Field label="Catégorie">
          {(fid) => (
            <select id={fid} required value={form.category_id} onChange={set("category_id")}>
              <option value="">— Choisir —</option>
              {categories.data?.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Auteur(s)" hint="Ctrl/Cmd + clic pour une sélection multiple.">
          {(fid, hint) => (
            <select id={fid} multiple required size={6} aria-describedby={hint} value={form.author_ids}
              onChange={(e) => setForm({ ...form, author_ids: [...e.target.selectedOptions].map((o) => o.value) })}>
              {authors.data?.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.full_name}
                </option>
              ))}
            </select>
          )}
        </Field>
        <Field label="Résumé">{(fid) => <textarea id={fid} rows={4} maxLength={5000} value={form.summary} onChange={set("summary")} />}</Field>
        <Alert kind="error">{action.error}</Alert>
        <div className="actions">
          <button type="submit" disabled={action.busy || !isbnOk}>
            Enregistrer
          </button>
        </div>
      </form>
    </section>
  );
}
