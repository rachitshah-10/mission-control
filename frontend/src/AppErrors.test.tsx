import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Mission Control non-JSON error handling", () => {
  it("shows readable error instead of JSON parse failure on plain-text 500", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(new Response("Internal Server Error", { status: 500 }));

    render(<App />);
    await screen.findByText(/No reports filed yet/i);

    fireEvent.change(screen.getByLabelText(/Engineer Name/i), { target: { value: "Rachit" } });
    fireEvent.change(screen.getByLabelText(/Station/i), { target: { value: "PROP-02" } });
    fireEvent.change(screen.getByLabelText(/Wind \(knots\)/i), { target: { value: "23" } });
    fireEvent.change(screen.getByLabelText(/Temp \(C\)/i), { target: { value: "6" } });
    fireEvent.change(screen.getByLabelText(/Fuel \(%\)/i), { target: { value: "99" } });
    fireEvent.change(screen.getByLabelText(/Anomaly Note/i), {
      target: { value: "Telemetry glitch" },
    });

    fireEvent.click(screen.getByRole("button", { name: /Submit Report/i }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/Internal Server Error/i);
    expect(alert).not.toHaveTextContent(/expected pattern/i);
  });
});
