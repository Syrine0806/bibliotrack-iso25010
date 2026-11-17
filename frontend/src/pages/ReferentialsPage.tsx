import { useState } from "react";
import type { FormEvent } from "react";
import { api } from "../api/client";
import type { Author, Category } from "../api/types";
import { Alert, Field, useAction, useAsync } from "../components/ui";

function CategoriesPanel() {
  const list = useAsync(() => api.get<Category[]>("/categories"), []);
  const action = useAction();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [editing, setEditing] = useState<number | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = { name, description: description || null };
    const ok = await action.run(
      () => (editing ? api.put(`/categories/${editing}`, body) : api.post("/categories", body)),
      editing ? "Catégorie modifiée." : "Catégorie créée.",
    );
    if (ok) {
      setName("");
      setDescription("");
      setEditing(null);
      list.reload();
    }
  }

  async function remove(c: Category) {
    if (window.confirm(`Supprimer la catégorie « ${c.name} » ?`) && (await action.run(() => api.del(`/categories/${c.id}`), "Catégorie supprimée.")))
      list.reload();
  }

  return (
    <section className="card" aria-labelledby="cat-title">
      <h2 id="cat-title">Catégories</h2>
      <form className="inline-form" onSubmit={submit}>
        <Field label="Nom de la catégorie">{(id) => <input id={id} required minLength={2} value={name} onChange={(e) => setName(e.target.value)} />}</Field>
        <Field label="Description">{(id) => <input id={id} value={description} onChange={(e) => setDescription(e.target.value)} />}</Field>
        <button type="submit">{editing ? "Modifier" : "Ajouter"}</button>
      </form>
      <Alert kind="error">{action.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Nom</th>
            <th scope="col">Description</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {list.data?.map((c) => (
            <tr key={c.id}>
              <td>{c.name}</td>
              <td>{c.description ?? "—"}</td>
              <td className="actions">
                <button type="button" className="small secondary" onClick={() => { setEditing(c.id); setName(c.name); setDescription(c.description ?? ""); }}>
                  Modifier
                </button>
                <button type="button" className="small danger" onClick={() => remove(c)} aria-label={`Supprimer ${c.name}`}>
                  Supprimer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function AuthorsPanel() {
  const [q, setQ] = useState("");
  const list = useAsync(() => api.get<Author[]>("/authors", { q }), [q]);
  const action = useAction();
  const [form, setForm] = useState({ full_name: "", nationality: "", birth_year: "" });

  async function submit(e: FormEvent) {
    e.preventDefault();
    const body = { full_name: form.full_name, nationality: form.nationality || null, birth_year: form.birth_year ? Number(form.birth_year) : null };
    if (await action.run(() => api.post("/authors", body), `Auteur « ${form.full_name} » créé.`)) {
      setForm({ full_name: "", nationality: "", birth_year: "" });
      list.reload();
    }
  }

  async function remove(a: Author) {
    if (window.confirm(`Supprimer l'auteur « ${a.full_name} » ?`) && (await action.run(() => api.del(`/authors/${a.id}`), "Auteur supprimé.")))
      list.reload();
  }

  return (
    <section className="card" aria-labelledby="auth-title">
      <h2 id="auth-title">Auteurs</h2>
      <form className="inline-form" onSubmit={submit}>
        <Field label="Nom complet">{(id) => <input id={id} required value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} />}</Field>
        <Field label="Nationalité">{(id) => <input id={id} value={form.nationality} onChange={(e) => setForm({ ...form, nationality: e.target.value })} />}</Field>
        <Field label="Année de naissance">{(id) => <input id={id} type="number" value={form.birth_year} onChange={(e) => setForm({ ...form, birth_year: e.target.value })} />}</Field>
        <button type="submit">Ajouter</button>
      </form>
      <Alert kind="error">{action.error}</Alert>
      <Alert kind="success">{action.success}</Alert>
      <Field label="Filtrer les auteurs">{(id) => <input id={id} type="search" value={q} onChange={(e) => setQ(e.target.value)} />}</Field>
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Nom</th>
            <th scope="col">Nationalité</th>
            <th scope="col">Naissance</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {list.data?.slice(0, 50).map((a) => (
            <tr key={a.id}>
              <td>{a.full_name}</td>
              <td>{a.nationality ?? "—"}</td>
              <td>{a.birth_year ?? "—"}</td>
              <td>
                <button type="button" className="small danger" onClick={() => remove(a)} aria-label={`Supprimer ${a.full_name}`}>
                  Supprimer
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export function ReferentialsPage() {
  return (
    <section>
      <h1>Auteurs &amp; catégories</h1>
      <div className="two-cols">
        <CategoriesPanel />
        <AuthorsPanel />
      </div>
    </section>
  );
}
