/** Fonctions de présentation pures (testées unitairement avec Vitest). */

const LABELS = new Map<string, string>([
  ["ADMIN", "Administrateur"],
  ["BIBLIOTHECAIRE", "Bibliothécaire"],
  ["ADHERENT", "Adhérent"],
  ["DISPONIBLE", "Disponible"],
  ["EMPRUNTE", "Emprunté"],
  ["RESERVE", "Réservé"],
  ["EN_REPARATION", "En réparation"],
  ["RETIRE", "Retiré"],
  ["EN_COURS", "En cours"],
  ["EN_RETARD", "En retard"],
  ["RENDU", "Rendu"],
  ["PERDU", "Perdu"],
  ["EN_ATTENTE", "En attente"],
  ["HONOREE", "Honorée"],
  ["ANNULEE", "Annulée"],
  ["EXPIREE", "Expirée"],
  ["IMPAYEE", "Impayée"],
  ["PAYEE", "Payée"],
]);

export function label(code: string): string {
  return LABELS.get(code) ?? code;
}

export type Tone = "success" | "warning" | "danger" | "neutral" | "info";

const TONES = new Map<string, Tone>([
  ["DISPONIBLE", "success"],
  ["RENDU", "success"],
  ["PAYEE", "success"],
  ["HONOREE", "success"],
  ["EN_COURS", "info"],
  ["EMPRUNTE", "info"],
  ["EN_ATTENTE", "info"],
  ["RESERVE", "warning"],
  ["EN_REPARATION", "warning"],
  ["EN_RETARD", "danger"],
  ["PERDU", "danger"],
  ["IMPAYEE", "danger"],
]);

export function tone(code: string): Tone {
  return TONES.get(code) ?? "neutral";
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const [y, m, d] = iso.slice(0, 10).split("-");
  return d && m && y ? `${d}/${m}/${y}` : "—";
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return `${formatDate(iso)} ${iso.slice(11, 16)}`.trim();
}

export function formatMoney(amount: string | number): string {
  const value = typeof amount === "number" ? amount : Number.parseFloat(amount);
  if (Number.isNaN(value)) return "—";
  return `${value.toFixed(2).replace(".", ",")} €`;
}

export function formatIsbn(isbn: string): string {
  return isbn.length === 13
    ? `${isbn.slice(0, 3)}-${isbn.slice(3, 4)}-${isbn.slice(4, 9)}-${isbn.slice(9, 12)}-${isbn.slice(12)}`
    : isbn;
}

/** Jours restants avant l'échéance (négatif = retard). `today` injectable pour les tests. */
export function daysUntil(dueIso: string, today: Date = new Date()): number {
  const due = Date.UTC(+dueIso.slice(0, 4), +dueIso.slice(5, 7) - 1, +dueIso.slice(8, 10));
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due - now) / 86_400_000);
}

export function pageCount(total: number, size: number): number {
  return Math.max(1, Math.ceil(total / size));
}

/** Validation côté client de la clé ISBN (miroir de la règle serveur RG-01). */
export function isValidIsbn(raw: string): boolean {
  const isbn = raw.replace(/[\s-]/g, "").toUpperCase();
  if (/^\d{9}[\dX]$/.test(isbn)) {
    const sum = [...isbn].reduce((acc, c, i) => acc + (10 - i) * (c === "X" ? 10 : +c), 0);
    return sum % 11 === 0;
  }
  if (/^97[89]\d{10}$/.test(isbn)) {
    const sum = [...isbn.slice(0, 12)].reduce((acc, c, i) => acc + +c * (i % 2 ? 3 : 1), 0);
    return (10 - (sum % 10)) % 10 === +isbn[12];
  }
  return false;
}
