import { expect, test } from "@playwright/test";
import { ACCOUNTS, login, loginAs, newMember, uid } from "./helpers";

test.describe("Authentification et rôles", () => {
  test("[EF-01][EF-02] l'administrateur accède à toutes les rubriques", async ({ page }) => {
    await loginAs(page, "admin");
    await expect(page).toHaveURL(/\/dashboard$/);
    const nav = page.getByRole("navigation", { name: "Navigation principale" });
    for (const item of ["Tableau de bord", "Catalogue", "Emprunts", "Utilisateurs", "Journal d'audit"]) {
      await expect(nav.getByRole("link", { name: item })).toBeVisible();
    }
  });

  test("[EF-01][EF-02] le bibliothécaire n'a pas accès au journal d'audit", async ({ page }) => {
    await loginAs(page, "biblio");
    const nav = page.getByRole("navigation", { name: "Navigation principale" });
    await expect(nav.getByRole("link", { name: "Tableau de bord" })).toBeVisible();
    await expect(nav.getByRole("link", { name: "Journal d'audit" })).toHaveCount(0);
    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: "Accès refusé" })).toBeVisible();
  });

  test("[EF-01][EF-02][EQ-SEC-03] l'adhérent arrive sur le catalogue avec un menu restreint", async ({ page }) => {
    await loginAs(page, "adherent");
    await expect(page).toHaveURL(/\/catalogue$/);
    const nav = page.getByRole("navigation", { name: "Navigation principale" });
    await expect(nav.getByRole("link", { name: "Tableau de bord" })).toHaveCount(0);
    await expect(nav.getByRole("link", { name: "Utilisateurs" })).toHaveCount(0);
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Accès refusé" })).toBeVisible();
  });

  test("[EF-01][EQ-SEC-04] un mauvais mot de passe affiche un message générique", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Adresse e-mail").fill(ACCOUNTS.biblio.email);
    await page.getByLabel("Mot de passe").fill("MauvaisMotDePasse1");
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page.getByRole("alert")).toHaveText("Identifiants invalides ou compte verrouillé.");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("[EF-01][RG-10] le compte est verrouillé après 5 échecs", async ({ page, request }) => {
    const member = await newMember(request);
    await page.goto("/login");
    await page.getByLabel("Adresse e-mail").fill(member.email);
    for (let i = 0; i < 5; i++) {
      await page.getByLabel("Mot de passe").fill(`Faux${i}12345`);
      await page.getByRole("button", { name: "Se connecter" }).click();
      await expect(page.getByRole("alert")).toBeVisible();
    }
    await page.getByLabel("Mot de passe").fill(member.password);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page.getByRole("alert")).toContainText("verrouillé");
  });

  test("[EF-01][EQ-USA-01] inscription d'un adhérent puis connexion", async ({ page }) => {
    const id = uid().toLowerCase();
    await page.goto("/login");
    await page.getByRole("link", { name: "Créer un compte adhérent" }).click();
    await page.getByLabel("Nom complet").fill(`Nouvel Adhérent ${id}`);
    await page.getByLabel("Adresse e-mail").fill(`inscrit.${id}@bibliotrack.example`);
    await page.getByLabel("Mot de passe", { exact: true }).fill("faiblesse");
    await page.getByLabel("Confirmation du mot de passe").fill("faiblesse");
    await page.getByRole("button", { name: "Créer mon compte" }).click();
    await expect(page.getByRole("alert")).toContainText("Mot de passe invalide");

    await page.getByLabel("Mot de passe", { exact: true }).fill("Solide1234");
    await page.getByLabel("Confirmation du mot de passe").fill("Solide1234");
    await page.getByRole("button", { name: "Créer mon compte" }).click();
    await expect(page.getByRole("status")).toContainText("Compte créé");
    await expect(page).toHaveURL(/\/login$/, { timeout: 5000 });
    await login(page, `inscrit.${id}@bibliotrack.example`, "Solide1234");
    await expect(page.getByTestId("current-user")).toContainText("Adhérent");
  });

  test("[EF-01] la déconnexion protège les pages", async ({ page }) => {
    await loginAs(page, "adherent");
    await page.getByRole("button", { name: "Se déconnecter" }).click();
    await page.goto("/emprunts");
    await expect(page).toHaveURL(/\/login$/);
  });
});
