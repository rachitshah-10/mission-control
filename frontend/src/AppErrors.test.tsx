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

  it("renders collapsible sections for dense safety/note and step trace details", async () => {
    const sample = {
      id: 1,
      name: "Rachit",
      station: "PROP-01",
      wind_knots: 14,
      temp_c: 15,
      fuel_pct: 99,
      note: "Raw sensor jitter on valve B.",
      verdict: "go",
      violations: [],
      subsystem: "propulsion",
      severity: "low",
      brief_by_minutes: 30,
      hidden_instructions_flagged: false,
      missing_details_flagged: false,
      panic_tone_flagged: false,
      review_required: false,
      briefing_text: "Nominal telemetry.",
      draft_rounds: 1,
      approval_status: "pending",
      approved_by: null,
      approved_at: null,
      total_tokens: 50,
      total_cost_usd: 0.0002,
      created_at: "2026-11-17T14:00:00Z",
      steps: [
        {
          id: 1,
          report_id: 1,
          step_order: 1,
          step_name: "launch_limits",
          input_tokens: 0,
          output_tokens: 0,
          total_tokens: 0,
          cost_usd: 0,
          output_summary: "verdict=go",
          detail: { verdict: "go" },
          created_at: "2026-11-17T14:00:00Z",
        },
      ],
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([sample]), { status: 200 })
    );

    render(<App />);
    await screen.findByText(/Nominal telemetry/i);

    const safetyToggle = screen.getByTestId("safety-note-details") as HTMLDetailsElement;
    expect(safetyToggle.open).toBe(false);

    const traceToggle = screen.getByTestId("trace-details") as HTMLDetailsElement;
    expect(traceToggle.open).toBe(true);
  });
});
