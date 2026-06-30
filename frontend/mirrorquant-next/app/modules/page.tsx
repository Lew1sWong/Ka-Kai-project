"use client";

/**
 * Finance Modules workbench — exercises the contract Article-4 modules that were
 * added to the backend: Investment-Hypothesis Management + IC materials (Module B),
 * Portfolio Risk-Assistance (Module C), and Research Hub / Knowledge Base (Module D).
 *
 * Self-contained route at /modules. Uses the same API base + cookie-session
 * convention as the main client (credentials: "include"). Every analytical/AI
 * response from the backend carries a `compliance` block, surfaced below.
 */

import { useState } from "react";

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000";

async function api(path: string, options: RequestInit = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(body?.detail || `${res.status} ${res.statusText}`);
  }
  return body;
}

function Json({ value }: { value: unknown }) {
  if (value === null || value === undefined) return null;
  return (
    <pre
      style={{
        background: "#0c0f17",
        border: "1px solid #1e2636",
        borderRadius: 8,
        padding: 12,
        overflowX: "auto",
        fontSize: 12,
        color: "#cdd6e4",
        whiteSpace: "pre-wrap",
        wordBreak: "break-word",
      }}
    >
      {JSON.stringify(value, null, 2)}
    </pre>
  );
}

function Compliance({ data }: { data: any }) {
  const c = data?.compliance;
  if (!c) return null;
  return (
    <div
      style={{
        marginTop: 8,
        padding: "8px 12px",
        borderLeft: "3px solid #b4791f",
        background: "#1a140a",
        borderRadius: 6,
        fontSize: 12,
        color: "#e9c884",
      }}
    >
      ⚠️ {c.disclaimer_en}
      {Array.isArray(c.flags) && c.flags.length > 0 && (
        <div style={{ marginTop: 6, color: "#ff9b9b" }}>
          Guardrail flags: {c.flags.join(", ")}
        </div>
      )}
      {Array.isArray(c.sources) && c.sources.length > 0 && (
        <div style={{ marginTop: 6, color: "#8fa3bf" }}>
          Sources: {c.sources.map((s: any) => `${s.kind}:${s.ref}`).join(", ")}
        </div>
      )}
    </div>
  );
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section
      style={{
        background: "#11151f",
        border: "1px solid #1e2636",
        borderRadius: 12,
        padding: 18,
        marginBottom: 18,
      }}
    >
      <h2 style={{ margin: "0 0 12px", fontSize: 16, color: "#e6edf6" }}>{title}</h2>
      {children}
    </section>
  );
}

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  marginBottom: 8,
  background: "#0c0f17",
  border: "1px solid #2a3343",
  borderRadius: 8,
  color: "#e6edf6",
  fontSize: 13,
};
const btnStyle: React.CSSProperties = {
  padding: "8px 14px",
  background: "#2563eb",
  color: "#fff",
  border: "none",
  borderRadius: 8,
  cursor: "pointer",
  fontSize: 13,
};

export default function ModulesPage() {
  // Knowledge base
  const [docTitle, setDocTitle] = useState("Sample research note");
  const [docText, setDocText] = useState(
    "NVIDIA's data-center revenue accelerated on AI demand. Key risk: export controls."
  );
  const [question, setQuestion] = useState("What is the key risk for NVIDIA?");
  const [kbOut, setKbOut] = useState<any>(null);

  // Hypotheses
  const [hypTicker, setHypTicker] = useState("NVDA");
  const [hypTitle, setHypTitle] = useState("AI capex super-cycle");
  const [hypThesis, setHypThesis] = useState(
    "Data-center AI spend sustains above-trend growth for 4+ quarters."
  );
  const [hypList, setHypList] = useState<any>(null);

  // Portfolio
  const [pfName, setPfName] = useState("Core book");
  const [pfId, setPfId] = useState<number | null>(null);
  const [pfRisk, setPfRisk] = useState<any>(null);

  // IC material
  const [icOut, setIcOut] = useState<any>(null);

  // KB semantic search
  const [kbQuery, setKbQuery] = useState("Federal Reserve interest rate decision");
  const [kbSearch, setKbSearch] = useState<any>(null);

  // Data diode (one-way transfer)
  const [dSource, setDSource] = useState("reuters.com");
  const [dTitle, setDTitle] = useState("Fed holds rates steady");
  const [dContent, setDContent] = useState(
    "The Federal Reserve held its policy rate steady amid cooling inflation."
  );
  const [dClass, setDClass] = useState("public");
  const [diodeOut, setDiodeOut] = useState<any>(null);
  const [diodeList, setDiodeList] = useState<any>(null);

  const [err, setErr] = useState<string>("");
  const guard = (fn: () => Promise<void>) => async () => {
    setErr("");
    try {
      await fn();
    } catch (e: any) {
      setErr(e.message || String(e));
    }
  };

  return (
    <main
      style={{
        maxWidth: 880,
        margin: "0 auto",
        padding: 24,
        fontFamily: "ui-sans-serif, system-ui, sans-serif",
        color: "#e6edf6",
        background: "#0a0d14",
        minHeight: "100vh",
      }}
    >
      <h1 style={{ fontSize: 22, marginBottom: 4 }}>MirrorQuant — Finance Modules</h1>
      <p style={{ color: "#8fa3bf", marginTop: 0, fontSize: 13 }}>
        Research Hub / Knowledge Base · Investment Hypotheses · Portfolio Risk · IC Materials.
        Requires a logged-in session (sign in on the main app first).
      </p>
      {err && (
        <div style={{ color: "#ff9b9b", marginBottom: 12, fontSize: 13 }}>Error: {err}</div>
      )}

      <Section title="Research Hub / Knowledge Base (Module D)">
        <input style={inputStyle} value={docTitle} onChange={(e) => setDocTitle(e.target.value)} placeholder="Document title" />
        <textarea style={{ ...inputStyle, minHeight: 70 }} value={docText} onChange={(e) => setDocText(e.target.value)} placeholder="Paste document text" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const r = await api("/api/kb/documents", {
              method: "POST",
              body: JSON.stringify({ title: docTitle, text: docText, kind: "text" }),
            });
            setKbOut(r);
          })}
        >
          Ingest document
        </button>{" "}
        <input style={{ ...inputStyle, marginTop: 10 }} value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Ask a question" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const r = await api("/api/kb/ask", {
              method: "POST",
              body: JSON.stringify({ query: question }),
            });
            setKbOut(r);
          })}
        >
          Ask (RAG)
        </button>
        <Compliance data={kbOut} />
        <Json value={kbOut} />
      </Section>

      <Section title="Investment-Hypothesis Management (Module B)">
        <input style={inputStyle} value={hypTicker} onChange={(e) => setHypTicker(e.target.value)} placeholder="Ticker" />
        <input style={inputStyle} value={hypTitle} onChange={(e) => setHypTitle(e.target.value)} placeholder="Title" />
        <textarea style={{ ...inputStyle, minHeight: 60 }} value={hypThesis} onChange={(e) => setHypThesis(e.target.value)} placeholder="Thesis / investment logic" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            await api("/api/hypotheses", {
              method: "POST",
              body: JSON.stringify({ ticker: hypTicker, title: hypTitle, thesis: hypThesis }),
            });
            setHypList(await api("/api/hypotheses"));
          })}
        >
          Create
        </button>{" "}
        <button style={btnStyle} onClick={guard(async () => setHypList(await api("/api/hypotheses")))}>
          List mine
        </button>
        <Json value={hypList} />
      </Section>

      <Section title="Portfolio Risk-Assistance (Module C)">
        <input style={inputStyle} value={pfName} onChange={(e) => setPfName(e.target.value)} placeholder="Portfolio name" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const p = await api("/api/portfolios", {
              method: "POST",
              body: JSON.stringify({ name: pfName }),
            });
            const id = p.id ?? p.portfolio?.id;
            setPfId(id);
            await api(`/api/portfolios/${id}/holdings`, {
              method: "POST",
              body: JSON.stringify({
                holdings: [
                  { ticker: "NVDA", weight: 0.5, sector: "Tech" },
                  { ticker: "MSFT", weight: 0.3, sector: "Tech" },
                  { ticker: "LLY", weight: 0.2, sector: "Healthcare" },
                ],
              }),
            });
            setPfRisk(await api(`/api/portfolios/${id}/risk`));
          })}
        >
          Create + import sample + analyze risk
        </button>
        <Compliance data={pfRisk} />
        <Json value={pfRisk} />
      </Section>

      <Section title="Investment-Committee Material Auto-Generation (Module B)">
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const r = await api("/api/hypotheses/generate-ic-material", {
              method: "POST",
              body: JSON.stringify({ title: "Weekly IC pack" }),
            });
            setIcOut(r);
          })}
        >
          Generate IC material
        </button>
        <Compliance data={icOut} />
        <Json value={icOut} />
      </Section>

      <Section title="Knowledge Base Search — Vector Store (Module D)">
        <input style={inputStyle} value={kbQuery} onChange={(e) => setKbQuery(e.target.value)} placeholder="Semantic search query" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const r = await api("/api/kb/search", {
              method: "POST",
              body: JSON.stringify({ query: kbQuery, top_k: 5 }),
            });
            setKbSearch(r);
          })}
        >
          Search KB
        </button>
        <p style={{ color: "#8fa3bf", fontSize: 12, marginBottom: 0 }}>
          Each hit shows its retrieval <code>method</code> — <code>vector:*</code> (embedding store)
          or <code>tfidf</code> (fallback).
        </p>
        <Compliance data={kbSearch} />
        <Json value={kbSearch} />
      </Section>

      <Section title="Data Diode — One-Way Transfer (contract Art. 2.3 / 10.4)">
        <p style={{ color: "#8fa3bf", fontSize: 12, marginTop: 0 }}>
          Public intel flows External → Internal only. Confidential/internal content is
          rejected at the gate; there is no internal → external path. User-selectable per
          deployment (enabled on/off; mode software / offline / physical) — click
          <b> Show policy</b> to see the active config.
        </p>
        <input style={inputStyle} value={dSource} onChange={(e) => setDSource(e.target.value)} placeholder="Source (e.g. reuters.com)" />
        <input style={inputStyle} value={dTitle} onChange={(e) => setDTitle(e.target.value)} placeholder="Title" />
        <textarea style={{ ...inputStyle, minHeight: 60 }} value={dContent} onChange={(e) => setDContent(e.target.value)} placeholder="Public intelligence content" />
        <input style={inputStyle} value={dClass} onChange={(e) => setDClass(e.target.value)} placeholder="classification (public)" />
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const r = await api("/api/diode/ingest", {
              method: "POST",
              body: JSON.stringify({
                source: dSource,
                title: dTitle,
                content: dContent,
                classification: dClass,
              }),
            });
            setDiodeOut(r);
            setDiodeList(await api("/api/diode"));
          })}
        >
          Submit to staging
        </button>{" "}
        <button
          style={btnStyle}
          onClick={guard(async () => {
            const pkt = diodeOut?.packet;
            if (!pkt?.id) throw new Error("Submit a packet first");
            const r = await api(`/api/diode/packets/${pkt.id}/transfer?confirm=true`, { method: "POST" });
            setDiodeOut(r);
            setDiodeList(await api("/api/diode"));
          })}
        >
          Transfer one-way → internal KB
        </button>{" "}
        <button style={btnStyle} onClick={guard(async () => setDiodeOut(await api("/api/diode/policy")))}>
          Show policy
        </button>
        <Compliance data={diodeOut} />
        <Json value={diodeOut} />
        <Json value={diodeList} />
      </Section>
    </main>
  );
}
