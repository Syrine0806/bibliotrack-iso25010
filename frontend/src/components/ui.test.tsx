import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Alert, BarChart, Field, Pagination, StatusBadge } from "./ui";

afterEach(cleanup);

describe("[EQ-USA-02] composants d'interface accessibles", () => {
  it("Alert d'erreur utilise role=alert, les autres role=status", () => {
    render(<Alert kind="error">Quota atteint</Alert>);
    expect(screen.getByRole("alert").textContent).toBe("Quota atteint");
    cleanup();
    render(<Alert kind="success">OK</Alert>);
    expect(screen.getByRole("status").textContent).toBe("OK");
  });

  it("Alert vide n'affiche rien", () => {
    const { container } = render(<Alert kind="error">{""}</Alert>);
    expect(container.innerHTML).toBe("");
  });

  it("StatusBadge traduit le statut et applique la couleur", () => {
    render(<StatusBadge status="EN_RETARD" />);
    const badge = screen.getByText("En retard");
    expect(badge.className).toContain("badge-danger");
  });

  it("Field associe le label au champ et l'aide via aria-describedby", () => {
    render(
      <Field label="ISBN" hint="ISBN-10 ou 13">
        {(id, hint) => <input id={id} aria-describedby={hint} />}
      </Field>,
    );
    const input = screen.getByLabelText("ISBN");
    const hintId = input.getAttribute("aria-describedby");
    expect(hintId && document.getElementById(hintId)?.textContent).toBe("ISBN-10 ou 13");
  });

  it("Pagination désactive les bornes et notifie le changement", async () => {
    const onChange = vi.fn();
    render(<Pagination page={1} size={20} total={45} onChange={onChange} />);
    expect(screen.getByText(/Page 1 \/ 3 — 45 résultats/)).toBeTruthy();
    expect((screen.getByRole("button", { name: /Précédent/ }) as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(screen.getByRole("button", { name: /Suivant/ }));
    expect(onChange).toHaveBeenCalledWith(2);
  });

  it("BarChart expose les données dans un tableau lisible par lecteur d'écran", () => {
    render(<BarChart title="Emprunts" data={[{ label: "2026-01", value: 4 }, { label: "2026-02", value: 8 }]} />);
    expect(screen.getByRole("figure", { name: "Emprunts" })).toBeTruthy();
    expect(screen.getAllByRole("rowheader").map((th) => th.textContent)).toEqual(["2026-01", "2026-02"]);
  });

  it("BarChart sans données affiche un message", () => {
    render(<BarChart title="Vide" data={[]} />);
    expect(screen.getByText(/Aucune donnée/)).toBeTruthy();
  });
});
