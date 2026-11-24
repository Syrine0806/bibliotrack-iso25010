/** Composants d'interface génériques, accessibles (WCAG 2.1 : labels, rôles ARIA, contraste). */
import { useCallback, useEffect, useId, useState } from "react";
import type { ReactNode } from "react";
import { ApiError } from "../api/client";
import type { CountItem } from "../api/types";
import { label, pageCount, tone } from "../utils/format";
import { Icon } from "./icons";
import type { IconName } from "./icons";

export function Alert({ kind, children }: { kind: "error" | "success" | "info"; children: ReactNode }) {
  if (!children) return null;
  return (
    <div className={`alert alert-${kind}`} role={kind === "error" ? "alert" : "status"}>
      <Icon name={kind === "error" ? "alert" : "check"} size={18} />
      <span>{children}</span>
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge badge-${tone(status)}`}>{label(status)}</span>;
}

export function Field({
  label: text,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: (id: string, describedBy?: string) => ReactNode;
}) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  return (
    <div className="field">
      <label htmlFor={id}>{text}</label>
      {children(id, hintId)}
      {hint && (
        <small id={hintId} className="hint">
          {hint}
        </small>
      )}
    </div>
  );
}

export function Pagination({
  page,
  size,
  total,
  onChange,
}: {
  page: number;
  size: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = pageCount(total, size);
  return (
    <nav className="pagination" aria-label="Pagination">
      <button type="button" onClick={() => onChange(page - 1)} disabled={page <= 1}>
        ← Précédent
      </button>
      <span aria-live="polite">
        Page {page} / {pages} — {total} résultat{total > 1 ? "s" : ""}
      </span>
      <button type="button" onClick={() => onChange(page + 1)} disabled={page >= pages}>
        Suivant →
      </button>
    </nav>
  );
}

export function StatCard({ title, value, tone: t = "neutral", icon }: { title: string; value: ReactNode; tone?: string; icon?: IconName }) {
  return (
    <div className={`stat stat-${t}`}>
      {icon && (
        <span className="stat-icon">
          <Icon name={icon} />
        </span>
      )}
      <span className="stat-body">
        <span className="stat-title">{title}</span>
        <span className="stat-value">{value}</span>
      </span>
    </div>
  );
}

/** Histogramme horizontal en SVG/HTML, accompagné d'un tableau accessible aux lecteurs d'écran. */
export function BarChart({ title, data }: { title: string; data: CountItem[] }) {
  const max = Math.max(1, ...data.map((d) => d.value));
  const captionId = useId();
  return (
    <figure className="chart" aria-labelledby={captionId}>
      <figcaption id={captionId}>{title}</figcaption>
      {data.length === 0 ? (
        <p className="muted">Aucune donnée sur la période.</p>
      ) : (
        <table className="bars">
          <tbody>
            {data.map((d) => (
              <tr key={d.label}>
                <th scope="row">{label(d.label)}</th>
                <td>
                  <span className="bar" style={{ width: `${(d.value / max) * 100}%` }} aria-hidden="true" />
                  <span className="bar-value">{d.value}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </figure>
  );
}

export function Loading() {
  return (
    <p className="muted" role="status">
      Chargement…
    </p>
  );
}

/** Hook de chargement de données : état, erreurs, rechargement ; ignore les réponses obsolètes. */
export function useAsync<T>(loader: () => Promise<T>, deps: unknown[]) {
  const [tick, setTick] = useState(0);
  const key = `${JSON.stringify(deps)}#${tick}`;
  const [state, setState] = useState<{ data: T | null; error: string; forKey: string }>({
    data: null,
    error: "",
    forKey: "",
  });

  useEffect(() => {
    let cancelled = false;
    loader()
      .then((data) => !cancelled && setState({ data, error: "", forKey: key }))
      .catch((e: unknown) => {
        const error = e instanceof ApiError ? e.message : String(e);
        if (!cancelled) setState((s) => ({ ...s, error, forKey: key }));
      });
    return () => {
      cancelled = true;
    };
    // `key` encode les dépendances déclarées par l'appelant (+ le compteur de rechargement).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const reload = useCallback(() => setTick((t) => t + 1), []);
  return { data: state.data, error: state.error, loading: state.forKey !== key, reload };
}

/** Exécute une action utilisateur et expose un message de succès / d'erreur. */
export function useAction() {
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);

  const run = useCallback(async (fn: () => Promise<unknown>, okMessage: string) => {
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await fn();
      setSuccess(okMessage);
      return true;
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
      return false;
    } finally {
      setBusy(false);
    }
  }, []);

  return { error, success, busy, run, setError, setSuccess };
}
