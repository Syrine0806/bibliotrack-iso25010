import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useNavigate } from "react-router";
import { api, ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { homeFor } from "../components/Layout";
import { Icon } from "../components/icons";
import { Alert, Field } from "../components/ui";

function AuthHero() {
  return (
    <aside className="auth-hero" aria-label="Présentation de BiblioTrack">
      <div className="brand">
        <span className="brand-mark" aria-hidden="true">
          <Icon name="book" size={18} />
        </span>
        <span className="brand-name">BiblioTrack</span>
      </div>
      <div className="auth-hero-body">
        <p className="eyebrow">Médiathèque connectée</p>
        <p className="auth-hero-title">Tout le catalogue, les prêts et les réservations au même endroit.</p>
        <ul className="auth-hero-list">
          <li><Icon name="search" size={18} /> Recherche instantanée parmi plus de 5 000 ouvrages</li>
          <li><Icon name="bookmark" size={18} /> Réservations avec file d'attente équitable</li>
          <li><Icon name="clock" size={18} /> Échéances, prolongations et rappels clairs</li>
        </ul>
      </div>
      <p className="auth-hero-foot">Qualité logicielle ISO/IEC 25010</p>
    </aside>
  );
}

export function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  if (user) return <Navigate to={homeFor(user.role)} replace />;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await login(email.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Connexion impossible.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <AuthHero />
      <main id="contenu" className="auth-main">
      <section className="auth-card">
        <h1>Connexion</h1>
        <p className="muted">Connectez-vous pour accéder à la médiathèque.</p>
        <form onSubmit={submit} noValidate>
          <Field label="Adresse e-mail">
            {(id) => (
              <input id={id} type="email" autoComplete="username" required value={email}
                onChange={(e) => setEmail(e.target.value)} />
            )}
          </Field>
          <Field label="Mot de passe">
            {(id) => (
              <input id={id} type="password" autoComplete="current-password" required value={password}
                onChange={(e) => setPassword(e.target.value)} />
            )}
          </Field>
          <Alert kind="error">{error}</Alert>
          <button type="submit" className="block" disabled={busy || !email || !password}>
            {busy ? "Connexion…" : "Se connecter"}
          </button>
        </form>
        <p>
          Pas encore de compte ? <Link to="/inscription">Créer un compte adhérent</Link>
        </p>
      </section>
      </main>
    </div>
  );
}

export function RegisterPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", full_name: "", password: "", confirm: "" });
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (form.password !== form.confirm) {
      setError("Les mots de passe ne correspondent pas.");
      return;
    }
    try {
      await api.post("/auth/register", { email: form.email, full_name: form.full_name, password: form.password });
      setDone(true);
      setTimeout(() => navigate("/login"), 1500);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Inscription impossible.");
    }
  }

  const set = (key: keyof typeof form) => (e: { target: { value: string } }) =>
    setForm({ ...form, [key]: e.target.value });

  return (
    <div className="auth-page">
      <AuthHero />
      <main id="contenu" className="auth-main">
      <section className="auth-card">
        <h1>Créer un compte adhérent</h1>
        <form onSubmit={submit}>
          <Field label="Nom complet">
            {(id) => <input id={id} required value={form.full_name} onChange={set("full_name")} />}
          </Field>
          <Field label="Adresse e-mail">
            {(id) => <input id={id} type="email" required value={form.email} onChange={set("email")} />}
          </Field>
          <Field label="Mot de passe" hint="8 caractères minimum, avec au moins une lettre et un chiffre.">
            {(id, hint) => (
              <input id={id} type="password" autoComplete="new-password" required minLength={8}
                aria-describedby={hint} value={form.password} onChange={set("password")} />
            )}
          </Field>
          <Field label="Confirmation du mot de passe">
            {(id) => (
              <input id={id} type="password" autoComplete="new-password" required value={form.confirm}
                onChange={set("confirm")} />
            )}
          </Field>
          <Alert kind="error">{error}</Alert>
          <Alert kind="success">{done && "Compte créé ! Redirection vers la connexion…"}</Alert>
          <button type="submit" className="block">Créer mon compte</button>
        </form>
        <p>
          <Link to="/login">← Retour à la connexion</Link>
        </p>
      </section>
      </main>
    </div>
  );
}
