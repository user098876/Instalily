import { useEffect, useMemo, useState } from "react";
import {
  fetchJobs,
  fetchRecords,
  runPipeline,
  updateReviewStatus,
  API_BASE,
  type JobCreateResponse,
  type JobRun,
  type RecordRow,
  type ReviewStatus
} from "./api/client";

const STATUS_OPTIONS: ReviewStatus[] = ["pending", "approved", "needs_review", "rejected"];

function formatDateTime(value: string | null): string {
  if (!value) return "-";
  try {
    return new Date(value).toLocaleString();
  } catch {
    return value;
  }
}

function getTierClass(tier: string | null): string {
  if (tier === "A") return "tier tier-a";
  if (tier === "B") return "tier tier-b";
  if (tier === "C") return "tier tier-c";
  return "tier";
}

function statusClass(status: string): string {
  return `status-chip status-${status}`;
}

function outreachStatusLabel(status: RecordRow["outreach_status"]): string {
  if (status === "ready") return "Ready";
  if (status === "low_confidence") return "Low Confidence";
  return "Omitted";
}

export function App() {
  const [records, setRecords] = useState<RecordRow[]>([]);
  const [jobs, setJobs] = useState<JobRun[]>([]);
  const [selectedRecord, setSelectedRecord] = useState<RecordRow | null>(null);

  const [loadingRecords, setLoadingRecords] = useState(false);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [runningPipeline, setRunningPipeline] = useState(false);

  const [recordsError, setRecordsError] = useState<string | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [runResponse, setRunResponse] = useState<JobCreateResponse | null>(null);

  const [query, setQuery] = useState("");
  const [tierFilter, setTierFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [minScore, setMinScore] = useState(0);
  const [sortBy, setSortBy] = useState<"score" | "company" | "status">("score");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("desc");
  const [reviewNotes, setReviewNotes] = useState("");

  async function loadRecords() {
    setLoadingRecords(true);
    setRecordsError(null);
    try {
      const rows = await fetchRecords();
      setRecords(rows);
      if (selectedRecord) {
        const refreshed = rows.find((r) => r.company_id === selectedRecord.company_id) || null;
        setSelectedRecord(refreshed);
      }
    } catch (error) {
      setRecordsError(error instanceof Error ? error.message : "Failed to load records");
    } finally {
      setLoadingRecords(false);
    }
  }

  async function loadJobs() {
    setLoadingJobs(true);
    setJobsError(null);
    try {
      setJobs(await fetchJobs());
    } catch (error) {
      setJobsError(error instanceof Error ? error.message : "Failed to load jobs");
    } finally {
      setLoadingJobs(false);
    }
  }

  useEffect(() => {
    void loadRecords();
    void loadJobs();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadJobs();
    }, 8000);
    return () => window.clearInterval(timer);
  }, []);

  const filteredRecords = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = records.filter((r) => {
      const searchHit =
        !q ||
        r.company.toLowerCase().includes(q) ||
        (r.event_or_association || "").toLowerCase().includes(q) ||
        (r.stakeholder || "").toLowerCase().includes(q);
      const tierHit = tierFilter === "all" || (r.score_tier || "").toLowerCase() === tierFilter;
      const statusHit = statusFilter === "all" || r.status === statusFilter;
      const scoreHit = (r.qualification_score || 0) >= minScore;
      return searchHit && tierHit && statusHit && scoreHit;
    });

    return list.sort((a, b) => {
      let cmp = 0;
      if (sortBy === "score") {
        cmp = (a.qualification_score || 0) - (b.qualification_score || 0);
      } else if (sortBy === "company") {
        cmp = a.company.localeCompare(b.company);
      } else {
        cmp = a.status.localeCompare(b.status);
      }
      return sortDir === "asc" ? cmp : -cmp;
    });
  }, [records, query, tierFilter, statusFilter, minScore, sortBy, sortDir]);

  const metrics = useMemo(() => {
    const total = records.length;
    const avgScore =
      total === 0
        ? 0
        : Math.round(
            (records.reduce((sum, r) => sum + (r.qualification_score || 0), 0) / Math.max(total, 1)) * 10
          ) / 10;
    const approved = records.filter((r) => r.status === "approved").length;
    const needsReview = records.filter((r) => r.status === "needs_review").length;
    const rejected = records.filter((r) => r.status === "rejected").length;
    const highPriority = records.filter((r) => (r.qualification_score || 0) >= 75).length;
    return { total, avgScore, approved, needsReview, rejected, highPriority };
  }, [records]);

  async function handleRunPipeline() {
    setRunningPipeline(true);
    setActionError(null);
    try {
      const response = await runPipeline();
      setRunResponse(response);
      await loadJobs();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to start pipeline");
    } finally {
      setRunningPipeline(false);
    }
  }

  async function handleSetStatus(status: ReviewStatus) {
    if (!selectedRecord) return;
    setActionError(null);
    try {
      await updateReviewStatus(selectedRecord.company_id, status, reviewNotes);
      await loadRecords();
      await loadJobs();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : "Failed to update review status");
    }
  }

  const activeJob = jobs[0];
  const activeJobSteps = ((activeJob?.details as { steps?: Record<string, { status?: string; metrics?: Record<string, unknown> }> } | null)?.steps) || {};

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>DuPont Tedlar Lead Review Dashboard</h1>
          <p>Evidence-first qualification and outreach review for Graphics & Signage.</p>
        </div>
        <div className="actions">
          <button className="primary" onClick={handleRunPipeline} disabled={runningPipeline}>
            {runningPipeline ? "Queueing..." : "Run Pipeline"}
          </button>
          <button className="secondary" onClick={() => { void loadRecords(); void loadJobs(); }}>
            Refresh
          </button>
        </div>
      </header>

      <section className="metrics-grid">
        <article className="metric-card"><h3>Total Leads</h3><strong>{metrics.total}</strong></article>
        <article className="metric-card"><h3>Avg Score</h3><strong>{metrics.avgScore}</strong></article>
        <article className="metric-card"><h3>High Priority (75+)</h3><strong>{metrics.highPriority}</strong></article>
        <article className="metric-card"><h3>Approved</h3><strong>{metrics.approved}</strong></article>
        <article className="metric-card"><h3>Needs Review</h3><strong>{metrics.needsReview}</strong></article>
        <article className="metric-card"><h3>Rejected</h3><strong>{metrics.rejected}</strong></article>
      </section>

      <section className="jobs-panel">
        <div>
          <h2>Recent Jobs</h2>
          {runResponse ? <p className="muted">Last queued job: #{runResponse.job_run_id}</p> : null}
        </div>
        {jobsError ? <p className="error">{jobsError}</p> : null}
        {loadingJobs ? <p className="muted">Loading jobs...</p> : null}
        {activeJob ? (
          <div className="job-highlight">
            <span className={statusClass(activeJob.status)}>{activeJob.status}</span>
            <span>Job #{activeJob.id}</span>
            <span>Started: {formatDateTime(activeJob.started_at)}</span>
            <span>Completed: {formatDateTime(activeJob.completed_at)}</span>
          </div>
        ) : (
          <p className="muted">No pipeline runs yet.</p>
        )}
        {activeJob && Object.keys(activeJobSteps).length > 0 ? (
          <div className="step-list">
            {Object.entries(activeJobSteps).map(([name, step]) => (
              <div key={name} className="step-row">
                <span>{name}</span>
                <span className={statusClass(step.status || "pending")}>{step.status || "pending"}</span>
                <span className="muted">{Object.entries(step.metrics || {}).map(([k, v]) => `${k}: ${String(v)}`).join(" | ") || "no metrics"}</span>
              </div>
            ))}
          </div>
        ) : null}
        {jobs.length > 1 ? (
          <div className="job-list">
            {jobs.slice(0, 5).map((job) => (
              <div key={job.id} className="job-row">
                <span>#{job.id}</span>
                <span className={statusClass(job.status)}>{job.status}</span>
                <span>{formatDateTime(job.started_at)}</span>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="filters-panel">
        <input
          placeholder="Search company, stakeholder, event"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <select value={tierFilter} onChange={(e) => setTierFilter(e.target.value)}>
          <option value="all">All Tiers</option>
          <option value="a">Tier A</option>
          <option value="b">Tier B</option>
          <option value="c">Tier C</option>
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="all">All Statuses</option>
          {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <div className="range-group">
          <label>Min Score: {minScore}</label>
          <input type="range" min={0} max={100} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} />
        </div>
        <select value={sortBy} onChange={(e) => setSortBy(e.target.value as "score" | "company" | "status") }>
          <option value="score">Sort: Score</option>
          <option value="company">Sort: Company</option>
          <option value="status">Sort: Status</option>
        </select>
        <select value={sortDir} onChange={(e) => setSortDir(e.target.value as "asc" | "desc") }>
          <option value="desc">Desc</option>
          <option value="asc">Asc</option>
        </select>
      </section>

      {actionError ? <p className="error">{actionError}</p> : null}
      {recordsError ? <p className="error">{recordsError}</p> : null}
      {loadingRecords ? <p className="muted">Loading lead records...</p> : null}
      {!loadingRecords && filteredRecords.length === 0 ? (
        <div className="empty-state">
          <h3>No leads match current filters</h3>
          <p>Adjust filters or run a new pipeline job.</p>
        </div>
      ) : null}

      <section className="content-grid">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Event/Association</th>
                <th>Company</th>
                <th>Score</th>
                <th>Stakeholder</th>
                <th>Qualification</th>
                <th>Evidence</th>
                <th>Outreach</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredRecords.map((row) => (
                <tr
                  key={row.company_id}
                  className={selectedRecord?.company_id === row.company_id ? "selected" : ""}
                  onClick={() => {
                    setSelectedRecord(row);
                    setReviewNotes("");
                  }}
                >
                  <td>{row.event_or_association || "-"}</td>
                  <td>
                    <div className="company-cell">
                      <strong>{row.company}</strong>
                      <span className={getTierClass(row.score_tier)}>{row.score_tier || "-"}</span>
                    </div>
                  </td>
                  <td>{row.qualification_score ?? "-"}</td>
                  <td>
                    <div>{row.stakeholder || "-"}</div>
                    <small>{row.stakeholder_title || ""}</small>
                  </td>
                  <td>{(row.qualification_rationale || row.rationale[0] || "No rationale").slice(0, 110)}</td>
                  <td>
                    {row.evidence_links.slice(0, 2).map((e) => (
                      <div key={e.url + e.label}><a href={e.url} target="_blank" rel="noreferrer">{e.label}</a></div>
                    ))}
                  </td>
                  <td><span className={statusClass(row.outreach_status)}>{outreachStatusLabel(row.outreach_status)}</span></td>
                  <td><span className={statusClass(row.status)}>{row.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <aside className="detail-drawer">
          {selectedRecord ? (
            <>
              <h2>{selectedRecord.company}</h2>
              <p className="muted">{selectedRecord.event_or_association || "No source ecosystem label"}</p>
              <p className="muted">
                Website:{" "}
                {selectedRecord.company_website ? (
                  <a href={selectedRecord.company_website} target="_blank" rel="noreferrer">{selectedRecord.company_website}</a>
                ) : (
                  "not validated"
                )}
              </p>

              <section className="drawer-section">
                <h3>Qualification</h3>
                <p>Score: <strong>{selectedRecord.qualification_score ?? "-"}</strong> ({selectedRecord.score_tier || "-"})</p>
                <p>Confidence: {selectedRecord.score_confidence != null ? selectedRecord.score_confidence.toFixed(2) : "-"}</p>
                <ul>
                  {selectedRecord.rationale.map((item, idx) => <li key={idx}>{item}</li>)}
                </ul>
                {selectedRecord.score_factors ? (
                  <>
                    <h4>Factor Breakdown</h4>
                    <div className="factor-grid">
                      {Object.entries(selectedRecord.score_factors).map(([key, value]) => {
                        const typed = value as { score?: number; max?: number };
                        return (
                          <div key={key} className="factor-item">
                            <span>{key}</span>
                            <strong>{typed.score ?? "-"} / {typed.max ?? "-"}</strong>
                          </div>
                        );
                      })}
                    </div>
                  </>
                ) : null}
                {selectedRecord.disqualifiers.length > 0 ? (
                  <>
                    <h4>Caveats / Disqualifiers</h4>
                    <ul>{selectedRecord.disqualifiers.map((d, i) => <li key={i}>{d}</li>)}</ul>
                  </>
                ) : null}
              </section>

              <section className="drawer-section">
                <h3>Stakeholder</h3>
                <p><strong>{selectedRecord.stakeholder || "Not found"}</strong></p>
                <p>{selectedRecord.stakeholder_title || ""}</p>
                {selectedRecord.stakeholder_profile_url ? (
                  <p><a href={selectedRecord.stakeholder_profile_url} target="_blank" rel="noreferrer">Validated profile link</a></p>
                ) : null}
                <p className="muted">Confidence: {selectedRecord.stakeholder_confidence != null ? selectedRecord.stakeholder_confidence.toFixed(2) : "-"}</p>
                <p>{selectedRecord.stakeholder_rationale || "No stakeholder rationale available."}</p>
              </section>

              <section className="drawer-section">
                <h3>Evidence</h3>
                {selectedRecord.evidence_links.length === 0 ? <p className="muted">No evidence links available.</p> : null}
                {selectedRecord.evidence_links.map((e) => (
                  <article key={e.url + e.label} className="evidence-item">
                    <a href={e.url} target="_blank" rel="noreferrer">{e.label}</a>
                    <p className="muted">
                      {e.source_type}
                      {e.extraction_method ? ` | ${e.extraction_method}` : ""}
                    </p>
                    <p>{e.snippet || "No snippet"}</p>
                  </article>
                ))}
                {selectedRecord.evidence_caveats.length > 0 ? (
                  <>
                    <h4>Missingness / Caveats</h4>
                    <ul>{selectedRecord.evidence_caveats.map((item, idx) => <li key={idx}>{item}</li>)}</ul>
                  </>
                ) : null}
              </section>

              <section className="drawer-section">
                <h3>Outreach</h3>
                <p className="muted">Status: {outreachStatusLabel(selectedRecord.outreach_status)}</p>
                <p><strong>Email opener:</strong> {selectedRecord.outreach_email_opener || "-"}</p>
                <p><strong>LinkedIn note:</strong> {selectedRecord.outreach_linkedin_note || "-"}</p>
                <p><strong>3-sentence outreach:</strong> {selectedRecord.outreach_three_sentence || "-"}</p>
              </section>

              <section className="drawer-section">
                <h3>Review Actions</h3>
                <textarea
                  placeholder="Optional review notes"
                  value={reviewNotes}
                  onChange={(e) => setReviewNotes(e.target.value)}
                />
                <div className="review-actions">
                  <button className="approve" onClick={() => { void handleSetStatus("approved"); }}>Approve</button>
                  <button className="needs" onClick={() => { void handleSetStatus("needs_review"); }}>Needs Review</button>
                  <button className="reject" onClick={() => { void handleSetStatus("rejected"); }}>Reject</button>
                </div>
              </section>
            </>
          ) : (
            <div className="empty-drawer">
              <h3>Select a lead</h3>
              <p>Click a table row to inspect evidence, rationale, and outreach details.</p>
            </div>
          )}
        </aside>
      </section>

      <footer className="footer-links">
        <a href={`${API_BASE}/export.csv`} target="_blank" rel="noreferrer">Export CSV</a>
        <a href={`${API_BASE}/export.json`} target="_blank" rel="noreferrer">Export JSON</a>
      </footer>
    </div>
  );
}
