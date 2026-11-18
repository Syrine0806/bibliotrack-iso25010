import { expect, test } from "@playwright/test";
import { loginAs, newBook, uid, uniqueIsbn } from "./helpers";

test.describe("Catalogue", () => {
  test("[EF-12] recherche plein texte, filtres et pagination sur ~5000 ouvrages", async ({ page }) => {
    const initial = page.waitForResponse((r) => r.url().includes("/api/books?") && !r.url().includes("q="));
    await loginAs(page, "adherent");
    const catalogSize = (await (await initial).json()).total as number;
    expect(catalogSize).toBeGreaterThanOrEqual(5000); // fort volume (données de démo + ajouts)
    await expect(page.getByText(`Page 1 / ${Math.ceil(catalogSize / 20)} — ${catalogSize} résultats`)).toBeVisible();
    await page.getByLabel("Titre, auteur ou ISBN").fill("algorithme");
    const [response] = await Promise.all([
      page.waitForResponse((r) => r.url().includes("/api/books?") && r.url().includes("q=algorithme")),
      page.getByRole("button", { name: "Rechercher" }).click(),
    ]);
    const total = (await response.json()).total as number;
    await expect(page.getByText(`— ${total} résultats`)).toBeVisible();
    expect(total).toBeGreaterThan(20);
    expect(total).toBeLessThan(catalogSize);
    const rows = page.getByRole("table").getByRole("row");
    await expect(rows).toHaveCount(21); // en-tête + 20 lignes
    await expect(rows.nth(1)).toContainText(/algorithme/i);

    await page.getByRole("button", { name: "Suivant →" }).click();
    await expect(page.getByText(/Page 2 \//)).toBeVisible();

    await page.getByLabel("Catégorie", { exact: true }).selectOption({ label: "Informatique" });
    await page.getByLabel("Disponibles uniquement").check();
    await Promise.all([
      page.waitForResponse((r) => r.url().includes("available_only=true")),
      page.getByRole("button", { name: "Rechercher" }).click(),
    ]);
    await expect(page.getByText(/Page 1 \//)).toBeVisible();
    await expect(rows.nth(1).getByRole("cell").nth(2)).toHaveText("Informatique");
  });

  test("[EF-12] recherche sans résultat", async ({ page }) => {
    await loginAs(page, "adherent");
    await page.getByLabel("Titre, auteur ou ISBN").fill(`introuvable-${uid()}`);
    await page.getByRole("button", { name: "Rechercher" }).click();
    await expect(page.getByText("Aucun ouvrage ne correspond à vos critères.")).toBeVisible();
  });

  test("[EF-05][EF-06][RG-01] le bibliothécaire crée un ouvrage puis ajoute un exemplaire", async ({ page }) => {
    const id = uid();
    await loginAs(page, "biblio");
    await page.goto("/catalogue/nouveau");
    const isbn = page.getByLabel("ISBN");
    await isbn.fill("978-2-07-036822-9"); // clé fausse
    await expect(page.getByText("Clé de contrôle ISBN invalide.")).toBeVisible();
    await expect(page.getByRole("button", { name: "Enregistrer" })).toBeDisabled();

    await isbn.fill(uniqueIsbn());
    await page.getByLabel("Titre").fill(`Le Livre E2E ${id}`);
    await page.getByLabel("Année de publication").fill("2025");
    await page.getByLabel("Catégorie").selectOption({ label: "Roman" });
    await page.getByLabel("Auteur(s)").selectOption({ index: 0 });
    await page.getByRole("button", { name: "Enregistrer" }).click();

    await expect(page.getByRole("heading", { level: 1, name: `Le Livre E2E ${id}` })).toBeVisible();
    await expect(page.getByTestId("availability")).toHaveText("0 exemplaire(s) disponible(s) sur 0");

    await page.getByLabel("Code-barres").fill(`CB-${id}`);
    await page.getByLabel("Emplacement").fill("R12-E3");
    await page.getByRole("button", { name: "Ajouter" }).click();
    await expect(page.getByRole("status")).toContainText(`Exemplaire CB-${id} ajouté`);
    await expect(page.getByTestId("availability")).toHaveText("1 exemplaire(s) disponible(s) sur 1");
    await expect(page.getByRole("cell", { name: `CB-${id}` })).toBeVisible();
  });

  test("[EF-06][RG-12] un code-barres en double est refusé avec un message clair", async ({ page, request }) => {
    const book = await newBook(request, 1);
    await loginAs(page, "biblio");
    await page.goto(`/catalogue/${book.id}`);
    await page.getByLabel("Code-barres").fill(book.barcodes[0]);
    await page.getByRole("button", { name: "Ajouter" }).click();
    await expect(page.getByRole("alert")).toContainText("déjà attribué");
  });

  test("[EF-06][RG-04] mise en réparation d'un exemplaire", async ({ page, request }) => {
    const book = await newBook(request, 1);
    await loginAs(page, "biblio");
    await page.goto(`/catalogue/${book.id}`);
    await page.getByRole("button", { name: "En réparation" }).click();
    await expect(page.getByRole("row", { name: book.barcodes[0] })).toContainText("En réparation");
    await expect(page.getByTestId("availability")).toHaveText("0 exemplaire(s) disponible(s) sur 1");
  });

  test("[EF-14][EQ-COMP-02] pré-remplissage par ISBN via le service tiers Open Library", async ({ page }) => {
    await loginAs(page, "biblio");
    await page.goto("/catalogue/nouveau");
    await page.getByLabel("ISBN").fill("9782070360024"); // L'Étranger, Folio
    await page.getByRole("button", { name: "Rechercher (Open Library)" }).click();
    // Deux issues valides : données tierces reçues, ou repli explicite si le service est injoignable.
    await expect(page.getByText(/Trouvé sur Open Library|indisponible|inconnu/)).toBeVisible({ timeout: 10_000 });
  });
});
