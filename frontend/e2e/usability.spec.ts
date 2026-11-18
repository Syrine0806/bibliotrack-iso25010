import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";
import * as fs from "node:fs";
import { loginAs } from "./helpers";

/** Analyse axe-core (WCAG 2.1 A/AA) : aucune violation « serious » ou « critical » tolérée. */
async function audit(page: Page, name: string, browser: string) {
  await page.waitForLoadState("networkidle");
  const results = await new AxeBuilder({ page }).withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]).analyze();
  const blocking = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  if (browser === "chromium") {
    fs.mkdirSync("../reports/e2e/accessibility", { recursive: true });
    fs.writeFileSync(
      `../reports/e2e/accessibility/${name}.json`,
      JSON.stringify(
        {
          page: name,
          url: page.url(),
          passes: results.passes.length,
          violations: results.violations.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length })),
        },
        null,
        2,
      ),
    );
  }
  expect(blocking, JSON.stringify(blocking.map((v) => `${v.id}: ${v.help}`), null, 2)).toEqual([]);
}

test.describe("Facilité d'utilisation et accessibilité", () => {
  test("[EQ-USA-02] page de connexion accessible", async ({ page }, info) => {
    await page.goto("/login");
    await audit(page, "connexion", info.project.name);
  });

  const pages: [string, string, "admin" | "biblio" | "adherent"][] = [
    ["catalogue", "/catalogue", "adherent"],
    ["emprunts", "/emprunts", "biblio"],
    ["tableau-de-bord", "/dashboard", "biblio"],
    ["utilisateurs", "/utilisateurs", "admin"],
    ["audit", "/audit", "admin"],
    ["referentiels", "/referentiels", "biblio"],
  ];
  for (const [name, url, who] of pages) {
    test(`[EQ-USA-02] page ${name} accessible (WCAG 2.1 AA)`, async ({ page }, info) => {
      await loginAs(page, who);
      await page.goto(url);
      await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
      await audit(page, name, info.project.name);
    });
  }

  test("[EQ-USA-01] connexion et navigation entièrement au clavier", async ({ page, browserName }) => {
    test.skip(browserName === "webkit", "WebKit/macOS ne tabule pas sur les liens par défaut (réglage OS)");
    await page.goto("/login");
    await page.keyboard.press("Tab");
    await expect(page.getByLabel("Adresse e-mail")).toBeFocused();
    await page.keyboard.type("biblio@bibliotrack.example");
    await page.keyboard.press("Tab");
    await page.keyboard.type("Biblio1234");
    await page.keyboard.press("Enter");
    await expect(page.getByTestId("current-user")).toBeVisible();
    // Lien d'évitement : premier élément focusable
    await page.keyboard.press("Tab");
    const skip = page.getByRole("link", { name: "Aller au contenu" });
    await expect(skip).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#contenu$/);
  });

  test("[EQ-USA-01] messages d'erreur compréhensibles et en français", async ({ page }) => {
    await loginAs(page, "biblio");
    await page.goto("/emprunts");
    await page.getByLabel("Rechercher l'adhérent (nom ou e-mail)").fill("adherent@");
    await page.getByLabel("Adhérent", { exact: true }).selectOption({ index: 1 });
    await page.getByLabel("Code-barres de l'exemplaire").fill("CODE-INEXISTANT");
    await page.getByRole("button", { name: "Enregistrer l'emprunt" }).click();
    await expect(page.getByRole("alert")).toHaveText(/Exemplaire introuvable/);
  });

  test("[EQ-USA-01][EQ-COMP-01] affichage responsive sur mobile", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await loginAs(page, "adherent");
    await expect(page.getByRole("heading", { name: "Catalogue" })).toBeVisible();
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
});
