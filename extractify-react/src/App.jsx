import React, { useEffect, useMemo, useRef, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  useNavigate,
  useParams,
  useLocation,
} from "react-router-dom";

/** Backend base URL (override via VITE_API_BASE in .env.local) */
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8000";

/* -------------------- data hook -------------------- */
function useFetch(url, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let mounted = true;
    setLoading(true);
    fetch(url)
      .then(async (r) => {
        if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
        return r.json();
      })
      .then((j) => mounted && setData(j))
      .catch((e) => mounted && setError(e))
      .finally(() => mounted && setLoading(false));
    return () => {
      mounted = false;
    };
  }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return { data, error, loading };
}

/* -------------------- layout -------------------- */
function Layout({ children }) {
  const location = useLocation();
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <nav className="sticky top-0 z-10 bg-white/80 backdrop-blur border-b">
        <div className="max-w-6xl mx-auto px-4 py-3 flex items-center justify-between">
          {/* Brand with STAR logo */}
          <Link to="/" className="flex items-center gap-2 font-bold">
            <img
              src="/star-logo.jpg"
              alt="STAR logo"
              className="h-7 w-7 rounded-full object-contain"
            />
            <span>Extractify</span>
          </Link>

          <div className="flex items-center gap-2">
            <Link
              to="/"
              className={`px-3 py-1.5 rounded-lg border ${
                location.pathname === "/" ? "bg-gray-100" : ""
              }`}
            >
              Home
            </Link>
            <Link
              to="/upload"
              className={`px-3 py-1.5 rounded-lg border ${
                location.pathname === "/upload" ? "bg-gray-100" : ""
              }`}
            >
              Upload
            </Link>
            <a
              className="px-3 py-1.5 rounded-lg border"
              href={`${API_BASE}/docs`}
              target="_blank"
              rel="noreferrer"
            >
              Swagger
            </a>
          </div>
        </div>
      </nav>

      <main className="max-w-6xl mx-auto p-4">{children}</main>

      <footer className="max-w-6xl mx-auto p-4 text-sm text-gray-500 flex justify-between">
        <span>© 2025 Extractify</span>
        <span>FastAPI + React</span>
      </footer>
    </div>
  );
}

/* -------- small UI helpers -------- */
function Badge({ label }) {
  const isSus = (label || "").toLowerCase() === "oui";
  const cls = isSus
    ? "bg-red-100 text-red-700 border-red-200"
    : "bg-green-100 text-green-700 border-green-200";
  return (
    <span className={`inline-block px-2 py-0.5 text-xs rounded border ${cls}`}>
      {label || "—"}
    </span>
  );
}
function MiniScore({ value }) {
  if (value == null) return null;
  return (
    <span className="inline-block ml-2 px-2 py-0.5 text-xs rounded bg-gray-100 border">
      score: {Number(value).toFixed(3)}
    </span>
  );
}

/* -------- reusable structured extraction view -------- */
function ExtractionView({ data, extraRight = null }) {
  if (!data) return null;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-3 gap-3">
      <div className="xl:col-span-2 bg-white rounded-2xl border shadow-sm p-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="font-semibold">Informations Générales</h2>
          {extraRight}
        </div>
        <table className="w-full text-sm">
          <tbody>
            <Row k="Assuré" v={data.assure} />
            <Row k="Tiers" v={data.tiers} />
            <Row k="Contrat" v={<code>{data.contrat}</code>} />
            <Row k="N° Dossier" v={data.numero_dossier} />
            <Row k="Expert" v={data.expert} />
            <Row k="Observation" v={data.observation} />
            <Row k="Date d'examen" v={data.date_examen} />
            <Row k="Date d'accident" v={data.date_accident} />
          </tbody>
        </table>
      </div>

      <div className="bg-white rounded-2xl border shadow-sm p-3">
        <h2 className="font-semibold mb-2">Résumé Véhicule</h2>
        <ul className="space-y-1 text-sm">
          <li><strong>Marque:</strong> {data.marque || ""}</li>
          <li><strong>Puissance:</strong> {data.puissance || ""}</li>
          <li><strong>Énergie:</strong> {data.energie || ""}</li>
          <li><strong>Couleur:</strong> {data.couleur || ""}</li>
          <li><strong>Date 1ère MC:</strong> {data.date_1_mc || ""}</li>
          <li><strong>N° Série:</strong> {data.numero_serie || ""}</li>
        </ul>
      </div>

      <div className="xl:col-span-3 bg-white rounded-2xl border shadow-sm p-3">
        <h2 className="font-semibold mb-2">Réparations & Totaux</h2>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="p-2">Désignation</th>
                <th className="p-2 text-right">Montant</th>
              </tr>
            </thead>
            <tbody>
              {Array.isArray(data.reparations) && data.reparations.length ? (
                data.reparations.map((r, i) => (
                  <tr key={i} className="border-t">
                    <td className="p-2">{r.designation}</td>
                    <td className="p-2 text-right">{r.montant}</td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td className="p-3" colSpan={2}>
                    —
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
        <div className="grid md:grid-cols-3 gap-2 mt-3 text-sm">
          <TotalBox label="Total M.O TTC" value={data.total_mo_ttc} />
          <TotalBox label="Total FOUR HT" value={data.total_four_ht} />
          <TotalBox label="Total Net" value={data.total_net} />
        </div>
      </div>
    </div>
  );
}

/* -------------------- Home: list ALL extractions -------------------- */
function HomePage() {
  const { data, error, loading } = useFetch(`${API_BASE}/api/extractions`, []);
  const [q, setQ] = useState("");
  const [pred, setPred] = useState({}); // { [id]: {suspect_oui_non, score_suspicion, algo_if_score} }
  const [busyAll, setBusyAll] = useState(false);
  const [busyRow, setBusyRow] = useState({}); // { [id]: true }

  const rows = useMemo(() => {
    if (!data) return [];
    if (!q) return data;
    const s = q.toLowerCase();
    return data.filter((r) =>
      [
        r.id,
        r.assure,
        r.tiers,
        r.contrat,
        r.numero_dossier,
        r.marque,
        r.date_examen,
      ]
        .join(" ")
        .toLowerCase()
        .includes(s)
    );
  }, [data, q]);

  const predictOne = async (id) => {
    setBusyRow((m) => ({ ...m, [id]: true }));
    try {
      const r = await fetch(`${API_BASE}/api/predict/${id}`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || "Prediction failed");
      setPred((m) => ({ ...m, [id]: j.prediction }));
    } catch (e) {
      setPred((m) => ({ ...m, [id]: { error: String(e?.message || e) } }));
    } finally {
      setBusyRow((m) => ({ ...m, [id]: false }));
    }
  };

  const predictAll = async () => {
    setBusyAll(true);
    try {
      const r = await fetch(`${API_BASE}/api/predict_all`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || "Prediction failed");
      const map = {};
      (j.results || []).forEach((row) => {
        if (row?.id && row?.prediction) map[row.id] = row.prediction;
      });
      setPred((m) => ({ ...m, ...map }));
    } catch (e) {
      alert(`Predict all error: ${String(e?.message || e)}`);
    } finally {
      setBusyAll(false);
    }
  };

  return (
    <Layout>
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <h1 className="text-2xl font-bold">All Extractions</h1>
        <span className="text-gray-500">Saved in SQLite</span>
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={predictAll}
            disabled={busyAll || !rows.length}
            className="px-3 py-1.5 rounded bg-blue-600 text-white disabled:opacity-50"
          >
            {busyAll ? "Predicting all…" : "Predict All"}
          </button>
        </div>
      </div>
      <div className="bg-white rounded-2xl border shadow-sm p-3">
        <div className="mb-2">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search (Assuré, Tiers, Contrat, Dossier, Marque)"
            className="w-full md:w-1/2 border rounded-lg px-3 py-2"
          />
        </div>
        {loading && <div className="p-4">Loading…</div>}
        {error && <div className="p-4 text-red-600">Error: {error.message}</div>}
        {!loading && !error && (
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 text-left">
                <tr>
                  <th className="p-2">ID</th>
                  <th className="p-2">Assuré</th>
                  <th className="p-2">Tiers</th>
                  <th className="p-2">Contrat</th>
                  <th className="p-2">N° Dossier</th>
                  <th className="p-2">Marque</th>
                  <th className="p-2">Date d'examen</th>
                  <th className="p-2">Fraud</th>
                  <th className="p-2"></th>
                </tr>
              </thead>
              <tbody>
                {rows.length ? (
                  rows.map((r) => {
                    const P = pred[r.id];
                    const waiting = busyRow[r.id];
                    return (
                      <tr className="border-t" key={r.id}>
                        <td className="p-2 text-gray-500">{r.id}</td>
                        <td className="p-2">{r.assure || ""}</td>
                        <td className="p-2">{r.tiers || ""}</td>
                        <td className="p-2 font-mono">{r.contrat || ""}</td>
                        <td className="p-2">{r.numero_dossier || ""}</td>
                        <td className="p-2">{r.marque || ""}</td>
                        <td className="p-2">{r.date_examen || ""}</td>
                        <td className="p-2">
                          {P?.error ? (
                            <span className="text-red-600 text-xs">{P.error}</span>
                          ) : P ? (
                            <>
                              <Badge label={P.suspect_oui_non} />
                              <MiniScore value={P.score_suspicion} />
                            </>
                          ) : (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </td>
                        <td className="p-2 text-right">
                          <div className="flex justify-end gap-2">
                            <button
                              onClick={() => predictOne(r.id)}
                              disabled={waiting}
                              className="px-2 py-1 border rounded disabled:opacity-50"
                            >
                              {waiting ? "…" : "Predict"}
                            </button>
                            <Link className="px-2 py-1 border rounded" to={`/extractions/${r.id}`}>
                              View
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })
                ) : (
                  <tr>
                    <td className="p-4 text-center" colSpan={9}>
                      No data yet. Go to <Link to="/upload">Upload</Link>.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}

/* -------------------- Upload: show JUST PROCESSED table -------------------- */
function UploadPage() {
  const inFilesRef = useRef(null);
  const inFolderRef = useRef(null);
  const [preview, setPreview] = useState([]);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [recentRows, setRecentRows] = useState([]); // ← only extractions that just finished
  const [pred, setPred] = useState({}); // predictions for recent rows
  const [busyRow, setBusyRow] = useState({}); // { [id]: true }
  const navigate = useNavigate();

  const collectFiles = () => {
    const f1 = Array.from(inFilesRef.current?.files || []);
    const f2 = Array.from(inFolderRef.current?.files || []);
    return [...f1, ...f2];
  };

  const renderList = () => {
    const files = collectFiles();
    setPreview(
      files.map((f) => ({
        name: f.webkitRelativePath || f.name,
        size: `${Math.round(f.size / 1024)} KB`,
      }))
    );
  };

  const onDrop = (e) => {
    e.preventDefault();
    const items = Array.from(e.dataTransfer.files || []);
    const pdfs = items.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    if (!pdfs.length) return;
    const dt = new DataTransfer();
    Array.from(inFilesRef.current.files || []).forEach((x) => dt.items.add(x));
    pdfs.forEach((x) => dt.items.add(x));
    inFilesRef.current.files = dt.files;
    renderList();
  };

  async function fetchExtraction(id) {
    const r = await fetch(`${API_BASE}/api/extractions/${id}`);
    if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
    return r.json();
  }

  const onUpload = async () => {
    const files = collectFiles();
    if (!files.length) return;
    const fd = new FormData();
    files.forEach((f) => fd.append("files", f));
    setBusy(true);
    setResult(null);
    setRecentRows([]);
    setPred({});
    try {
      const r = await fetch(`${API_BASE}/api/upload`, { method: "POST", body: fd });
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const j = await r.json();
      setResult(j);

      // Build the "Just processed" table from returned IDs
      if (Array.isArray(j.processed) && j.processed.length) {
        const ids = j.processed.map((p) => p.id);
        const details = await Promise.all(ids.map(fetchExtraction));
        setRecentRows(details);
      }
    } catch (e) {
      setResult({ error: e.message });
    } finally {
      setBusy(false);
    }
  };

  const predictOne = async (id) => {
    setBusyRow((m) => ({ ...m, [id]: true }));
    try {
      const r = await fetch(`${API_BASE}/api/predict/${id}`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || "Prediction failed");
      setPred((m) => ({ ...m, [id]: j.prediction }));
    } catch (e) {
      setPred((m) => ({ ...m, [id]: { error: String(e?.message || e) } }));
    } finally {
      setBusyRow((m) => ({ ...m, [id]: false }));
    }
  };

  return (
    <Layout>
      <h1 className="text-2xl font-bold mb-3">Select files or a folder (or drag & drop)</h1>

      <div className="bg-white rounded-2xl border shadow-sm p-4">
        {/* Drop zone with crisp centered logo (watermark) */}
        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          className="relative mb-3 border-2 border-dashed rounded-xl p-8 text-center bg-gray-50 overflow-hidden"
        >
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <img src="/star-logo.jpg" alt="" className="h-48 w-48 object-contain opacity-30" />
          </div>
          <div className="relative">
            <div className="text-3xl">☁️⬆️</div>
            <p className="mt-1">Drop PDFs here or use the buttons below</p>
            <p className="text-gray-500 text-sm">PDF only • Multiple files supported</p>
          </div>
        </div>

        <input ref={inFilesRef} type="file" accept=".pdf" multiple hidden onChange={renderList} />
        {/* @ts-ignore non-standard attributes are fine in Chromium */}
        <input ref={inFolderRef} type="file" webkitdirectory="" directory="" multiple hidden onChange={renderList} />

        <div className="flex flex-wrap gap-2 mb-2">
          <button className="px-3 py-1.5 rounded border" onClick={() => inFilesRef.current.click()} type="button">
            Choose files
          </button>
          <button className="px-3 py-1.5 rounded border" onClick={() => inFolderRef.current.click()} type="button">
            Choose folder
          </button>
        </div>

        <ul className="divide-y text-sm bg-white rounded-xl border mb-3">
          {preview.map((p, i) => (
            <li key={i} className="flex justify-between px-3 py-2">
              <span>{p.name}</span>
              <span className="text-gray-500">{p.size}</span>
            </li>
          ))}
          {!preview.length && <li className="px-3 py-2 text-gray-400">No files selected</li>}
        </ul>

        <div className="flex gap-2">
          <button
            disabled={busy || !preview.length}
            className="px-3 py-1.5 rounded bg-black text-white disabled:opacity-50"
            onClick={onUpload}
          >
            {busy ? "Processing…" : "Process"}
          </button>
          <button
            className="px-3 py-1.5 rounded border"
            type="button"
            onClick={() => {
              if (inFilesRef.current) inFilesRef.current.value = "";
              if (inFolderRef.current) inFolderRef.current.value = "";
              setPreview([]); setResult(null); setRecentRows([]); setPred({});
            }}
          >
            Clear
          </button>
        </div>

        {/* Upload summary (names + links) */}
        {result && (
          <div className="mt-4 grid md:grid-cols-2 gap-3">
            {result.error && (
              <div className="p-3 rounded border bg-red-50 border-red-200 text-red-700">
                Error: {result.error}
              </div>
            )}
            {Array.isArray(result.processed) && (
              <div className="p-3 rounded border">
                <h3 className="font-semibold mb-2">Processed ({result.processed.length})</h3>
                <ul className="list-disc ml-5 space-y-1">
                  {result.processed.map((p, i) => (
                    <li key={i}>
                      {p.name} → <Link className="underline" to={`/extractions/${p.id}`}>#{p.id}</Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {Array.isArray(result.skipped) && result.skipped.length > 0 && (
              <div className="p-3 rounded border">
                <h3 className="font-semibold mb-2">Skipped / Errors ({result.skipped.length})</h3>
                <ul className="list-disc ml-5 space-y-1">
                  {result.skipped.map((s, i) => (
                    <li key={i}>
                      {s.name} – <span className="text-gray-600">{s.reason}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {/* JUST PROCESSED table (only the extractions that just finished) */}
        {recentRows.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-xl font-semibold">Just processed</h2>
              <Link className="px-2 py-1 border rounded" to="/">Go to Home</Link>
            </div>
            <div className="overflow-auto">
              <table className="w-full text-sm bg-white rounded-2xl border">
                <thead className="bg-gray-50 text-left">
                  <tr>
                    <th className="p-2">ID</th>
                    <th className="p-2">Assuré</th>
                    <th className="p-2">Tiers</th>
                    <th className="p-2">Contrat</th>
                    <th className="p-2">N° Dossier</th>
                    <th className="p-2">Marque</th>
                    <th className="p-2">Date d'examen</th>
                    <th className="p-2">Fraud</th>
                    <th className="p-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {recentRows.map((r) => {
                    const P = pred[r.id];
                    const waiting = busyRow[r.id];
                    return (
                      <tr className="border-t" key={r.id}>
                        <td className="p-2 text-gray-500">{r.id}</td>
                        <td className="p-2">{r.assure || ""}</td>
                        <td className="p-2">{r.tiers || ""}</td>
                        <td className="p-2 font-mono">{r.contrat || ""}</td>
                        <td className="p-2">{r.numero_dossier || ""}</td>
                        <td className="p-2">{r.marque || ""}</td>
                        <td className="p-2">{r.date_examen || ""}</td>
                        <td className="p-2">
                          {P?.error ? (
                            <span className="text-red-600 text-xs">{P.error}</span>
                          ) : P ? (
                            <>
                              <Badge label={P.suspect_oui_non} />
                              <MiniScore value={P.score_suspicion} />
                            </>
                          ) : (
                            <span className="text-gray-400 text-xs">—</span>
                          )}
                        </td>
                        <td className="p-2 text-right">
                          <div className="flex justify-end">
                            <button
                              onClick={() => predictOne(r.id)}
                              disabled={waiting}
                              className="px-2 py-1 border rounded disabled:opacity-50"
                            >
                              {waiting ? "…" : "Predict"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}

/* -------------------- Detail page -------------------- */
function ViewPage() {
  const { id } = useParams();
  const { data, error, loading } = useFetch(`${API_BASE}/api/extractions/${id}`, [id]);
  const [P, setP] = useState(null);
  const [busy, setBusy] = useState(false);

  const predictThis = async () => {
    setBusy(true);
    setP(null);
    try {
      const r = await fetch(`${API_BASE}/api/predict/${id}`, { method: "POST" });
      const j = await r.json();
      if (!r.ok) throw new Error(j?.detail || "Prediction failed");
      setP(j.prediction);
    } catch (e) {
      setP({ error: String(e?.message || e) });
    } finally {
      setBusy(false);
    }
  };

  if (loading) return <Layout><div>Loading…</div></Layout>;
  if (error)   return <Layout><div className="text-red-600">Error: {error.message}</div></Layout>;
  if (!data || data.detail === "Not found")
    return <Layout><div className="text-red-600">Extraction not found.</div></Layout>;

  const extraRight = (
    <div className="flex items-center gap-2">
      <button
        onClick={predictThis}
        disabled={busy}
        className="px-2 py-1 border rounded disabled:opacity-50"
      >
        {busy ? "…" : "Predict This"}
      </button>
      {P && !P.error && (
        <>
          <Badge label={P.suspect_oui_non} />
          <MiniScore value={P.score_suspicion} />
        </>
      )}
      {P?.error && <span className="text-red-600 text-xs">{P.error}</span>}
    </div>
  );

  return (
    <Layout>
      <div className="flex items-center justify-between mb-3">
        <button className="px-3 py-1.5 rounded border" onClick={() => history.back()}>← Back</button>
        <h1 className="text-xl font-bold">Extraction #{data.id}</h1>
      </div>
      <ExtractionView data={data} extraRight={extraRight} />
    </Layout>
  );
}

/* -------------------- helpers -------------------- */
function Row({ k, v }) {
  return (
    <tr className="border-t">
      <th className="p-2 text-left align-top w-48 text-gray-600">{k}</th>
      <td className="p-2">{v || ""}</td>
    </tr>
  );
}

function TotalBox({ label, value }) {
  return (
    <div className="border rounded-xl p-3 flex items-baseline justify-between">
      <span className="text-gray-600">{label}</span>
      <strong>{value ?? ""}</strong>
    </div>
  );
}

/* -------------------- router -------------------- */
function App() {
  return (
    <BrowserRouter>
      <Routes>
        {/* Default → Home (all extractions) */}
        <Route path="/" element={<HomePage />} />

        {/* Upload page */}
        <Route path="/upload" element={<UploadPage />} />

        {/* Detail */}
        <Route path="/extractions/:id" element={<ViewPage />} />
      </Routes>
    </BrowserRouter>
  );
}

export default App;
