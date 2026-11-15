import { describe, expect, it } from "vitest";
import {
  daysUntil,
  formatDate,
  formatDateTime,
  formatIsbn,
  formatMoney,
  isValidIsbn,
  label,
  pageCount,
  tone,
} from "./format";
import { buildQuery, errorMessage } from "../api/client";

describe("[EQ-USA-01] formatage à la française", () => {
  it("formate les dates ISO en JJ/MM/AAAA", () => {
    expect(formatDate("2026-03-23")).toBe("23/03/2026");
    expect(formatDate("2026-03-23T10:15:00")).toBe("23/03/2026");
    expect(formatDate(null)).toBe("—");
    expect(formatDateTime("2026-03-23T10:15:00")).toBe("23/03/2026 10:15");
    expect(formatDateTime(undefined)).toBe("—");
  });

  it("formate les montants en euros à la française", () => {
    expect(formatMoney("5.5")).toBe("5,50 €");
    expect(formatMoney(20)).toBe("20,00 €");
    expect(formatMoney("abc")).toBe("—");
  });

  it("formate un ISBN-13 avec des tirets", () => {
    expect(formatIsbn("9782070368228")).toBe("978-2-07036-822-8");
    expect(formatIsbn("123")).toBe("123");
  });

  it("traduit les codes de statut et associe une couleur", () => {
    expect(label("EN_RETARD")).toBe("En retard");
    expect(label("INCONNU")).toBe("INCONNU");
    expect(tone("EN_RETARD")).toBe("danger");
    expect(tone("DISPONIBLE")).toBe("success");
    expect(tone("ANNULEE")).toBe("neutral");
  });
});

describe("calculs", () => {
  it("[RG-05] calcule les jours restants avant échéance", () => {
    const today = new Date(2026, 2, 20);
    expect(daysUntil("2026-03-23", today)).toBe(3);
    expect(daysUntil("2026-03-20", today)).toBe(0);
    expect(daysUntil("2026-03-18", today)).toBe(-2);
  });

  it("calcule le nombre de pages", () => {
    expect(pageCount(0, 20)).toBe(1);
    expect(pageCount(41, 20)).toBe(3);
  });

  it("[RG-01] valide la clé ISBN comme le serveur", () => {
    expect(isValidIsbn("978-2-07-036822-8")).toBe(true);
    expect(isValidIsbn("207036822X")).toBe(true);
    expect(isValidIsbn("9782070368229")).toBe(false);
    expect(isValidIsbn("2070368228")).toBe(false);
    expect(isValidIsbn("abc")).toBe(false);
  });
});

describe("[EQ-USA-01] client API : messages d'erreur", () => {
  it("construit une query string en ignorant les valeurs vides", () => {
    expect(buildQuery({ q: "dune", page: 2, empty: "", none: undefined, flag: false })).toBe(
      "?q=dune&page=2&flag=false",
    );
    expect(buildQuery({})).toBe("");
  });

  it("normalise les messages d'erreur de l'API", () => {
    expect(errorMessage(409, { detail: "Quota atteint", code: "RG-02" })).toBe("Quota atteint");
    expect(errorMessage(422, { detail: [{ loc: ["body", "isbn"], msg: "ISBN invalide" }] })).toBe(
      "isbn : ISBN invalide",
    );
    expect(errorMessage(503, null)).toMatch(/indisponible/);
    expect(errorMessage(500, null)).toBe("Erreur interne du serveur.");
    expect(errorMessage(418, {})).toBe("Erreur 418");
  });
});
