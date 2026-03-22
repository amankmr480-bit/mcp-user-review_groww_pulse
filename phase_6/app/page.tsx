"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

type Note = {
  week_id: string;
  content: string;
  word_count: number;
};

type Draft = {
  week_id: string;
  subject: string;
  body: string;
  recipient: string | null;
};

type WeekFromDate = {
  week_id: string;
  week_beginning: string;
  date: string;
};

const API_BASE = process.env.NEXT_PUBLIC_BACKEND_API_URL || "http://localhost:8000";

function todayYmd(): string {
  const d = new Date();
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

async function getJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as T;
}

export default function Page() {
  const [weeks, setWeeks] = useState<string[]>([]);
  const [weekStartDate, setWeekStartDate] = useState(todayYmd);
  const [resolved, setResolved] = useState<WeekFromDate | null>(null);
  const [week, setWeek] = useState<string>("");
  const [note, setNote] = useState<Note | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [batchSize, setBatchSize] = useState(15);
  const [runIngest, setRunIngest] = useState(false);

  const canLoad = useMemo(() => !!week, [week]);

  const resolveDate = useCallback(async (ymd: string) => {
    setMsg("");
    try {
      const q = new URLSearchParams({ date: ymd });
      const info = await getJson<WeekFromDate>(`/week/from-date?${q}`);
      setResolved(info);
      setWeek(info.week_id);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Invalid or unknown date: ${m}`);
      setResolved(null);
    }
  }, []);

  async function refreshWeeks() {
    try {
      const data = await getJson<{ weeks: string[] }>("/weeks");
      setWeeks(data.weeks || []);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Failed to load weeks: ${m}`);
    }
  }

  async function loadWeekFor(wid: string) {
    if (!wid) return;
    setBusy(true);
    setMsg("");
    try {
      const [n, d] = await Promise.all([
        getJson<Note>(`/weeks/${encodeURIComponent(wid)}/note`),
        getJson<Draft>(`/weeks/${encodeURIComponent(wid)}/email-draft`)
      ]);
      setNote(n);
      setDraft(d);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Failed to load week data: ${m}`);
      setNote(null);
      setDraft(null);
    } finally {
      setBusy(false);
    }
  }

  async function loadWeek() {
    await loadWeekFor(week);
  }

  async function runPipeline() {
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/pipeline/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          week_start_date: weekStartDate,
          run_ingest: runIngest,
          batch_size: Number(batchSize)
        })
      });
      if (!res.ok) throw new Error(await res.text());
      const body = (await res.json()) as { resolved_week_id?: string | null };
      await refreshWeeks();
      await resolveDate(weekStartDate);
      const wid = body.resolved_week_id;
      if (wid) {
        setWeek(wid);
        await loadWeekFor(wid);
      }
      setMsg("Pipeline run completed.");
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Pipeline failed: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function sendDraft() {
    if (!week) return;
    setBusy(true);
    setMsg("");
    try {
      const res = await fetch(`${API_BASE}/weeks/${encodeURIComponent(week)}/send`, {
        method: "POST"
      });
      if (!res.ok) throw new Error(await res.text());
      setMsg("Email sent successfully.");
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Send failed: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  async function onPickGeneratedWeek(w: string) {
    if (!w) return;
    setBusy(true);
    setMsg("");
    try {
      const q = new URLSearchParams({ week_id: w });
      const info = await getJson<WeekFromDate>(`/week/from-id?${q}`);
      setWeekStartDate(info.week_beginning);
      setResolved(info);
      setWeek(info.week_id);
    } catch (e: unknown) {
      const m = e instanceof Error ? e.message : String(e);
      setMsg(`Could not resolve week: ${m}`);
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    refreshWeeks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    resolveDate(weekStartDate);
  }, [weekStartDate, resolveDate]);

  useEffect(() => {
    if (week) loadWeek();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [week]);

  return (
    <main>
      <h1>GROWW Review AI Frontend (Phase 6)</h1>
      <p>
        Connected backend: <code>{API_BASE}</code>
      </p>

      <div className="card" style={{ marginBottom: 16 }}>
        <h3>Pipeline Controls</h3>
        <div className="row">
          <div className="col">
            <label htmlFor="week-start">Week — any day in that week (YYYY-MM-DD)</label>
            <input
              id="week-start"
              type="date"
              value={weekStartDate}
              onChange={(e) => setWeekStartDate(e.target.value)}
            />
            {resolved ? (
              <p className="hint">
                ISO week <strong>{resolved.week_id}</strong> — Monday{" "}
                <strong>{resolved.week_beginning}</strong>
              </p>
            ) : null}
          </div>
          <div className="col">
            <label htmlFor="gen-week">Or choose a generated week</label>
            <select
              id="gen-week"
              value={weeks.includes(week) ? week : ""}
              onChange={(e) => {
                const w = e.target.value;
                if (w) void onPickGeneratedWeek(w);
              }}
            >
              <option value="">—</option>
              {weeks.map((w) => (
                <option key={w} value={w}>
                  {w}
                </option>
              ))}
            </select>
          </div>
          <div className="col">
            <label htmlFor="batch">Phase 2 batch size</label>
            <input
              id="batch"
              type="number"
              value={batchSize}
              min={1}
              onChange={(e) => setBatchSize(Number(e.target.value))}
            />
          </div>
          <div className="col" style={{ display: "flex", alignItems: "end", gap: 8 }}>
            <label>
              <input
                type="checkbox"
                checked={runIngest}
                onChange={(e) => setRunIngest(e.target.checked)}
              />{" "}
              Run Phase 1 ingest
            </label>
          </div>
        </div>
        <div style={{ marginTop: 12, display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button type="button" onClick={runPipeline} disabled={busy}>
            Run Pipeline
          </button>
          <button type="button" className="secondary" onClick={refreshWeeks} disabled={busy}>
            Refresh Weeks
          </button>
          <button type="button" className="secondary" onClick={loadWeek} disabled={busy || !canLoad}>
            Reload Note &amp; Draft
          </button>
          <button type="button" onClick={sendDraft} disabled={busy || !canLoad}>
            Send To Alias
          </button>
        </div>
        {msg ? <p style={{ marginTop: 12 }}>{msg}</p> : null}
      </div>

      <div className="row">
        <div className="col card">
          <h3>Weekly Note</h3>
          {note ? (
            <>
              <p>Word count: {note.word_count}</p>
              <pre>{note.content}</pre>
            </>
          ) : (
            <p>No note loaded.</p>
          )}
        </div>
        <div className="col card">
          <h3>Email Draft</h3>
          {draft ? (
            <>
              <p>
                <b>Subject:</b> {draft.subject}
              </p>
              <p>
                <b>Recipient:</b> {draft.recipient || "N/A"}
              </p>
              <pre>{draft.body}</pre>
            </>
          ) : (
            <p>No draft loaded.</p>
          )}
        </div>
      </div>
    </main>
  );
}
