import { expect } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

export const ACCOUNTS = {
  admin: { email: "admin@bibliotrack.example", password: "Admin1234", name: "Alice Admin" },
  biblio: { email: "biblio@bibliotrack.example", password: "Biblio1234", name: "Bruno Bibliothécaire" },
  adherent: { email: "adherent@bibliotrack.example", password: "Adherent1234", name: "Chloé Adhérente" },
} as const;

/** Identifiant unique par test (exécution parallèle sur 3 navigateurs sans collision). */
export function uid(): string {
  return `${Date.now().toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`.toUpperCase();
}

/** ISBN-13 valide et unique (préfixe 979, clé calculée). */
export function uniqueIsbn(): string {
  const core = `979${String(Date.now() % 1e9).padStart(9, "0")}`.slice(0, 12);
  const rnd = String(Math.floor(Math.random() * 1000)).padStart(3, "0");
  const base = core.slice(0, 9) + rnd;
  const sum = [...base].reduce((acc, c, i) => acc + Number(c) * (i % 2 ? 3 : 1), 0);
  return base + ((10 - (sum % 10)) % 10);
}

export async function login(page: Page, email: string, password: string) {
  await page.goto("/login");
  await page.getByLabel("Adresse e-mail").fill(email);
  await page.getByLabel("Mot de passe").fill(password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page.getByTestId("current-user")).toBeVisible();
}

export async function loginAs(page: Page, who: keyof typeof ACCOUNTS) {
  const { email, password } = new Map(Object.entries(ACCOUNTS)).get(who)!;
  await login(page, email, password);
}

/** Client API authentifié pour préparer les données d'un test. */
export async function apiAs(request: APIRequestContext, email: string, password: string) {
  const r = await request.post("/api/auth/login", { data: { email, password } });
  expect(r.ok()).toBeTruthy();
  const { access_token } = await r.json();
  const headers = { Authorization: `Bearer ${access_token}` };
  return {
    get: async (url: string) => (await request.get(`/api${url}`, { headers })).json(),
    post: async (url: string, data?: unknown) => {
      const res = await request.post(`/api${url}`, { headers, data });
      expect(res.ok(), `${url} → ${res.status()} ${await res.text()}`).toBeTruthy();
      return res.json();
    },
  };
}

export async function staffApi(request: APIRequestContext) {
  return apiAs(request, ACCOUNTS.biblio.email, ACCOUNTS.biblio.password);
}

/** Crée un adhérent dédié au test (via l'inscription publique). */
export async function newMember(request: APIRequestContext) {
  const id = uid();
  const member = { email: `e2e.${id.toLowerCase()}@bibliotrack.example`, password: "Membre1234", full_name: `Membre E2E ${id}` };
  const r = await request.post("/api/auth/register", { data: member });
  expect(r.status()).toBe(201);
  return { ...member, id: (await r.json()).id as number };
}

/** Crée un ouvrage (avec N exemplaires) dédié au test. */
export async function newBook(request: APIRequestContext, copies = 1, title?: string) {
  const api = await staffApi(request);
  const id = uid();
  const categories = await api.get("/categories");
  const author = await api.post("/authors", { full_name: `Auteur E2E ${id}` });
  const book = await api.post("/books", {
    isbn: uniqueIsbn(),
    title: title ?? `Ouvrage E2E ${id}`,
    category_id: categories[0].id,
    author_ids: [author.id],
    publication_year: 2024,
  });
  const barcodes: string[] = [];
  for (let k = 0; k < copies; k++) {
    const barcode = `E2E-${id}-${k}`;
    await api.post(`/books/${book.id}/copies`, { barcode });
    barcodes.push(barcode);
  }
  return { ...book, barcodes } as { id: number; title: string; barcodes: string[] };
}
