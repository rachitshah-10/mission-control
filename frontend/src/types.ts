export interface PipelineStep {
  id: number;
  report_id: number;
  step_order: number;
  step_name: string;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  cost_usd: number;
  output_summary: string;
  detail: Record<string, unknown>;
  created_at: string;
}

export interface Report {
  id: number;
  name: string;
  station: string;
  wind_knots: number;
  temp_c: number;
  fuel_pct: number;
  note: string;
  verdict: "go" | "no_go";
  violations: string[];
  subsystem: string;
  severity: "high" | "medium" | "low";
  brief_by_minutes: 5 | 15 | 30;
  hidden_instructions_flagged: boolean;
  missing_details_flagged: boolean;
  panic_tone_flagged: boolean;
  review_required: boolean;
  briefing_text: string;
  draft_rounds: number;
  approval_status: "pending" | "approved";
  approved_by: string | null;
  approved_at: string | null;
  total_tokens: number;
  total_cost_usd: number;
  created_at: string;
  steps: PipelineStep[];
}

export interface ReportFormValues {
  name: string;
  station: string;
  wind_knots: string;
  temp_c: string;
  fuel_pct: string;
  note: string;
}
