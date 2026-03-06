export type ReviewStatus = "pending" | "approved" | "rejected" | "needs_review";

export type EvidenceLink = {
  url: string;
  label: string;
  source_type: string;
  snippet?: string | null;
};

export type RecordRow = {
  company_id: number;
  event_or_association: string | null;
  company: string;
  qualification_score: number | null;
  score_tier: string | null;
  score_confidence: number | null;
  score_factors: Record<string, unknown> | null;
  rationale: string[];
  disqualifiers: string[];
  stakeholder: string | null;
  stakeholder_title: string | null;
  stakeholder_rationale: string | null;
  stakeholder_confidence: number | null;
  evidence_links: EvidenceLink[];
  outreach_preview: string | null;
  outreach_email_opener: string | null;
  outreach_linkedin_note: string | null;
  outreach_three_sentence: string | null;
  status: ReviewStatus;
};

export type JobRun = {
  id: number;
  job_name: string;
  status: string;
  started_at: string;
  completed_at: string | null;
  details: Record<string, unknown> | null;
};

export type JobCreateResponse = {
  job_run_id: number;
  task_id: string | null;
  status: string;
  started_at: string;
  details: Record<string, unknown> | null;
};

export const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:8000/api";

export async function fetchRecords(): Promise<RecordRow[]> {
  const res = await fetch(`${API_BASE}/records`);
  if (!res.ok) throw new Error("Failed to load records");
  return res.json();
}

export async function runPipeline(): Promise<JobCreateResponse> {
  const payload = {
    account_name: "DuPont Tedlar",
    target_segment: "Graphics & Signage",
    icp_themes: [
      "protective films",
      "signage",
      "graphics",
      "vehicle wraps",
      "architectural graphics",
      "wallcoverings",
      "durable surfaces",
      "anti-graffiti",
      "UV/weather resistance"
    ]
  };

  const res = await fetch(`${API_BASE}/pipeline/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload)
  });
  if (!res.ok) throw new Error("Pipeline dispatch failed");
  return res.json();
}

export async function fetchJobs(): Promise<JobRun[]> {
  const res = await fetch(`${API_BASE}/pipeline/jobs`);
  if (!res.ok) throw new Error("Failed to load jobs");
  return res.json();
}

export async function fetchJob(jobRunId: number): Promise<JobRun> {
  const res = await fetch(`${API_BASE}/pipeline/jobs/${jobRunId}`);
  if (!res.ok) throw new Error("Failed to load job detail");
  return res.json();
}

export async function updateReviewStatus(
  companyId: number,
  status: ReviewStatus,
  notes?: string
): Promise<void> {
  const res = await fetch(`${API_BASE}/review/company/${companyId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ status, notes: notes || null })
  });
  if (!res.ok) throw new Error("Failed to update review status");
}
