import { expect, test } from "@playwright/test";
import { loginAs, newMember, uid } from "./helpers";

test.describe("Pilotage et administration", () => {
  test("[EF-11] tableau de bord : indicateurs agrégés et filtres", async ({ page }, info) => {
    await loginAs(page, "biblio");
    const kpis = page.getByTestId("kpis");
    await expect(kpis.getByText("Ouvrages")).toBeVisible();
    await expect(kpis).toContainText(/Emprunts actifs\s*\d+/);
    await expect(kpis).toContainText(/Emprunts en retard\s*\d+/);
    await expect(page.getByRole("figure", { name: "Emprunts par mois" })).toBeVisible();
    await expect(page.getByRole("figure", { name: "Top 5 des ouvrages empruntés" }).getByRole("row")).toHaveCount(5);
    if (info.project.name === "chromium") {
      await page.screenshot({ path: "../reports/e2e/screenshots/02-tableau-de-bord.png", fullPage: true });
    }
    const allBooks = await kpis.locator(".stat", { hasText: "Ouvrages" }).locator(".stat-value").textContent();
    await page.getByLabel("Catégorie", { exact: true }).selectOption({ label: "Philosophie" });
    await expect(kpis.locator(".stat", { hasText: "Ouvrages" }).locator(".stat-value")).not.toHaveText(allBooks ?? "");
    const byCategory = page.getByRole("figure", { name: "Emprunts par catégorie" }).getByRole("rowheader");
    await expect(byCategory).toHaveText(["Philosophie"]);
  });

  test("[EF-07][EF-02] l'administrateur crée un bibliothécaire puis modifie son rôle", async ({ page }) => {
    const id = uid().toLowerCase();
    await loginAs(page, "admin");
    await page.getByRole("link", { name: "Utilisateurs" }).click();
    await page.getByLabel("Nom complet").fill(`Bib ${id}`);
    await page.getByLabel("E-mail", { exact: true }).fill(`bib.${id}@bibliotrack.example`);
    await page.getByLabel("Mot de passe initial").fill("Initial1234");
    await page.getByLabel("Rôle", { exact: true }).first().selectOption("BIBLIOTHECAIRE");
    await page.getByRole("button", { name: "Créer" }).click();
    await expect(page.getByRole("status").filter({ hasText: `Compte bib.${id}@bibliotrack.example créé` })).toBeVisible();

    await page.getByLabel("Recherche (nom, e-mail)").fill(`bib.${id}`);
    const row = page.getByRole("row", { name: `bib.${id}` });
    await expect(row).toHaveCount(1);
    await row.getByLabel(`Rôle de Bib ${id}`).selectOption("ADHERENT");
    await expect(page.getByRole("status").filter({ hasText: "Rôle modifié" })).toBeVisible();
    await row.getByRole("button", { name: "Désactiver" }).click();
    await expect(row).toContainText("Inactif");
  });

  test("[EF-13] le journal d'audit trace les actions sensibles et se filtre", async ({ page, request }) => {
    const member = await newMember(request);
    await request.post("/api/auth/login", { data: { email: member.email, password: "Mauvais999" } });
    await loginAs(page, "admin");
    await page.getByRole("link", { name: "Journal d'audit" }).click();
    await page.getByLabel("Action").selectOption("LOGIN_FAILED");
    await page.getByLabel("Utilisateur (e-mail)").fill(member.email);
    const row = page.getByRole("row", { name: member.email });
    await expect(row.first()).toContainText("LOGIN_FAILED");
    await expect(row.first()).toContainText("User");
  });
});
