import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "./App";

const SAMPLE_REPORT = {
  id: 1,
  name: "Elena Vance",
  station: "PROP-02",
  wind_knots: 28.0,
  temp_c: 12.0,
  fuel_pct: 99.1,
  note: "LOX bleed valve oscillated on ramp test.",
  verdict: "no_go",
  violations: ["wind_knots (28.0) exceeds maximum limit of 25.0 knots"],
  subsystem: "propulsion",
  severity: "high",
  brief_by_minutes: 5,
  hidden_instructions_flagged: false,
  missing_details_flagged: false,
  panic_tone_flagged: false,
  review_required: false,
  briefing_text: "NO-GO: PROP-02 wind limit exceeded (28.0 kt). Hold launch pending wind check.",
  draft_rounds: 1,
  approval_status: "pending",
  approved_by: null,
  approved_at: null,
  total_tokens: 185,
  total_cost_usd: 0.000725,
  created_at: "2026-11-17T13:00:00Z",
  steps: [
    {
      id: 1,
      report_id: 1,
      step_order: 1,
      step_name: "launch_limits",
      input_tokens: 0,
      output_tokens: 0,
      total_tokens: 0,
      cost_usd: 0.0,
      output_summary: "verdict=no_go, violations=1",
      detail: { verdict: "no_go" },
      created_at: "2026-11-17T13:00:00Z",
    },
    {
      id: 2,
      report_id: 1,
      step_order: 2,
      step_name: "sort_report",
      input_tokens: 120,
      output_tokens: 65,
      total_tokens: 185,
      cost_usd: 0.000725,
      output_summary: "subsystem=propulsion, severity=high, brief_by=5m",
      detail: { subsystem: "propulsion" },
      created_at: "2026-11-17T13:00:00Z",
    },
  ],
};

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Mission Control Console", () => {
  it("renders report briefing, verdict, cost, and one trace card per step with tokens", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify([SAMPLE_REPORT]), { status: 200 })
    );

    render(<App />);

    expect(await screen.findByText(/NO-GO: PROP-02 wind limit exceeded/i)).toBeInTheDocument();
    expect(screen.getAllByText(/NO-GO/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/5 min/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/\$0\.000725/).length).toBeGreaterThan(0);

    const stepCards = screen.getAllByTestId("trace-step-card");
    expect(stepCards).toHaveLength(2);
    expect(stepCards[0]).toHaveTextContent("launch_limits");
    expect(stepCards[0]).toHaveTextContent("0 tokens");
    expect(stepCards[1]).toHaveTextContent("sort_report");
    expect(stepCards[1]).toHaveTextContent("185 tokens");
  });

  it("submits all report fields and displays clear backend validation errors", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({
            detail: [{ loc: ["body", "fuel_pct"], msg: "fuel_pct must be between 0 and 100" }],
          }),
          { status: 422 }
        )
      )
      .mockResolvedValueOnce(new Response(JSON.stringify(SAMPLE_REPORT), { status: 201 }));

    render(<App />);
    await screen.findByText(/No reports filed yet/i);

    fireEvent.change(screen.getByLabelText(/Engineer Name/i), {
      target: { value: "Elena Vance" },
    });
    fireEvent.change(screen.getByLabelText(/Station/i), {
      target: { value: "PROP-02" },
    });
    fireEvent.change(screen.getByLabelText(/Wind \(knots\)/i), {
      target: { value: "28" },
    });
    fireEvent.change(screen.getByLabelText(/Temp \(C\)/i), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText(/Fuel \(%\)/i), {
      target: { value: "105" },
    });
    fireEvent.change(screen.getByLabelText(/Anomaly Note/i), {
      target: { value: "LOX bleed valve oscillated on ramp test." },
    });

    fireEvent.click(screen.getByRole("button", { name: /Submit Report/i }));

    expect(await screen.findByText(/fuel_pct must be between 0 and 100/i)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText(/Fuel \(%\)/i), {
      target: { value: "99.1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Submit Report/i }));

    await waitFor(() => {
      expect(fetchMock).toHaveBeenCalledTimes(3);
    });

    const thirdCallBody = JSON.parse(String(fetchMock.mock.calls[2][1]?.body));
    expect(thirdCallBody).toEqual({
      name: "Elena Vance",
      station: "PROP-02",
      wind_knots: 28,
      temp_c: 12,
      fuel_pct: 99.1,
      note: "LOX bleed valve oscillated on ramp test.",
    });
  });

  it("allows human Flight Director approval of a pending briefing", async () => {
    const approvedReport = {
      ...SAMPLE_REPORT,
      approval_status: "approved",
      approved_by: "Director Kim",
      approved_at: "2026-11-17T13:05:00Z",
    };

    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify([SAMPLE_REPORT]), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(approvedReport), { status: 200 }));

    render(<App />);
    await screen.findByText(/Pending Human Approval/i);

    fireEvent.change(screen.getByLabelText(/Flight Director Name/i), {
      target: { value: "Director Kim" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Approve Briefing/i }));

    await waitFor(() => {
      expect(screen.getByText(/Approved by Director Kim/i)).toBeInTheDocument();
    });

    const approveCallBody = JSON.parse(String(fetchMock.mock.calls[1][1]?.body));
    expect(approveCallBody).toEqual({
      approved_by: "Director Kim",
      actor_type: "human",
    });
  });
});
