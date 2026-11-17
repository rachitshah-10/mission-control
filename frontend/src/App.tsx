import { FormEvent, useEffect, useState } from "react";
import type { Report, ReportFormValues } from "./types";

const EMPTY_FORM: ReportFormValues = {
  name: "",
  station: "",
  wind_knots: "",
  temp_c: "",
  fuel_pct: "",
  note: "",
};

function formatApiError(payload: unknown, fallback: string): string {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }
  const detail = (payload as { detail?: unknown }).detail;
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const messages = detail.map((item) => {
      if (item && typeof item === "object") {
        const record = item as { loc?: unknown[]; msg?: string };
        const field = Array.isArray(record.loc) ? record.loc[record.loc.length - 1] : null;
        return field ? `${String(field)}: ${record.msg ?? "invalid"}` : String(record.msg ?? "invalid");
      }
      return String(item);
    });
    return messages.join(" | ");
  }
  return fallback;
}

function formatCost(cost: number): string {
  return `$${cost.toFixed(6)}`;
}

export default function App() {
  const [reports, setReports] = useState<Report[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [form, setForm] = useState<ReportFormValues>(EMPTY_FORM);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const [approverName, setApproverName] = useState("");
  const [approvalError, setApprovalError] = useState<string | null>(null);
  const [approving, setApproving] = useState(false);

  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    async function loadReports() {
      try {
        const res = await fetch("/api/reports");
        if (!res.ok) {
          throw new Error(`Failed to load reports (${res.status})`);
        }
        const data: Report[] = await res.json();
        if (!active) return;
        setReports(data);
        if (data.length > 0) {
          setSelectedId((prev) => prev ?? data[0].id);
        }
      } catch (err) {
        if (!active) return;
        setLoadError(err instanceof Error ? err.message : "Failed to load reports");
      }
    }
    loadReports();
    return () => {
      active = false;
    };
  }, []);

  const selectedReport = reports.find((r) => r.id === selectedId) ?? reports[0] ?? null;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    const wind = Number(form.wind_knots);
    const temp = Number(form.temp_c);
    const fuel = Number(form.fuel_pct);

    if (
      form.wind_knots.trim() === "" ||
      form.temp_c.trim() === "" ||
      form.fuel_pct.trim() === "" ||
      Number.isNaN(wind) ||
      Number.isNaN(temp) ||
      Number.isNaN(fuel)
    ) {
      setFormError("Wind, temperature, and fuel readings must be valid numbers.");
      return;
    }

    setSubmitting(true);
    try {
      const res = await fetch("/api/reports", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name,
          station: form.station,
          wind_knots: wind,
          temp_c: temp,
          fuel_pct: fuel,
          note: form.note,
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        setFormError(formatApiError(body, "Report submission failed."));
        return;
      }
      const created = body as Report;
      setReports((prev) => [created, ...prev]);
      setSelectedId(created.id);
      setForm(EMPTY_FORM);
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Network error submitting report.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleApprove(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selectedReport) return;
    setApprovalError(null);

    if (!approverName.trim()) {
      setApprovalError("Enter Flight Director name before approving.");
      return;
    }

    setApproving(true);
    try {
      const res = await fetch(`/api/reports/${selectedReport.id}/approve`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved_by: approverName.trim(),
          actor_type: "human",
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        setApprovalError(formatApiError(body, "Approval failed."));
        return;
      }
      const updated = body as Report;
      setReports((prev) => prev.map((r) => (r.id === updated.id ? updated : r)));
      setApproverName("");
    } catch (err) {
      setApprovalError(err instanceof Error ? err.message : "Approval request failed.");
    } finally {
      setApproving(false);
    }
  }

  const noGoCount = reports.filter((r) => r.verdict === "no_go").length;
  const pendingCount = reports.filter((r) => r.approval_status === "pending").length;

  return (
    <div className="console-shell">
      <header className="topbar">
        <div>
          <h1>Mission Control — Go/No-Go Launch Console</h1>
          <div className="topbar-sub">Meridian Launch Services · T-90m Flight Director Desk</div>
        </div>
        <div className="metrics-bar">
          <div className="metric-pill">Reports: {reports.length}</div>
          <div className="metric-pill">NO-GO: {noGoCount}</div>
          <div className="metric-pill">Pending Approval: {pendingCount}</div>
        </div>
      </header>

      <div className="main-grid">
        <section className="card">
          <h2>File Anomaly Report</h2>
          <form className="form-grid" onSubmit={handleSubmit} noValidate>
            <div className="field">
              <label htmlFor="engineer-name">Engineer Name</label>
              <input
                id="engineer-name"
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                placeholder="Elena Vance"
              />
            </div>
            <div className="field">
              <label htmlFor="station">Station</label>
              <input
                id="station"
                value={form.station}
                onChange={(e) => setForm({ ...form, station: e.target.value })}
                placeholder="PROP-02"
              />
            </div>

            <div className="telemetry-inputs">
              <div className="field">
                <label htmlFor="wind-knots">Wind (knots)</label>
                <input
                  id="wind-knots"
                  type="number"
                  step="0.1"
                  value={form.wind_knots}
                  onChange={(e) => setForm({ ...form, wind_knots: e.target.value })}
                  placeholder="<= 25"
                />
              </div>
              <div className="field">
                <label htmlFor="temp-c">Temp (C)</label>
                <input
                  id="temp-c"
                  type="number"
                  step="0.1"
                  value={form.temp_c}
                  onChange={(e) => setForm({ ...form, temp_c: e.target.value })}
                  placeholder=">= 4"
                />
              </div>
              <div className="field">
                <label htmlFor="fuel-pct">Fuel (%)</label>
                <input
                  id="fuel-pct"
                  type="number"
                  step="0.1"
                  value={form.fuel_pct}
                  onChange={(e) => setForm({ ...form, fuel_pct: e.target.value })}
                  placeholder="98-100"
                />
              </div>
            </div>

            <div className="field">
              <label htmlFor="anomaly-note">Anomaly Note</label>
              <textarea
                id="anomaly-note"
                rows={4}
                value={form.note}
                onChange={(e) => setForm({ ...form, note: e.target.value })}
                placeholder="Describe valve, telemetry, or sensor behavior..."
              />
            </div>

            {formError && (
              <div className="alert-error" role="alert">
                {formError}
              </div>
            )}

            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? "Running Triage Pipeline..." : "Submit Report"}
            </button>
          </form>
        </section>

        <section className="card">
          <h2>Flight Director Console</h2>
          {loadError && <div className="alert-error">{loadError}</div>}

          {reports.length === 0 ? (
            <p className="muted">No reports filed yet. Submit a console report to begin triage.</p>
          ) : (
            <div className="console-split">
              <div className="report-list">
                {reports.map((report) => (
                  <button
                    key={report.id}
                    type="button"
                    className={`report-item ${
                      selectedReport?.id === report.id ? "active" : ""
                    }`}
                    onClick={() => setSelectedId(report.id)}
                  >
                    <div className="row-between">
                      <strong>{report.station}</strong>
                      <span
                        className={`badge ${
                          report.verdict === "go" ? "badge-go" : "badge-nogo"
                        }`}
                      >
                        {report.verdict === "go" ? "GO" : "NO-GO"}
                      </span>
                    </div>
                    <div className="muted" style={{ marginTop: 4 }}>
                      {report.name} · {report.subsystem} · {report.brief_by_minutes} min
                    </div>
                    <div className="row-between muted" style={{ marginTop: 6 }}>
                      <span>{report.approval_status === "approved" ? "Approved" : "Pending"}</span>
                      <span className="mono">{formatCost(report.total_cost_usd)}</span>
                    </div>
                  </button>
                ))}
              </div>

              {selectedReport && (
                <div>
                  <div className="row-between">
                    <div>
                      <h3 style={{ margin: 0 }}>
                        #{selectedReport.id} · {selectedReport.station} ({selectedReport.name})
                      </h3>
                      <div className="muted">Filed: {selectedReport.created_at}</div>
                    </div>
                    <span
                      className={`badge ${
                        selectedReport.verdict === "go" ? "badge-go" : "badge-nogo"
                      }`}
                    >
                      {selectedReport.verdict === "go" ? "GO" : "NO-GO"}
                    </span>
                  </div>

                  <div className="kv-grid">
                    <div className="kv-box">
                      <div className="kv-label">Subsystem / Severity</div>
                      <div className="kv-value">
                        {selectedReport.subsystem} / {selectedReport.severity}
                      </div>
                    </div>
                    <div className="kv-box">
                      <div className="kv-label">Brief By</div>
                      <div className="kv-value">{selectedReport.brief_by_minutes} min</div>
                    </div>
                    <div className="kv-box">
                      <div className="kv-label">Readings</div>
                      <div className="kv-value mono">
                        {selectedReport.wind_knots}kt · {selectedReport.temp_c}C ·{" "}
                        {selectedReport.fuel_pct}%
                      </div>
                    </div>
                    <div className="kv-box">
                      <div className="kv-label">Total Cost</div>
                      <div className="kv-value mono">
                        {formatCost(selectedReport.total_cost_usd)} ({selectedReport.total_tokens}{" "}
                        tok)
                      </div>
                    </div>
                  </div>

                  {selectedReport.violations.length > 0 && (
                    <div className="section-block">
                      <div className="alert-error">
                        <strong>Launch Limit Violations:</strong>
                        <ul style={{ margin: "6px 0 0 18px", padding: 0 }}>
                          {selectedReport.violations.map((v) => (
                            <li key={v}>{v}</li>
                          ))}
                        </ul>
                      </div>
                    </div>
                  )}

                  <div className="section-block" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                    <span
                      className={`badge ${
                        selectedReport.hidden_instructions_flagged ? "badge-nogo" : "badge-neutral"
                      }`}
                    >
                      Hidden Instructions:{" "}
                      {selectedReport.hidden_instructions_flagged ? "Flagged" : "Clear"}
                    </span>
                    <span
                      className={`badge ${
                        selectedReport.missing_details_flagged ? "badge-warn" : "badge-neutral"
                      }`}
                    >
                      Missing Details:{" "}
                      {selectedReport.missing_details_flagged ? "Flagged" : "Clear"}
                    </span>
                    <span
                      className={`badge ${
                        selectedReport.panic_tone_flagged ? "badge-warn" : "badge-neutral"
                      }`}
                    >
                      Panic Tone: {selectedReport.panic_tone_flagged ? "Flagged" : "Clear"}
                    </span>
                    {selectedReport.review_required && (
                      <span className="badge badge-nogo">Review Required</span>
                    )}
                  </div>

                  <div className="section-block">
                    <div className="row-between" style={{ marginBottom: 6 }}>
                      <strong>Drafted Briefing</strong>
                      <span className="muted">
                        Rounds: {selectedReport.draft_rounds} / 3
                      </span>
                    </div>
                    <div className="briefing-box">{selectedReport.briefing_text}</div>
                  </div>

                  <div className="section-block">
                    <strong>Human Flight Director Approval</strong>
                    {selectedReport.approval_status === "approved" ? (
                      <p style={{ marginTop: 8, color: "var(--go)", fontWeight: 600 }}>
                        Approved by {selectedReport.approved_by} at {selectedReport.approved_at}
                      </p>
                    ) : (
                      <div style={{ marginTop: 8 }}>
                        <div className="muted" style={{ marginBottom: 8 }}>
                          Pending Human Approval
                        </div>
                        <form className="approval-row" onSubmit={handleApprove}>
                          <div className="field" style={{ flex: "1 1 200px" }}>
                            <label htmlFor="flight-director-name">Flight Director Name</label>
                            <input
                              id="flight-director-name"
                              value={approverName}
                              onChange={(e) => setApproverName(e.target.value)}
                              placeholder="Director Kim"
                            />
                          </div>
                          <button
                            className="btn btn-approve"
                            type="submit"
                            disabled={approving}
                          >
                            {approving ? "Approving..." : "Approve Briefing"}
                          </button>
                        </form>
                        {approvalError && (
                          <div className="alert-error" style={{ marginTop: 8 }}>
                            {approvalError}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="section-block">
                    <strong>Pipeline Step Trace ({selectedReport.steps.length} steps)</strong>
                    <div className="trace-grid">
                      {selectedReport.steps.map((step) => (
                        <div
                          key={step.id}
                          className="trace-card"
                          data-testid="trace-step-card"
                        >
                          <div className="row-between">
                            <strong className="mono">
                              #{step.step_order} {step.step_name}
                            </strong>
                            <span className="mono muted">{formatCost(step.cost_usd)}</span>
                          </div>
                          <div className="muted">{step.output_summary}</div>
                          <div className="trace-meta mono">
                            <span>{step.total_tokens} tokens</span>
                            <span>
                              {step.input_tokens} in / {step.output_tokens} out
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
