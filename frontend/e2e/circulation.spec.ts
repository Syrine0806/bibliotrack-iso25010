import { expect, test } from "@playwright/test";
import { apiAs, login, loginAs, newBook, newMember, staffApi } from "./helpers";

test.describe("Parcours de circulation", () => {
  test("[EF-08][WF-01][RG-05] emprunt au comptoir, prolongation par l'adhérent, retour", async ({ page, request }, info) => {
    const member = await newMember(request);
    const book = await newBook(request, 1);

    // 1. Le bibliothécaire enregistre l'emprunt
    await loginAs(page, "biblio");
    await page.goto("/emprunts");
    await page.getByLabel("Rechercher l'adhérent (nom ou e-mail)").fill(member.full_name);
    await page.getByLabel("Adhérent", { exact: true }).selectOption({ label: `${member.full_name} (${member.email})` });
    await page.getByLabel("Code-barres de l'exemplaire").fill(book.barcodes[0]);
    await page.getByRole("button", { name: "Enregistrer l'emprunt" }).click();
    await expect(page.getByRole("status").filter({ hasText: `Emprunt enregistré pour l'exemplaire ${book.barcodes[0]}` })).toBeVisible();
    if (info.project.name === "chromium") {
      await page.screenshot({ path: "../reports/e2e/screenshots/01-emprunt-enregistre.png", fullPage: true });
    }

    // 2. L'adhérent voit son emprunt (J-21) et le prolonge une fois
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await login(page, member.email, member.password);
    await page.getByRole("link", { name: "Emprunts" }).click();
    await expect(page.getByRole("heading", { name: "Mes emprunts" })).toBeVisible();
    const row = page.getByRole("row", { name: book.title });
    await expect(row).toContainText("En cours");
    await expect(row).toContainText("J-21");
    await row.getByRole("button", { name: "Prolonger" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Emprunt prolongé" })).toBeVisible();
    await expect(row).toContainText("J-35");
    await expect(row.getByRole("button", { name: "Prolonger" })).toHaveCount(0);

    // 3. Retour au comptoir
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await loginAs(page, "biblio");
    await page.goto("/emprunts");
    await page.getByLabel("Recherche (adhérent, titre, code-barres)").fill(book.barcodes[0]);
    const staffRow = page.getByRole("row", { name: book.title });
    await staffRow.getByRole("button", { name: "Retour" }).click();
    await expect(page.getByRole("status").filter({ hasText: `Retour de « ${book.title} » enregistré` })).toBeVisible();
    await expect(staffRow).toContainText("Rendu");
  });

  test("[EF-08][RG-02] le quota de 5 emprunts est appliqué et expliqué", async ({ page, request }) => {
    const member = await newMember(request);
    const api = await staffApi(request);
    for (let i = 0; i < 5; i++) {
      const b = await newBook(request, 1);
      await api.post("/loans", { user_id: member.id, barcode: b.barcodes[0] });
    }
    const sixth = await newBook(request, 1);
    await loginAs(page, "biblio");
    await page.goto("/emprunts");
    await page.getByLabel("Rechercher l'adhérent (nom ou e-mail)").fill(member.email);
    await page.getByLabel("Adhérent", { exact: true }).selectOption({ index: 1 });
    await page.getByLabel("Code-barres de l'exemplaire").fill(sixth.barcodes[0]);
    await page.getByRole("button", { name: "Enregistrer l'emprunt" }).click();
    await expect(page.getByRole("alert")).toContainText("Quota atteint : 5 emprunts simultanés maximum.");
  });

  test("[EF-09][WF-02][RG-07][RG-08] réservation d'un ouvrage indisponible, file d'attente et annulation", async ({ page, request }) => {
    const borrower = await newMember(request);
    const member = await newMember(request);
    const book = await newBook(request, 1);
    const api = await staffApi(request);
    await api.post("/loans", { user_id: borrower.id, barcode: book.barcodes[0] });

    await login(page, member.email, member.password);
    await page.goto(`/catalogue/${book.id}`);
    await expect(page.getByTestId("availability")).toHaveText("0 exemplaire(s) disponible(s) sur 1");
    await page.getByRole("button", { name: "Réserver cet ouvrage" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Réservation enregistrée" })).toBeVisible();

    await page.getByRole("link", { name: "Réservations" }).click();
    const row = page.getByRole("row", { name: book.title });
    await expect(row).toContainText("En attente");
    await expect(row).toContainText("n° 1 dans la file");
    await row.getByRole("button", { name: "Annuler" }).click();
    await expect(row).toContainText("Annulée");
  });

  test("[EF-10][WF-03][RG-03][RG-06] retard → pénalité → blocage → encaissement", async ({ page, request }) => {
    const member = await newMember(request);
    const api = await staffApi(request);
    await api.post("/penalties", { user_id: member.id, amount: "4.50", reason: "Retard de 9 jour(s) (E2E)" });
    const book = await newBook(request, 1);

    await login(page, member.email, member.password);
    await page.getByRole("link", { name: "Pénalités" }).click();
    await expect(page.getByRole("status")).toContainText("4,50 € de pénalités impayées");
    await page.getByRole("button", { name: "Se déconnecter" }).click();

    await loginAs(page, "biblio");
    await page.goto("/emprunts");
    await page.getByLabel("Rechercher l'adhérent (nom ou e-mail)").fill(member.email);
    await page.getByLabel("Adhérent", { exact: true }).selectOption({ index: 1 });
    await page.getByLabel("Code-barres de l'exemplaire").fill(book.barcodes[0]);
    await page.getByRole("button", { name: "Enregistrer l'emprunt" }).click();
    await expect(page.getByRole("alert")).toContainText("Pénalités impayées (4.50 €)");

    await page.getByRole("link", { name: "Pénalités" }).click();
    const row = page.getByRole("row", { name: member.full_name });
    await row.getByRole("button", { name: "Encaisser" }).click();
    await expect(page.getByRole("status").filter({ hasText: "Paiement enregistré" })).toBeVisible();

    const memberApi = await apiAs(request, member.email, member.password);
    const penalties = await memberApi.get("/penalties?status=IMPAYEE");
    expect(penalties.total).toBe(0);
  });
});
