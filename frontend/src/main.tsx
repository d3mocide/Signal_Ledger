import { Component, FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api, ApiError, Area, Me, Overview, Run, send } from "./api";
import "./style.css";
type Page =
  | "overview"
  | "surveys"
  | "inventory"
  | "vendors"
  | "coverage"
  | "device"
  | "baselines"
  | "anomalies"
  | "access";
type Job = {
  id: number;
  filename: string;
  source_format: string;
  status: string;
  parser_version: string;
  report: Record<string, unknown>;
  created_at: string;
};
type Device = {
  id: number;
  token: string;
  oui_organization: string;
  category: string;
  first_seen: string;
  last_seen: string;
  last_protocol?: string | null;
  last_ssid?: string | null;
  has_stored_address?: boolean;
};
type DeviceDetail = {
  device: Device;
  summary: { observations: number; runs: number; coarse_cells: number };
  observations: {
    id: number;
    captured_at: string;
    protocol: string;
    ssid: string | null;
    security: string | null;
    rssi: number | null;
    spatial_cell: string | null;
    run_name: string;
  }[];
};
const msg = (e: unknown) =>
  e instanceof Error ? e.message : "Unexpected error";
const count = (value: unknown) => (typeof value === "number" ? value : 0);
function Auth({ done }: { done: () => void }) {
  const [s, setS] = useState(false),
    [u, setU] = useState(""),
    [p, setP] = useState(""),
    [e, setE] = useState("");
  useEffect(() => {
    api<{ setup_required: boolean }>("/v1/setup/status")
      .then((x) => setS(x.setup_required))
      .catch((x) => setE(msg(x)));
  }, []);
  async function go(x: FormEvent) {
    x.preventDefault();
    try {
      await send(s ? "/v1/setup" : "/v1/auth/login", {
        username: u,
        password: p,
      });
      done();
    } catch (x) {
      setE(msg(x));
    }
  }
  return (
    <main className="auth">
      <form className="auth-card" onSubmit={go}>
        <span className="mark">◫</span>
        <p className="eyebrow">SIGNAL LEDGER</p>
        <h1>{s ? "Create administrator" : "Welcome back"}</h1>
        <p>
          {s
            ? "The first account manages users and roles."
            : "Sign in to your private observatory."}
        </p>
        <label>
          Username
          <input value={u} onChange={(x) => setU(x.target.value)} required />
        </label>
        <label>
          Password
          <input
            type="password"
            value={p}
            onChange={(x) => setP(x.target.value)}
            minLength={10}
            required
          />
        </label>
        {e && <small>{e}</small>}
        <button>{s ? "Create account" : "Sign in"}</button>
      </form>
    </main>
  );
}
const navItems: { page: Page; label: string; icon: string; group: string }[] = [
  {
    page: "overview",
    label: "Command center",
    icon: "overview",
    group: "WORKSPACE",
  },
  {
    page: "inventory",
    label: "Device inventory",
    icon: "inventory",
    group: "",
  },
  {
    page: "vendors",
    label: "Vendor breakdown",
    icon: "vendors",
    group: "",
  },
  { page: "coverage", label: "Coverage explorer", icon: "coverage", group: "" },
  {
    page: "anomalies",
    label: "Review queue",
    icon: "anomalies",
    group: "ANALYSIS",
  },
  { page: "baselines", label: "Baselines", icon: "baselines", group: "" },
  {
    page: "surveys",
    label: "Capture imports",
    icon: "surveys",
    group: "COLLECTION",
  },
  { page: "access", label: "Administration", icon: "access", group: "" },
];
const descriptions: Record<Page, string> = {
  overview: "Your discovery landscape, at a glance.",
  inventory: "Explore site-scoped devices and the evidence behind them.",
  vendors: "See your device inventory grouped and ranked by OUI manufacturer.",
  coverage: "Understand where your collection has observed signals.",
  anomalies: "Review changes against your established baselines.",
  baselines: "Define expected behavior from completed survey runs.",
  surveys: "Drop a capture to create an import session, or organize sessions when useful.",
  access: "Manage workspace access and local enrichment.",
  device: "Trace an observed device back to its source evidence.",
};
function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    inventory: "M4 5h16v14H4z M8 9h8 M8 13h5",
    vendors: "M4 6h13 M4 12h17 M4 18h9",
    coverage:
      "M12 3v3 M12 18v3 M3 12h3 M18 12h3 M19 12a7 7 0 1 1-14 0 7 7 0 0 1 14 0 M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0",
    anomalies: "M12 3 2 20h20L12 3z M12 9v5 M12 17v.1",
    baselines: "M3 17h18 M5 13V8 M10 13V4 M15 13v-3 M20 13V6",
    surveys: "M12 16V3 M7 8l5-5 5 5 M4 14v6h16v-6",
    access: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4z M8 12l3 3 5-6",
    arrow: "M5 12h14 M14 7l5 5-5 5",
    refresh: "M20 8a8 8 0 1 0 0 8 M20 3v5h-5",
  };
  return (
    <svg
      className="icon"
      width="20"
      height="20"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d={paths[name] || paths.overview} />
    </svg>
  );
}
class WorkspaceBoundary extends Component<
  { children: ReactNode },
  { error: string }
> {
  state = { error: "" };
  static getDerivedStateFromError(e: Error) {
    return { error: e.message };
  }
  render() {
    return this.state.error ? (
      <section className="panel">
        <h2>Unable to display this workspace</h2>
        <p>{this.state.error}</p>
        <button onClick={() => this.setState({ error: "" })}>Try again</button>
      </section>
    ) : (
      this.props.children
    );
  }
}
function App() {
  const [me, setMe] = useState<Me | null>(null),
    [page, setPage] = useState<Page>("overview"),
    [o, setO] = useState<Overview | null>(null),
    [areas, setAreas] = useState<Area[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [mapDevice, setMapDevice] = useState(""),
    [vendorFilter, setVendorFilter] = useState(""),
    [deviceId, setDeviceId] = useState<number | null>(null),
    [note, setNote] = useState(""),
    [loading, setLoading] = useState(true),
    [refresh, setRefresh] = useState(0),
    [updated, setUpdated] = useState("");
  const load = async () => {
    setLoading(true);
    try {
      const m = await api<Me>("/v1/me");
      setMe(m);
      const [a, b, c, d] = await Promise.all([
        api<Overview>("/v1/overview"),
        api<Area[]>("/v1/survey-areas"),
        api<Run[]>("/v1/survey-runs"),
        api<Job[]>("/v1/ingestions"),
      ]);
      setO(a);
      setAreas(b);
      setRuns(c);
      setJobs(d);
      setNote("");
      setUpdated(
        new Date().toLocaleTimeString([], {
          hour: "2-digit",
          minute: "2-digit",
        }),
      );
      setRefresh((x) => x + 1);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setMe(null);
      else setNote(msg(e));
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    const handle = (e: PromiseRejectionEvent) => {
      setNote(msg(e.reason));
      e.preventDefault();
    };
    window.addEventListener("unhandledrejection", handle);
    return () => window.removeEventListener("unhandledrejection", handle);
  }, []);
  if (!me && loading)
    return (
      <main className="auth">
        <p className="loading">Opening Signal Ledger…</p>
      </main>
    );
  if (!me)
    return (
      <>
        {note && (
          <div className="notice" role="alert">
            {note}
            <button className="quiet" onClick={load}>
              Retry connection
            </button>
          </div>
        )}
        <Auth done={load} />
      </>
    );
  const title =
    page === "device"
      ? "Device evidence"
      : navItems.find((x) => x.page === page)!.label;
  return (
    <div className="app-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("overview");
          }}
        >
          <span className="brand-mark">
            <Icon name="baselines" />
          </span>
          <span>
            Signal Ledger<small>DISCOVERY OBSERVATORY</small>
          </span>
        </a>
        <div className="workspace-label">
          <span className="workspace-avatar">SL</span>
          <div>
            Private workspace<small>Authorized discovery</small>
          </div>
          <span className="connection-dot" />
        </div>
        <nav aria-label="Main navigation">
          {navItems
            .filter((x) => x.page !== "access" || me.role === "admin")
            .map((x) => (
              <div key={x.page}>
                {x.group && <p className="nav-group">{x.group}</p>}
                <button
                  aria-current={page === x.page ? "page" : undefined}
                  className={
                    page === x.page ||
                    (page === "device" && x.page === "inventory")
                      ? "active"
                      : ""
                  }
                  onClick={() => {
                    setPage(x.page);
                    setNote("");
                  }}
                >
                  <Icon name={x.icon} />
                  {x.label}
                  {x.page === "overview" && <span className="nav-active-dot" />}
                </button>
              </div>
            ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <Icon name="access" />
            <div>
              Private by design<small>Site-scoped tokens. Local maps.</small>
            </div>
          </div>
          <div className="profile">
            <span className="avatar">{me.actor.slice(0, 2).toUpperCase()}</span>
            <div>
              {me.actor}
              <small>{me.role}</small>
            </div>
            <button
              className="quiet"
              onClick={async () => {
                try {
                  await send("/v1/auth/logout", {});
                  setMe(null);
                } catch (e) {
                  setNote(msg(e));
                }
              }}
            >
              Sign out
            </button>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span className="muted">Workspace</span>
            <span className="breadcrumb">/</span>
            {title}
          </div>
          <span className="environment">
            <span className="connection-dot" /> Private instance
          </span>
        </header>
        <main id="workspace">
          <section className="page-heading">
            <div>
              <p className="eyebrow">
                {page === "overview"
                  ? "OPERATIONAL OVERVIEW"
                  : "SIGNAL LEDGER / " +
                    (page === "device" ? "INVENTORY" : page.toUpperCase())}
              </p>
              <h1>{title}</h1>
              <p className="muted">{descriptions[page]}</p>
            </div>
            <div className="heading-actions">
              <button className="secondary" disabled={loading} onClick={load}>
                <Icon name="refresh" />
                {loading ? "Refreshing…" : "Refresh"}
              </button>
              {["admin", "analyst"].includes(me.role) && page !== "surveys" && (
                <button onClick={() => setPage("surveys")}>
                  <Icon name="surveys" />
                  Import data
                </button>
              )}
            </div>
          </section>
          {note && (
            <div className="notice" role="alert">
              {note}
              <button
                className="quiet"
                aria-label="Dismiss notification"
                onClick={() => setNote("")}
              >
                ×
              </button>
            </div>
          )}
          <WorkspaceBoundary key={page + refresh}>
            {page === "overview" && (
              <Dashboard overview={o} jobs={jobs} runs={runs} go={setPage} />
            )}{" "}
            {page === "surveys" && (
              <Surveys areas={areas} runs={runs} reload={load} say={setNote} />
            )}{" "}
            {page === "inventory" && (
              <Inventory
                areas={areas}
                showDevice={(x) => {
                  setDeviceId(x);
                  setPage("device");
                }}
                mapDevice={(x) => {
                  setMapDevice(String(x));
                  setPage("coverage");
                }}
                initialVendor={vendorFilter}
              />
            )}{" "}
            {page === "vendors" && (
              <VendorBreakdown
                areas={areas}
                showVendor={(vendor) => {
                  setVendorFilter(vendor);
                  setPage("inventory");
                }}
              />
            )}{" "}
            {page === "coverage" && (
              <Coverage
                areas={areas}
                initialDevice={mapDevice}
                clearDevice={() => setMapDevice("")}
                mapTileKey={me.map_tile_key}
              />
            )}{" "}
            {page === "device" && deviceId && (
              <DeviceEvidence
                id={deviceId}
                back={() => setPage("inventory")}
                mapDevice={(x) => {
                  setMapDevice(String(x));
                  setPage("coverage");
                }}
                role={me.role}
              />
            )}{" "}
            {page === "baselines" && <Baselines areas={areas} runs={runs} />}{" "}
            {page === "anomalies" && <Anomalies areas={areas} />}{" "}
            {page === "access" && <Access me={me} />}
          </WorkspaceBoundary>
          <footer>
            <span>
              Signal Ledger <span className="footer-divider">/</span> Passive
              discovery intelligence
            </span>
            <span>
              {updated
                ? "Workspace refreshed at " + updated
                : "Workspace data unavailable"}
            </span>
          </footer>
        </main>
      </div>
    </div>
  );
}
type Analytics = {
  protocol_mix: Record<string, number>;
  vendor_mix: Record<string, number>;
  daily_observations: { day: string; count: number }[];
  mean_quality: number;
};
function Dashboard({
  overview: o,
  jobs,
  runs,
  go,
}: {
  overview: Overview | null;
  jobs: Job[];
  runs: Run[];
  go: (x: Page) => void;
}) {
  const [chosen, setChosen] = useState<Job | null>(jobs[0] || null),
    [analytics, setAnalytics] = useState<Analytics | null>(null),
    [cells, setCells] = useState<Cell[]>([]),
    [findings, setFindings] = useState<Finding[]>([]),
    [error, setError] = useState(""),
    [ready, setReady] = useState(false);
  useEffect(() => {
    Promise.all([
      api<Analytics>("/v1/analytics/discovery"),
      api<Cell[]>("/v1/map/clusters?limit=1000"),
      api<Finding[]>("/v1/anomalies"),
    ])
      .then(([a, c, f]) => {
        setAnalytics(a);
        setCells(c);
        setFindings(f);
      })
      .catch((e) => setError(msg(e)))
      .finally(() => setReady(true));
  }, []);
  const j = chosen,
    r = j?.report || {},
    pending = findings.filter((x) =>
      ["open", "needs_review"].includes(x.status),
    ),
    daily = analytics?.daily_observations.slice(-28) || [],
    peak = Math.max(1, ...daily.map((x) => x.count)),
    protocols = Object.entries(analytics?.protocol_mix || {}),
    total = protocols.reduce((n, [, v]) => n + v, 0);
  return (
    <div className="dashboard">
      {error && (
        <p className="notice" role="alert">
          Analytics could not be loaded: {error}
        </p>
      )}
      <div className="metrics">
        {[
          {
            label: "Total observations",
            value: o?.observations,
            icon: "baselines",
            detail: "Retained source evidence",
          },
          {
            label: "Observed devices",
            value: o?.devices,
            icon: "inventory",
            detail: "Site-scoped identities",
          },
          {
            label: "Capture sessions",
            value: o?.runs,
            icon: "surveys",
            detail: (o?.completed_runs ?? 0) + " completed",
          },
          {
            label: "Attributed devices",
            value: o ? o.devices - o.unattributable : undefined,
            icon: "vendors",
            detail:
              o && o.devices
                ? Math.round(((o.devices - o.unattributable) / o.devices) * 100) +
                  "% of inventory · " +
                  o.unattributable.toLocaleString() +
                  " unattributable"
                : "OUI-matched identities",
          },
        ].map((x) => (
          <div className="metric" key={x.label}>
            <div className="metric-label">
              {x.label}
              <Icon name={x.icon} />
            </div>
            <b>{x.value?.toLocaleString() ?? "—"}</b>
            <span>{x.detail}</span>
          </div>
        ))}
      </div>
      <div className="dashboard-grid">
        <section className="panel landscape">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SPATIAL INTELLIGENCE</p>
              <h2>Observation footprint</h2>
            </div>
            <button className="text-action" onClick={() => go("coverage")}>
              Explore coverage <Icon name="arrow" />
            </button>
          </div>
          {!ready ? (
            <div className="map-empty">Loading observation footprint…</div>
          ) : (
            <LocalMap cells={cells} compact />
          )}
          <div className="map-caption">
            <span>
              <i className="legend-dot" /> {cells.length.toLocaleString()}{" "}
              coarse cells shown · up to 1,000
            </span>
            <span>Relative coordinates · no external tiles</span>
          </div>
        </section>
        <section className="panel protocol-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">SIGNAL COMPOSITION</p>
              <h2>Protocol distribution</h2>
            </div>
            <Icon name="baselines" />
          </div>
          <div className="protocol-total">
            <b>{ready && !error ? total.toLocaleString() : "—"}</b>
            <span>retained observations</span>
          </div>
          <div className="stack-bar">
            {protocols.map(([k, v], i) => (
              <span
                key={k}
                style={{
                  width: (v / total) * 100 + "%",
                  background: ["#a6e36d", "#72b4ef", "#b8a2f4"][i % 3],
                }}
              />
            ))}
          </div>
          <div className="protocol-list">
            {protocols.map(([k, v], i) => (
              <div key={k}>
                <span>
                  <i
                    style={{
                      background: ["#a6e36d", "#72b4ef", "#b8a2f4"][i % 3],
                    }}
                  />
                  {k === "wifi" ? "Wi-Fi" : k === "bluetooth" ? "Bluetooth" : k}
                </span>
                <b>{v.toLocaleString()}</b>
                <small>{Math.round((v / total) * 100)}%</small>
              </div>
            ))}
            {ready && !protocols.length && (
              <p className="muted">Import a survey to see your signal mix.</p>
            )}
          </div>
          <div className="quality-row">
            <span>Mean evidence quality</span>
            <b>
              {analytics && total
                ? Math.round(analytics.mean_quality * 100) + "%"
                : "—"}
            </b>
          </div>
        </section>
        <section className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">COLLECTION HISTORY</p>
              <h2>Discovery activity</h2>
            </div>
            <span className="tag">Last {daily.length} observed days</span>
          </div>
          <div
            className="activity-chart"
            role="img"
            aria-label={
              daily.length
                ? "Daily retained observations: " +
                  daily.map((x) => x.day + ": " + x.count).join(", ")
                : "No recorded activity"
            }
          >
            {daily.length ? (
              daily.map((x) => (
                <div className="activity-column" key={x.day}>
                  <div
                    style={{
                      height: Math.max(3, (x.count / peak) * 100) + "%",
                    }}
                  >
                    <title>
                      {x.day}: {x.count.toLocaleString()} observations
                    </title>
                    <span>
                      {x.count.toLocaleString()}
                      <br />
                      {x.day}
                    </span>
                  </div>
                </div>
              ))
            ) : (
              <p className="muted">
                Your collection timeline will appear after the first import.
              </p>
            )}
          </div>
          <div className="chart-axis">
            <span>{daily[0]?.day || "No observations"}</span>
            <span>{daily.at(-1)?.day || ""}</span>
          </div>
        </section>
        <section className="panel review-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">ATTENTION & REVIEW</p>
              <h2>Changes to investigate</h2>
            </div>
            <span className="review-icon">
              <Icon name="anomalies" />
            </span>
          </div>
          <div className="review-count">
            <b>{ready && !error ? pending.length : "—"}</b>
            <span>findings awaiting review</span>
          </div>
          <p className="muted">
            {pending.length
              ? "Compare these changes with the baseline evidence before assigning a disposition."
              : "Baseline comparisons surface changes here. Scores guide review, not security verdicts."}
          </p>
          <button
            className="secondary full-width"
            onClick={() => go(pending.length ? "anomalies" : "baselines")}
          >
            {pending.length ? "Open review queue" : "Manage baselines"}
            <Icon name="arrow" />
          </button>
        </section>
        <section className="panel imports-panel">
          <div className="panel-heading">
            <div>
              <p className="eyebrow">INGESTION PIPELINE</p>
              <h2>Recent imports</h2>
            </div>
            <button className="text-action" onClick={() => go("surveys")}>
              Manage collection <Icon name="arrow" />
            </button>
          </div>
          <div className="imports-layout">
            <div className="list import-list">
              {jobs.length ? (
                jobs.slice(0, 8).map((x) => (
                  <button
                    key={x.id}
                    className={"history " + (j?.id === x.id ? "selected" : "")}
                    onClick={() => setChosen(x)}
                    aria-pressed={j?.id === x.id}
                  >
                    <span className="file-icon">
                      <Icon name="inventory" />
                    </span>
                    <span className="file-info">
                      <b>{x.filename}</b>
                      <small>
                        {x.source_format || "Source pending"} ·{" "}
                        {new Date(x.created_at).toLocaleDateString()}
                      </small>
                    </span>
                    <span className={"status " + x.status}>{x.status}</span>
                  </button>
                ))
              ) : (
                <div className="empty-state">
                  <Icon name="surveys" />
                  <h3>Your workspace is ready for its first signal.</h3>
                  <p>
                    Create an authorized area, start a run, and import an
                    export.
                  </p>
                  <button onClick={() => go("surveys")}>
                    Set up collection <Icon name="arrow" />
                  </button>
                </div>
              )}
            </div>
            {j && (
              <div className="import-detail">
                <p className="eyebrow">SELECTED IMPORT</p>
                <h3>{j.filename}</h3>
                <div className="import-stats">
                  {[
                    ["Accepted", r.accepted],
                    ["Duplicates", r.skipped_duplicates],
                    ["Rejected", r.rejected],
                  ].map(([label, value]) => (
                    <div key={String(label)}>
                      <b>{count(value).toLocaleString()}</b>
                      <span>{String(label)}</span>
                    </div>
                  ))}
                </div>
                <p className="muted">
                  {Math.round(count(r.location_completeness) * 100)}% location
                  present · {Math.round(count(r.coverage) * 100)}% collector
                  coverage
                </p>
                {Object.keys(r.reasons || {}).length > 0 && (
                  <p className="warning">
                    Rejected:{" "}
                    {Object.entries(r.reasons as Record<string, number>)
                      .map(([k, v]) => k + " (" + v + ")")
                      .join(", ")}
                  </p>
                )}
                <a
                  className="report-link"
                  href={"/v1/ingestions/" + j.id + "/report"}
                >
                  Download validation report ↗
                </a>
              </div>
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
function Surveys({
  areas,
  runs,
  reload,
  say,
}: {
  areas: Area[];
  runs: Run[];
  reload: () => void;
  say: (x: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  async function quickUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = new FormData(form);
    if (!(body.get("file") instanceof File)) return;
    setBusy(true);
    try {
      const response = await fetch("/v1/imports", {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      form.reset();
      say("Import queued. The new session will be named from this file.");
      for (let attempt = 0; attempt < 120; attempt++) {
        const status = await api<Job>("/v1/ingestions/" + job.id);
        if (!["queued", "processing"].includes(status.status)) {
          say("Import " + status.status + ": " + count(status.report.accepted).toLocaleString() + " accepted.");
          reload();
          return;
        }
        await new Promise((resolve) => setTimeout(resolve, 1000));
      }
      reload();
    } catch (error) {
      say(msg(error));
    } finally {
      setBusy(false);
    }
  }
  const [selected, setSelected] = useState<Set<number>>(new Set()),
    [target, setTarget] = useState(""),
    [newCollectionName, setNewCollectionName] = useState(""),
    [filing, setFiling] = useState(false);
  const visibleRuns = runs.slice(0, 20);
  function toggleSelected(id: number) {
    setSelected((current) => {
      const next = new Set(current);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }
  function toggleSelectAll() {
    setSelected((current) =>
      current.size === visibleRuns.length
        ? new Set()
        : new Set(visibleRuns.map((run) => run.id)),
    );
  }
  async function fileSelected() {
    const name = target === "__new__" ? newCollectionName.trim() : target;
    if (!name || !selected.size) return;
    setFiling(true);
    try {
      await Promise.all(
        [...selected].map((sessionId) =>
          send("/v1/sessions/" + sessionId + "/collection", { name }),
        ),
      );
      say(
        "Filed " +
          selected.size +
          " session(s) into " +
          name +
          ".",
      );
      setSelected(new Set());
      setTarget("");
      setNewCollectionName("");
      reload();
    } catch (error) {
      say(msg(error));
    } finally {
      setFiling(false);
    }
  }
  const collectionNames = new Map(areas.map((area) => [area.id, area.name]));
  async function addArea(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form);
    try {
      await send("/v1/survey-areas", {
        name: f.get("name"),
        authorization_ref: f.get("authorization_ref"),
        precision: f.get("precision"),
      });
      form.reset();
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  async function addRun(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form);
    try {
      await send("/v1/survey-runs", {
        survey_area_id: Number(f.get("survey_area_id")),
        name: f.get("name"),
        authorization_ref: f.get("authorization_ref"),
        collector_coverage: Number(f.get("collector_coverage")),
      });
      form.reset();
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  async function complete(id: number) {
    try {
      await send("/v1/survey-runs/" + id + "/complete", {});
      say("Run marked complete.");
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget),
      file = f.get("file");
    if (!(file instanceof File)) return;
    setBusy(true);
    const body = new FormData();
    body.set("file", file);
    body.set("source_format", String(f.get("source_format")));
    if (f.get("session_name")) body.set("session_name", String(f.get("session_name")));
    if (f.get("collection_name")) body.set("collection_name", String(f.get("collection_name")));
    try {
      const x = await fetch(
        "/v1/imports",
        { method: "POST", body, credentials: "same-origin" },
      );
      if (!x.ok) throw new Error(await x.text());
      const j = await x.json();
      for (let n = 0; n < 120; n++) {
        const z = await api<Job>("/v1/ingestions/" + j.id);
        if (!["queued", "processing"].includes(z.status)) {
          say(
            "Import " +
              z.status +
              ": " +
              count(z.report.accepted).toLocaleString() +
              " accepted · " +
              count(z.report.rejected).toLocaleString() +
              " rejected.",
          );
          reload();
          return;
        }
        await new Promise((q) => setTimeout(q, 1000));
      }
      say(
        "Import is still processing. Refresh the command center to check its status.",
      );
    } catch (x) {
      say(msg(x));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
    <div className="capture-flow">
      <section className="panel capture-drop">
        <p className="eyebrow">NEW CAPTURE</p>
        <h2>Drop a WiGLE or Kismet log</h2>
        <p className="muted">That is all you need to do. Signal Ledger names the import session from the filename and time, then you can explore it immediately.</p>
        <form onSubmit={quickUpload}>
          <select aria-label="Source format" name="source_format">
            <option value="wigle">WiGLE CSV</option>
            <option value="kismet">Kismet database / CSV / JSON</option>
          </select>
          <label className="file-drop">
            Source log<span>Choose a WiGLE or Kismet file</span>
            <input name="file" type="file" accept=".csv,.json,.ndjson,.kismet" required />
          </label>
          <button disabled={busy}>{busy ? "Importing…" : "Import capture"}</button>
        </form>
      </section>
      <section className="panel capture-history">
        <div className="panel-heading"><div><p className="eyebrow">RECENT CAPTURES</p><h2>Organize only when useful</h2></div><span className="tag">{runs.length} sessions</span></div>
        <p className="muted">Collections are labels applied after import. Leave a session unfiled if it does not need one. Select one or more below to file them together.</p>
        {!!visibleRuns.length && (
          <div className="toolbar filters">
            <label className="check">
              <input
                type="checkbox"
                checked={
                  selected.size === visibleRuns.length && visibleRuns.length > 0
                }
                onChange={toggleSelectAll}
              />
              Select all
            </label>
            <select
              aria-label="Target collection"
              value={target}
              onChange={(x) => setTarget(x.target.value)}
            >
              <option value="">Choose a collection…</option>
              {areas.map((x) => (
                <option key={x.id} value={x.name}>
                  {x.name}
                </option>
              ))}
              <option value="__new__">+ New collection…</option>
            </select>
            {target === "__new__" && (
              <input
                value={newCollectionName}
                onChange={(x) => setNewCollectionName(x.target.value)}
                placeholder="New collection name"
              />
            )}
            <button
              disabled={
                filing ||
                !selected.size ||
                !target ||
                (target === "__new__" && !newCollectionName.trim())
              }
              onClick={fileSelected}
            >
              {filing
                ? "Filing…"
                : "File " + (selected.size || "") + " selected"}
            </button>
          </div>
        )}
        <div className="list">
          {visibleRuns.map((run) => (
            <div key={run.id}>
              <label className="check">
                <input
                  type="checkbox"
                  checked={selected.has(run.id)}
                  onChange={() => toggleSelected(run.id)}
                />
                <b>{run.name}</b>
              </label>
              <span>{collectionNames.get(run.survey_area_id) || "Unfiled"} · {run.completed ? "Imported" : "Processing"}</span>
            </div>
          ))}
          {!runs.length && <p>No captures yet. Import a log to begin.</p>}
        </div>
      </section>
    </div>
    <div className="cards">
      <section className="panel">
        <p className="eyebrow">OPTIONAL GROUPING</p>
        <h2>Collection</h2>
        <p className="muted">
          Use a collection only when you want to compare or filter a set of captures.
        </p>
        <form onSubmit={addArea}>
          <label className="field-label">
            Collection name
            <input name="name" placeholder="e.g. Portland drives" required />
          </label>
          <label className="field-label">
            Notes (optional)
            <input
              name="authorization_ref"
              placeholder="e.g. device, route, or purpose"
            />
          </label>
          <select aria-label="Location precision" name="precision">
            <option value="coarse">Coarse cells (recommended)</option>
            <option value="exact">Exact, policy-approved</option>
          </select>
          <button>Create collection</button>
        </form>
        <List rows={areas.map((x) => x.name + " · " + x.precision)} />
      </section>
      <section className="panel">
        <p className="eyebrow">OPTIONAL LABEL</p>
        <h2>Named session</h2>
        <p className="muted">
          Direct imports make these automatically. Add one manually only when you need it.
        </p>
        <form onSubmit={addRun}>
          <select aria-label="Collection" name="survey_area_id" required>
            <option value="">Choose collection</option>
            {areas.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <label className="field-label">
            Session name
            <input name="name" placeholder="e.g. Sunday north loop" required />
          </label>
          <label className="field-label">
            Notes (optional)
            <input
              name="authorization_ref"
              placeholder="e.g. source device or route"
            />
          </label>
          <label className="field-label">
            Collector coverage (0–1)
            <input
              name="collector_coverage"
              type="number"
              min="0"
              max="1"
              step=".05"
              defaultValue="1"
            />
          </label>
          <button>Create session</button>
        </form>
        <div className="list">
          {runs.map((x) => (
            <div key={x.id}>
              <b>
                {x.name} · {Math.round(x.collector_coverage * 100)}% coverage
              </b>
              <span>{x.completed ? "Complete" : "Open"}</span>
              {!x.completed && (
                <button className="quiet" onClick={() => complete(x.id)}>
                  Mark complete
                </button>
              )}
            </div>
          ))}
        </div>
      </section>
      <section className="panel">
        <p className="eyebrow">DIRECT IMPORT</p>
        <h2>Drop a capture</h2>
        <p className="muted">A session is created from the filename and import time. Both fields below are optional.</p>
        <form onSubmit={upload}>
          <label className="field-label">Session name (optional)<input name="session_name" placeholder="Defaults to the filename" /></label>
          <label className="field-label">Collection (optional)<input name="collection_name" placeholder="Defaults to Personal captures" /></label>
          <select aria-label="Source format" name="source_format">
            <option value="wigle">WiGLE CSV</option>
            <option value="kismet">Kismet database / CSV / JSON</option>
          </select>
          <label className="file-drop">
            Source export<span>Choose a WiGLE or Kismet file</span>
            <input
              name="file"
              type="file"
              accept=".csv,.json,.ndjson,.kismet"
              required
            />
          </label>
          <button disabled={busy}>
            {busy ? "Validating…" : "Upload & validate"}
          </button>
        </form>
      </section>
    </div>
    </>
  );
}
type VendorRow = { oui_organization: string; device_count: number; share: number };
function VendorBreakdown({
  areas,
  showVendor,
}: {
  areas: Area[];
  showVendor: (vendor: string) => void;
}) {
  const [a, setA] = useState(""),
    [rows, setRows] = useState<VendorRow[]>([]),
    [loading, setLoading] = useState(false);
  async function load(area = a) {
    setLoading(true);
    try {
      setRows(
        await api<VendorRow[]>(
          "/v1/devices/vendors" + (area ? "?area_id=" + area : ""),
        ),
      );
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
  }, []);
  const totalDevices = rows.reduce((sum, x) => sum + x.device_count, 0),
    top = rows.slice(0, 15),
    max = Math.max(1, ...top.map((x) => x.device_count));
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">DEVICE LEDGER</p>
          <h2>Vendor breakdown</h2>
          <p className="muted">
            {totalDevices.toLocaleString()} devices across{" "}
            {rows.length.toLocaleString()} OUI organizations
            {top.length < rows.length
              ? " · top " + top.length + " charted below"
              : ""}
            .
          </p>
        </div>
        <select
          aria-label="Survey area"
          value={a}
          onChange={(x) => {
            setA(x.target.value);
            load(x.target.value);
          }}
        >
          <option value="">All areas</option>
          {areas.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
      </div>
      <div className="coverage">
        <div>
          {top.map((x) => (
            <div className="bar" key={x.oui_organization}>
              <button
                className="bar-label"
                title={x.oui_organization}
                onClick={() => showVendor(x.oui_organization)}
              >
                {x.oui_organization}
              </button>
              <i style={{ width: (x.device_count / max) * 100 + "%" }}></i>
              <b>{x.device_count.toLocaleString()}</b>
            </div>
          ))}
          {!top.length && !loading && (
            <p className="muted">No devices matched.</p>
          )}
        </div>
        <aside>
          <h3>Leading vendor</h3>
          {top[0] ? (
            <p>
              <b>{top[0].oui_organization}</b>
              <br />
              {Math.round(top[0].share * 100)}% of devices
            </p>
          ) : (
            <p className="muted">No data yet.</p>
          )}
        </aside>
      </div>
      <h3>All vendors</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>OUI organization</th>
              <th>Devices</th>
              <th>Share</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((x) => (
              <tr key={x.oui_organization}>
                <td>{x.oui_organization}</td>
                <td>{x.device_count.toLocaleString()}</td>
                <td>{(x.share * 100).toFixed(1)}%</td>
                <td>
                  <button
                    className="quiet map-action"
                    onClick={() => showVendor(x.oui_organization)}
                  >
                    View devices
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!rows.length && !loading && (
        <p className="muted">No matching devices.</p>
      )}
    </section>
  );
}
function Inventory({
  areas,
  showDevice,
  mapDevice,
  initialVendor,
}: {
  areas: Area[];
  showDevice: (id: number) => void;
  mapDevice: (id: number) => void;
  initialVendor: string;
}) {
  const [a, setA] = useState(""),
    [v, setV] = useState(initialVendor),
    [attributedOnly, setAttributedOnly] = useState(false),
    [sort, setSort] = useState("last_seen"),
    [direction, setDirection] = useState<"asc" | "desc">("desc"),
    [d, setD] = useState<Device[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0),
    [loading, setLoading] = useState(false);
  const limit = 50;
  async function load(
    next = offset,
    nextSort = sort,
    nextDirection = direction,
    nextAttributedOnly = attributedOnly,
    nextVendor = v,
  ) {
    setLoading(true);
    try {
      const q = new URLSearchParams({
        limit: String(limit),
        offset: String(next),
        vendor: nextVendor,
        sort: nextSort,
        direction: nextDirection,
      });
      if (a) q.set("area_id", a);
      if (nextAttributedOnly) q.set("attributed_only", "true");
      const x = await api<{ items: Device[]; total: number }>(
        "/v1/devices?" + q,
      );
      setD(x.items);
      setTotal(x.total);
      setOffset(next);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load(0);
  }, []);
  useEffect(() => {
    if (initialVendor) {
      setV(initialVendor);
      load(0, sort, direction, attributedOnly, initialVendor);
    }
  }, [initialVendor]);
  function toggleSort(column: string) {
    const nextDirection: "asc" | "desc" =
      column === sort
        ? direction === "asc"
          ? "desc"
          : "asc"
        : column === "oui_organization" || column === "category"
          ? "asc"
          : "desc";
    setSort(column);
    setDirection(nextDirection);
    load(0, column, nextDirection);
  }
  const sortIndicator = (column: string) =>
    sort === column ? (direction === "asc" ? " ▲" : " ▼") : "";
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">PSEUDONYMOUS INVENTORY</p>
          <h2>Devices from imported runs</h2>
        </div>
        <select
          aria-label="Survey area"
          value={a}
          onChange={(x) => setA(x.target.value)}
        >
          <option value="">All areas</option>
          {areas.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
      </div>
      <div className="toolbar filters">
        <input
          value={v}
          onChange={(x) => setV(x.target.value)}
          placeholder="OUI organization"
        />
        <label className="check">
          <input
            type="checkbox"
            checked={attributedOnly}
            onChange={(x) => {
              setAttributedOnly(x.target.checked);
              load(0, sort, direction, x.target.checked);
            }}
          />
          Attributed only
        </label>
        <button onClick={() => load(0)}>Apply</button>
      </div>
      <p className="muted">
        {total.toLocaleString()} matching devices · showing{" "}
        {total ? offset + 1 : 0}–{Math.min(offset + limit, total)}
      </p>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Site token</th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("oui_organization")}
                >
                  OUI organization{sortIndicator("oui_organization")}
                </button>
              </th>
              <th>Radio</th>
              <th>Last network</th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("category")}
                >
                  Category{sortIndicator("category")}
                </button>
              </th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("first_seen")}
                >
                  First seen{sortIndicator("first_seen")}
                </button>
              </th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("last_seen")}
                >
                  Last seen{sortIndicator("last_seen")}
                </button>
              </th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {d.map((x) => (
              <tr key={x.id}>
                <td>
                  <button
                    className="token-button"
                    onClick={() => showDevice(x.id)}
                  >
                    <code>{x.token.slice(0, 14)}…</code>
                  </button>
                </td>
                <td>{x.oui_organization}</td>
                <td>{x.last_protocol || "—"}</td>
                <td>{x.last_ssid || "—"}</td>
                <td>{x.category}</td>
                <td>{new Date(x.first_seen).toLocaleString()}</td>
                <td>{new Date(x.last_seen).toLocaleString()}</td>
                <td>
                  <button
                    className="quiet map-action"
                    onClick={() => mapDevice(x.id)}
                  >
                    Map sightings
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!d.length && !loading && <p className="muted">No matching devices.</p>}
      <div className="pager">
        <button
          disabled={offset === 0 || loading}
          onClick={() => load(Math.max(0, offset - limit))}
        >
          Previous
        </button>
        <span>
          Page {Math.floor(offset / limit) + 1} of{" "}
          {Math.max(1, Math.ceil(total / limit))}
        </span>
        <button
          disabled={offset + limit >= total || loading}
          onClick={() => load(offset + limit)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
type Cell = {
  cell: string;
  count: number;
  avg_rssi: number | null;
  device_count: number;
};
function DeviceEvidence({
  id,
  back,
  mapDevice,
  role,
}: {
  id: number;
  back: () => void;
  mapDevice: (id: number) => void;
  role: string;
}) {
  const [d, setD] = useState<DeviceDetail | null>(null),
    [error, setError] = useState(""),
    [address, setAddress] = useState(""),
    [revealing, setRevealing] = useState(false),
    [revealError, setRevealError] = useState("");
  useEffect(() => {
    setD(null);
    setAddress("");
    setRevealError("");
    api<DeviceDetail>("/v1/devices/" + id)
      .then(setD)
      .catch((x) => setError(msg(x)));
  }, [id]);
  async function reveal() {
    setRevealing(true);
    setRevealError("");
    try {
      const x = await send<{ address: string }>(
        "/v1/devices/" + id + "/reveal-address",
        {},
      );
      setAddress(x.address);
    } catch (x) {
      setRevealError(msg(x));
    } finally {
      setRevealing(false);
    }
  }
  if (error)
    return (
      <section className="panel">
        <button className="quiet" onClick={back}>
          ← Inventory
        </button>
        <p className="warning">{error}</p>
      </section>
    );
  if (!d) return <section className="panel">Loading device evidence…</section>;
  const x = d.device;
  return (
    <section className="panel">
      <button className="quiet" onClick={back}>
        ← Inventory
      </button>
      <p className="eyebrow">DEVICE EVIDENCE</p>
      <h2>
        <code>{x.token.slice(0, 22)}…</code>
      </h2>
      <p className="muted">
        OUI organization: {x.oui_organization} · Category hypothesis:{" "}
        {x.category}
      </p>
      <div className="result">
        <b>{d.summary.observations.toLocaleString()}</b>
        <span>observations</span>
        <b>{d.summary.runs.toLocaleString()}</b>
        <span>runs</span>
        <b>{d.summary.coarse_cells.toLocaleString()}</b>
        <span>coarse cells</span>
      </div>
      <button onClick={() => mapDevice(x.id)}>Map sightings</button>
      {role === "admin" && x.has_stored_address && (
        <div className="notice">
          {address ? (
            <span>
              Real address: <code>{address}</code>
            </span>
          ) : (
            <span>
              This device was captured in a policy-approved exact-precision
              area, so its real address was retained, encrypted.
            </span>
          )}
          <button
            className="quiet"
            onClick={reveal}
            disabled={revealing || !!address}
          >
            {address ? "Revealed" : revealing ? "Revealing…" : "Reveal address"}
          </button>
        </div>
      )}
      {revealError && <p className="warning">{revealError}</p>}
      <h3>Recent source facts</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>When</th>
              <th>Run</th>
              <th>Radio</th>
              <th>Network</th>
              <th>RSSI</th>
              <th>Coarse cell</th>
            </tr>
          </thead>
          <tbody>
            {d.observations.map((o) => (
              <tr key={o.id}>
                <td>{new Date(o.captured_at).toLocaleString()}</td>
                <td>{o.run_name}</td>
                <td>{o.protocol}</td>
                <td>{o.ssid || "—"}</td>
                <td>{o.rssi ?? "—"}</td>
                <td>{o.spatial_cell || "No location"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!d.observations.length && (
        <p className="muted">No retained observations.</p>
      )}
    </section>
  );
}
type Track = {
  segments: { cell: string; captured_at: string }[][];
  truncated: boolean;
};
function GeographicMap({ cells, track, tileKey }: { cells: Cell[]; track: Track; tileKey: string }) {
  const node = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!node.current) return;
    const points = cells.map((cell) => cell.cell.split(",").map(Number) as [number, number]).filter(([lat, lon]) => Number.isFinite(lat) && Number.isFinite(lon) && !(lat === 0 && lon === 0));
    if (!points.length) return;
    const map = new maplibregl.Map({ container: node.current, style: `https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json?key=${tileKey}`, center: [points[0][1], points[0][0]], zoom: 12 });
    map.addControl(new maplibregl.NavigationControl(), "top-right");
    map.on("load", () => {
      const features = cells.map((cell) => { const [lat, lon] = cell.cell.split(",").map(Number); return { type: "Feature" as const, properties: { count: cell.count, devices: cell.device_count, cell: cell.cell }, geometry: { type: "Point" as const, coordinates: [lon, lat] } }; });
      const lines = track.segments.map((segment) => ({ type: "Feature" as const, properties: {}, geometry: { type: "LineString" as const, coordinates: segment.map((item) => { const [lat, lon] = item.cell.split(",").map(Number); return [lon, lat]; }) } }));
      map.addSource("capture-points", { type: "geojson", data: { type: "FeatureCollection", features } });
      map.addSource("capture-track", { type: "geojson", data: { type: "FeatureCollection", features: lines } });
      map.addLayer({ id: "capture-track", type: "line", source: "capture-track", paint: { "line-color": "#5a8d44", "line-width": 3, "line-opacity": .75 } });
      map.addLayer({ id: "capture-halo", type: "circle", source: "capture-points", paint: { "circle-radius": ["interpolate", ["linear"], ["get", "count"], 1, 5, 100, 13], "circle-color": "#b0e780", "circle-opacity": .28, "circle-stroke-width": 1, "circle-stroke-color": "#436c33" } });
      map.addLayer({ id: "capture-point", type: "circle", source: "capture-points", paint: { "circle-radius": 4, "circle-color": "#d7f5bb", "circle-stroke-width": 1, "circle-stroke-color": "#325025" } });
      map.on("click", "capture-point", (event) => { const properties = event.features?.[0].properties || {}; new maplibregl.Popup().setLngLat(event.lngLat).setHTML(`<b>${properties.cell}</b><br>${properties.count} observations · ${properties.devices} devices`).addTo(map); });
      const bounds = points.reduce((value, [lat, lon]) => value.extend([lon, lat]), new maplibregl.LngLatBounds([points[0][1], points[0][0]], [points[0][1], points[0][0]]));
      map.fitBounds(bounds, { padding: 52, maxZoom: 16 });
    });
    return () => map.remove();
  }, [cells, track, tileKey]);
  return <figure className="geographic-map"><div ref={node} /><figcaption><b>Geographic basemap enabled.</b> Map tiles are requested only for this viewport from CARTO; your capture records remain in Signal Ledger.</figcaption></figure>;
}
function LocalMap({
  cells,
  track,
  compact,
}: {
  cells: Cell[];
  track?: Track;
  compact?: boolean;
}) {
  const points = cells
    .map((x) => {
      const [lat, lon] = x.cell.split(",").map(Number);
      return { ...x, lat, lon };
    })
    .filter(
      (x) =>
        Number.isFinite(x.lat) &&
        Number.isFinite(x.lon) &&
        !(x.lat === 0 && x.lon === 0),
    );
  if (!points.length)
    return (
      <div className="map-empty">
        No coarse location data matches this selection.
      </div>
    );
  const lats = points.map((x) => x.lat),
    lons = points.map((x) => x.lon),
    minLat = Math.min(...lats),
    maxLat = Math.max(...lats),
    minLon = Math.min(...lons),
    maxLon = Math.max(...lons),
    meanLat = (minLat + maxLat) / 2,
    longitudeScale = Math.cos((meanLat * Math.PI) / 180),
    spanLat = Math.max(0.001, maxLat - minLat),
    spanLon = Math.max(0.001, (maxLon - minLon) * longitudeScale),
    maxCount = Math.max(...points.map((x) => x.count));
  const W = compact ? 1120 : 800;
  const H = compact ? 300 : 464;
  const left = compact ? 52 : 42;
  const right = compact ? 18 : 42;
  const top = compact ? 44 : 58;
  const bottom = compact ? 46 : 42;
  const plotW = W - left - right;
  const plotH = H - top - bottom;
  const EDGE_PAD = 31; // largest halo radius (27 + 4); keeps points off the axis labels
  const xy = (x: { lat: number; lon: number }) => ({
    x:
      left +
      EDGE_PAD +
      (((x.lon - minLon) * longitudeScale) / spanLon) * (plotW - EDGE_PAD * 2),
    y:
      top +
      plotH -
      EDGE_PAD -
      ((x.lat - minLat) / spanLat) * (plotH - EDGE_PAD * 2),
  });
  const paths = (track?.segments || []).map((segment) =>
    segment
      .map((item) => {
        const [lat, lon] = item.cell.split(",").map(Number);
        return xy({ lat, lon });
      })
      .filter((item) => Number.isFinite(item.x) && Number.isFinite(item.y)),
  );
  const ticks = [0, 1, 2, 3, 4];
  const gridPath =
    ticks.map((t) => `M${left} ${top + (t * plotH) / 4}H${left + plotW}`).join(" ") +
    " " +
    ticks.map((t) => `M${left + (t * plotW) / 4} ${top}V${top + plotH}`).join(" ");
  return (
    <figure className="local-map">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Coarse observation map">
        <rect x="0" y="0" width={W} height={H} rx="12" />
        <path className="map-grid" d={gridPath} />
        {ticks.map((tick) => (
          <text
            className="axis-label axis-lat"
            key={"lat" + tick}
            x="8"
            y={top + 4 + (tick * plotH) / 4}
          >
            {(maxLat - ((maxLat - minLat) * tick) / 4).toFixed(3)}°
          </text>
        ))}
        {ticks.map((tick) => (
          <text
            className="axis-label axis-lon"
            key={"lon" + tick}
            x={left + (tick * plotW) / 4}
            y={top + plotH + 20}
            textAnchor={tick === 0 ? "start" : tick === 4 ? "end" : "middle"}
          >
            {(minLon + ((maxLon - minLon) * tick) / 4).toFixed(3)}°
          </text>
        ))}
        {paths.map((path, index) =>
          path.length > 1 ? (
            <path
              className="map-track"
              key={index}
              d={path
                .map((point, pointIndex) =>
                  (pointIndex ? "L" : "M") + point.x + " " + point.y,
                )
                .join(" ")}
            />
          ) : null,
        )}
        {points.map((p) => {
          const q = xy(p),
            radius = 7 + Math.sqrt(p.count / maxCount) * 20;
          return (
            <g key={p.cell}>
              <circle className="map-halo" cx={q.x} cy={q.y} r={radius + 4} />
              <circle className="map-point" cx={q.x} cy={q.y} r={radius}>
                <title>
                  {p.cell}: {p.count.toLocaleString()} observations across{" "}
                  {p.device_count.toLocaleString()} device
                  {p.device_count === 1 ? "" : "s"}
                </title>
              </circle>
            </g>
          );
        })}
        <text className="axis-title" x={left} y={top - 27}>Latitude (°)</text>
        <text className="axis-title" x={left + plotW} y={top + plotH + 36} textAnchor="end">Longitude (°)</text>
      </svg>
      <figcaption>
        <b>{points.length.toLocaleString()} coarse location cells</b> shown. One
        circle is a rounded 0.001° GPS cell, not a device; its size represents
        the number of observations collected in that cell. The thin line shows
        collection movement and breaks between sessions or five-minute gaps.
        Placeholder 0,0 GPS values are excluded.
      </figcaption>
    </figure>
  );
}
function Coverage({
  areas,
  initialDevice,
  clearDevice,
  mapTileKey,
}: {
  areas: Area[];
  initialDevice: string;
  clearDevice: () => void;
  mapTileKey: string | null;
}) {
  const [a, setA] = useState(""),
    [r, setR] = useState(""),
    [d, setD] = useState(initialDevice),
    [protocol, setProtocol] = useState(""),
    [vendor, setVendor] = useState(""),
    [minRssi, setMinRssi] = useState(""),
    [start, setStart] = useState(""),
    [end, setEnd] = useState(""),
    [c, setC] = useState<Cell[]>([]),
    [track, setTrack] = useState<Track>({ segments: [], truncated: false }),
    [geographic, setGeographic] = useState(false),
    [tileNotice, setTileNotice] = useState(false),
    [mix, setMix] = useState<Record<string, number>>({}),
    [runs, setRuns] = useState<Run[]>([]),
    [devices, setDevices] = useState<Device[]>([]);
  function params(area = a, run = r, device = d) {
    const q = new URLSearchParams();
    if (area) q.set("area_id", area);
    if (run) q.set("run_id", run);
    if (device) q.set("device_id", device);
    if (protocol) q.set("protocol", protocol);
    if (vendor) q.set("vendor", vendor);
    if (minRssi) q.set("min_rssi", minRssi);
    if (start) q.set("start", start + "T00:00:00");
    if (end) q.set("end", end + "T23:59:59");
    return q;
  }
  async function load(area = a, run = r, device = d) {
    const q = params(area, run, device),
      t = q.toString() ? "?" + q : "",
      x = await Promise.all([
        api<Cell[]>("/v1/map/clusters" + t),
        api<{ protocol_mix: Record<string, number> }>(
          "/v1/analytics/discovery" + t,
        ),
        api<Track>("/v1/map/track" + t),
      ]);
    setC(x[0]);
    setMix(x[1].protocol_mix);
    setTrack(x[2]);
  }
  useEffect(() => {
    Promise.all([
      api<Run[]>("/v1/survey-runs"),
      api<{ items: Device[] }>("/v1/devices?limit=500"),
    ]).then((x) => {
      setRuns(x[0]);
      setDevices(x[1].items);
      load();
    });
  }, []);
  useEffect(() => {
    setD(initialDevice);
    load(a, r, initialDevice);
  }, [initialDevice]);
  const max = Math.max(1, ...c.map((x) => x.count));
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">CAPTURE MAP</p>
          <h2>
            {d ? "Where this device was observed" : "Explore collected GPS coverage"}
          </h2>
          <p className="muted">
            {geographic && mapTileKey
              ? "Locations are rounded cells, not precise device points. The geographic basemap requests map tiles for the visible viewport from CARTO."
              : "Locations are rounded cells, not precise device points. No third-party map tiles receive this data."}
          </p>
        </div>
        <button
          className="secondary"
          disabled={!mapTileKey}
          title={mapTileKey ? undefined : "Set CARTO_API_KEY in the server .env to enable the geographic basemap"}
          onClick={() =>
            setGeographic((value) => {
              const next = !value;
              if (next) setTileNotice(true);
              return next;
            })
          }
        >
          {geographic ? "Use private grid" : "Show geographic basemap"}
        </button>
        <select
          aria-label="Collection"
          value={a}
          onChange={(x) => {
            setA(x.target.value);
            setR("");
          }}
        >
          <option value="">All collections</option>
          {areas.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
        <select
          aria-label="Import session"
          value={r}
          onChange={(x) => setR(x.target.value)}
        >
          <option value="">All sessions</option>
          {runs
            .filter((x) => !a || String(x.survey_area_id) === a)
            .map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
        </select>
        <select
          aria-label="Device"
          value={d}
          onChange={(x) => setD(x.target.value)}
        >
          <option value="">All devices</option>
          {devices.map((x) => (
            <option key={x.id} value={x.id}>
              {x.token.slice(0, 14)}… · {x.oui_organization}
            </option>
          ))}
        </select>
      </div>
      <div className="toolbar filters">
        <select
          aria-label="Radio protocol"
          value={protocol}
          onChange={(x) => setProtocol(x.target.value)}
        >
          <option value="">All radio types</option>
          <option value="wifi">Wi-Fi</option>
          <option value="bluetooth">Bluetooth</option>
        </select>
        <input
          value={vendor}
          onChange={(x) => setVendor(x.target.value)}
          placeholder="OUI organization"
        />
        <input
          value={minRssi}
          onChange={(x) => setMinRssi(x.target.value)}
          type="number"
          placeholder="Min RSSI"
        />
        <input
          aria-label="Start date"
          value={start}
          onChange={(x) => setStart(x.target.value)}
          type="date"
        />
        <input
          aria-label="End date"
          value={end}
          onChange={(x) => setEnd(x.target.value)}
          type="date"
        />
        <button onClick={() => load()}>Apply filters</button>
        {d && (
          <button
            className="quiet"
            onClick={() => {
              setD("");
              clearDevice();
              load(a, r, "");
            }}
          >
            Clear device
          </button>
        )}
      </div>
      {geographic && mapTileKey && tileNotice && (
        <div className="notice" role="alert">
          This basemap sends the visible map area to CARTO's tile servers to
          draw roads and terrain; your captures and coarse cells stay in
          Signal Ledger and are never sent to them.
          <button
            className="quiet"
            aria-label="Dismiss notification"
            onClick={() => setTileNotice(false)}
          >
            Dismiss
          </button>
        </div>
      )}
      {geographic && mapTileKey ? (
        <GeographicMap cells={c} track={track} tileKey={mapTileKey} />
      ) : (
        <LocalMap cells={c} track={track} />
      )}
      <div className="coverage">
        <div>
          {c.slice(0, 50).map((x) => (
            <div className="bar" key={x.cell}>
              <span>{x.cell}</span>
              <i style={{ width: (x.count / max) * 100 + "%" }}></i>
              <b>{x.count.toLocaleString()}</b>
            </div>
          ))}
        </div>
        <aside>
          <h3>Protocol mix</h3>
          {Object.entries(mix).map(([k, v]) => (
            <p key={k}>
              {k}: <b>{v}</b>
            </p>
          ))}
        </aside>
      </div>
    </section>
  );
}
type Baseline = {
  id: number;
  name: string;
  survey_area_id: number;
  run_ids: number[];
  expectations: { version: string; coverage_mean: number };
  created_at: string;
};
type Finding = {
  id: number;
  kind: string;
  score: number;
  confidence: number;
  explanation: string;
  status: string;
  disposition_note: string | null;
  created_at: string;
};
function Baselines({ areas, runs }: { areas: Area[]; runs: Run[] }) {
  const [a, setA] = useState(""),
    [name, setName] = useState(""),
    [ids, setIds] = useState<number[]>([]),
    [items, setItems] = useState<Baseline[]>([]),
    [note, setNote] = useState("");
  async function load(area = a) {
    setItems(
      await api<Baseline[]>("/v1/baselines" + (area ? "?area_id=" + area : "")),
    );
  }
  useEffect(() => {
    load();
  }, []);
  const toggle = (id: number) =>
    setIds((x) => (x.includes(id) ? x.filter((y) => y !== id) : [...x, id]));
  async function create(e: FormEvent) {
    e.preventDefault();
    try {
      await send("/v1/baselines", {
        survey_area_id: Number(a),
        name,
        run_ids: ids,
      });
      setName("");
      setIds([]);
      setNote("Baseline frozen and findings evaluated.");
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  async function evaluate(id: number) {
    try {
      const x = await send<{ findings: number }>(
        "/v1/baselines/" + id + "/evaluate",
        {},
      );
      setNote("Evaluation complete: " + x.findings + " findings.");
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <div className="split">
      <section className="panel">
        <p className="eyebrow">FROZEN TRAINING SET</p>
        <h2>Create baseline</h2>
        <p className="muted">
          Select completed runs from one area. Later runs are compared against
          this frozen evidence.
        </p>
        <form onSubmit={create}>
          <select
            aria-label="Survey area"
            value={a}
            onChange={(x) => {
              setA(x.target.value);
              setIds([]);
            }}
            required
          >
            <option value="">Choose area</option>
            {areas.map((x) => (
              <option key={x.id} value={x.id}>
                {x.name}
              </option>
            ))}
          </select>
          <input
            value={name}
            onChange={(x) => setName(x.target.value)}
            placeholder="Baseline name"
            required
          />
          {runs
            .filter((x) => x.completed && String(x.survey_area_id) === a)
            .map((x) => (
              <label className="check" key={x.id}>
                <input
                  type="checkbox"
                  checked={ids.includes(x.id)}
                  onChange={() => toggle(x.id)}
                />
                {x.name} · {Math.round(x.collector_coverage * 100)}% coverage
              </label>
            ))}
          <button disabled={!ids.length}>Freeze baseline</button>
        </form>
        {note && <p className="notice">{note}</p>}
      </section>
      <section className="panel">
        <p className="eyebrow">BASELINE HISTORY</p>
        <h2>Frozen versions</h2>
        <div className="list">
          {items.map((x) => (
            <div key={x.id}>
              <b>{x.name}</b>
              <span>
                {x.run_ids.length} runs ·{" "}
                {Math.round(x.expectations.coverage_mean * 100)}% mean coverage
                · {x.expectations.version}
              </span>
              <button className="quiet" onClick={() => evaluate(x.id)}>
                Re-evaluate later runs
              </button>
            </div>
          ))}
          {!items.length && <p>Nothing yet.</p>}
        </div>
      </section>
    </div>
  );
}
function Anomalies({ areas }: { areas: Area[] }) {
  const [a, setA] = useState(""),
    [items, setItems] = useState<Finding[]>([]),
    [note, setNote] = useState(""),
    [drafts, setDrafts] = useState<Record<number, string>>({});
  async function load(area = a) {
    setItems(
      await api<Finding[]>("/v1/anomalies" + (area ? "?area_id=" + area : "")),
    );
  }
  useEffect(() => {
    load();
  }, []);
  async function disposition(id: number, status: string) {
    try {
      await api("/v1/anomalies/" + id, {
        method: "PATCH",
        body: JSON.stringify({ status, disposition_note: drafts[id] || null }),
        headers: { "Content-Type": "application/json" },
      });
      setNote("Finding updated.");
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">ANALYST REVIEW QUEUE</p>
          <h2>Explainable findings</h2>
          <p className="muted">
            Scores prioritize review; they are not security verdicts.
          </p>
        </div>
        <select
          aria-label="Survey area"
          value={a}
          onChange={(x) => {
            setA(x.target.value);
            load(x.target.value);
          }}
        >
          <option value="">All areas</option>
          {areas.map((x) => (
            <option key={x.id} value={x.id}>
              {x.name}
            </option>
          ))}
        </select>
      </div>
      {note && <p className="notice">{note}</p>}
      <div className="list">
        {items.map((x) => (
          <div key={x.id}>
            <b>
              {x.kind.replace("_", " ")} · score {Math.round(x.score * 100)} ·
              confidence {Math.round(x.confidence * 100)}%
            </b>
            <span>{x.explanation}</span>
            <span>Status: {x.status}</span>
            <label className="field-label compact-field">
              Review note or evidence reference
              <input
                value={drafts[x.id] ?? x.disposition_note ?? ""}
                onChange={(event) =>
                  setDrafts((current) => ({
                    ...current,
                    [x.id]: event.target.value,
                  }))
                }
                placeholder="Optional analyst context"
              />
            </label>
            <button
              className="quiet"
              onClick={() => disposition(x.id, "confirmed")}
            >
              Confirm
            </button>
            <button
              className="quiet"
              onClick={() => disposition(x.id, "dismissed")}
            >
              Dismiss
            </button>
            <button
              className="quiet"
              onClick={() => disposition(x.id, "needs_review")}
            >
              Needs review
            </button>
          </div>
        ))}
        {!items.length && <p>No findings for this selection.</p>}
      </div>
    </section>
  );
}
function OUIImportPanel() {
  const [status, setStatus] = useState<{
      assignments: number;
      latest: { registry_version: string; created_at: string } | null;
    } | null>(null),
    [note, setNote] = useState(""),
    [refreshing, setRefreshing] = useState(false);
  async function load() {
    setStatus(await api("/v1/oui/status"));
  }
  useEffect(() => {
    load();
  }, []);
  async function refresh() {
    setRefreshing(true);
    try {
      const x = await send<{ idempotent?: boolean; assignments: number }>(
        "/v1/oui/refresh",
        {},
      );
      setNote(
        (x.idempotent ? "Already up to date: " : "Refreshed from IEEE: ") +
          x.assignments +
          " assignments.",
      );
      load();
    } catch (x) {
      setNote(msg(x));
    } finally {
      setRefreshing(false);
    }
  }
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const file = new FormData(e.currentTarget).get("file");
    if (!(file instanceof File)) return;
    const body = new FormData();
    body.set("file", file);
    try {
      const response = await fetch("/v1/oui/import", {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(await response.text());
      const x = await response.json();
      setNote(
        (x.idempotent ? "Already imported: " : "Imported: ") +
          x.assignments +
          " assignments.",
      );
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <section className="panel">
      <p className="eyebrow">OFFLINE OUI CATALOG</p>
      <h2>IEEE MA-L enrichment</h2>
      <p className="muted">
        {status?.assignments?.toLocaleString() || 0} local assignments
        {status?.latest ? " · " + status.latest.registry_version : ""}
      </p>
      <div className="toolbar">
        <form onSubmit={upload}>
          <input name="file" type="file" accept=".csv" required />
          <button>Import IEEE CSV</button>
        </form>
        <button className="secondary" onClick={refresh} disabled={refreshing}>
          {refreshing ? "Fetching…" : "Refresh from IEEE"}
        </button>
      </div>
      <p className="muted">
        "Refresh from IEEE" has the server fetch the current registry
        directly from standards-oui.ieee.org over HTTPS — no file leaves
        or enters your browser.
      </p>
      {note && <p className="notice">{note}</p>}
    </section>
  );
}
type Account = {
  id: number;
  username: string;
  role: string;
  disabled: boolean;
  created_at: string;
};
function RetentionPanel() {
  const [p, setP] = useState<{
      raw_retention_days: number;
      normalized_retention_days: number;
      raw_uploads: { id: number; filename: string }[];
      survey_runs: { id: number; name: string }[];
    } | null>(null),
    [confirm, setConfirm] = useState(""),
    [note, setNote] = useState("");
  async function preview() {
    try {
      setP(await api("/v1/retention/preview"));
      setNote("Review the candidate list before confirming.");
    } catch (x) {
      setNote(msg(x));
    }
  }
  async function purge() {
    try {
      const x = await api<{
        expired_raw_uploads: number;
        purged_survey_runs: number[];
      }>("/v1/retention/purge", {
        method: "POST",
        body: JSON.stringify({ confirm }),
      });
      setNote(
        "Retention completed: " +
          x.expired_raw_uploads +
          " raw upload(s) expired; " +
          x.purged_survey_runs.length +
          " run(s) removed.",
      );
      setConfirm("");
      preview();
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <section className="panel">
      <p className="eyebrow">RETENTION CONTROL</p>
      <h2>Review before removal</h2>
      <p className="muted">
        Raw uploads: {p?.raw_retention_days ?? "…"} days · run evidence:{" "}
        {p?.normalized_retention_days ?? "…"} days. This never runs
        automatically.
      </p>
      <button className="quiet" onClick={preview}>
        Preview candidates
      </button>
      {p && (
        <div className="list">
          <p>
            <b>{p.raw_uploads.length}</b> raw upload(s) to expire ·{" "}
            <b>{p.survey_runs.length}</b> run(s) to purge
          </p>
          {p.raw_uploads.slice(0, 5).map((x) => (
            <span key={x.id}>Raw: {x.filename}</span>
          ))}
          {p.survey_runs.slice(0, 5).map((x) => (
            <span key={x.id}>Run: {x.name}</span>
          ))}
          {(p.raw_uploads.length > 5 || p.survey_runs.length > 5) && (
            <span>Only the first five of each are shown here.</span>
          )}
          <label className="field-label compact-field">
            Type PURGE to run the reviewed sweep
            <input
              value={confirm}
              onChange={(x) => setConfirm(x.target.value)}
              aria-label="Retention confirmation"
            />
          </label>
          <button disabled={confirm !== "PURGE"} onClick={purge}>
            Purge reviewed candidates
          </button>
        </div>
      )}
      {note && <p className="notice">{note}</p>}
    </section>
  );
}
function CollectionsPanel() {
  const [areas, setAreas] = useState<Area[]>([]),
    [note, setNote] = useState("");
  async function load() {
    setAreas(await api<Area[]>("/v1/survey-areas"));
  }
  useEffect(() => {
    load();
  }, []);
  async function rename(e: FormEvent<HTMLFormElement>, id: number) {
    e.preventDefault();
    const name = new FormData(e.currentTarget).get("name");
    try {
      await api("/v1/survey-areas/" + id, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      setNote("Renamed.");
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <section className="panel">
      <p className="eyebrow">COLLECTION MANAGEMENT</p>
      <h2>Collections</h2>
      <p className="muted">
        Created from the Surveys page when importing. Rename one here; its
        precision (coarse vs. exact) is set at creation and not editable.
      </p>
      <div className="list">
        {areas.map((x) => (
          <div key={x.id}>
            <form className="inline-form" onSubmit={(e) => rename(e, x.id)}>
              <input name="name" defaultValue={x.name} required />
              <button className="quiet">Rename</button>
            </form>
            <span>
              {x.precision} · {(x.run_count ?? 0).toLocaleString()} runs ·{" "}
              {(x.device_count ?? 0).toLocaleString()} devices
            </span>
          </div>
        ))}
        {!areas.length && <p>No collections yet.</p>}
      </div>
      {note && <p className="notice">{note}</p>}
    </section>
  );
}
function Access({ me }: { me: Me }) {
  const [u, setU] = useState<Account[]>([]),
    [note, setNote] = useState("");
  async function load() {
    setU(await api<Account[]>("/v1/users"));
  }
  useEffect(() => {
    if (me.role === "admin") load();
  }, [me.role]);
  if (me.role !== "admin")
    return (
      <section className="panel">
        <h2>Access</h2>
        <p>Only administrators manage users.</p>
      </section>
    );
  async function add(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    try {
      await send(
        "/v1/users",
        Object.fromEntries(new FormData(e.currentTarget)),
      );
      e.currentTarget.reset();
      setNote("Account created.");
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  async function change(account: Account) {
    const disabling = !account.disabled;
    if (
      disabling &&
      !window.confirm(
        "Disable " + account.username + " and revoke their sessions?",
      )
    )
      return;
    try {
      await api("/v1/users/" + account.id, {
        method: "PATCH",
        body: JSON.stringify({ disabled: disabling }),
      });
      setNote(account.username + (disabling ? " disabled." : " enabled."));
      load();
    } catch (x) {
      setNote(msg(x));
    }
  }
  async function revoke(account: Account) {
    if (!window.confirm("Revoke every session for " + account.username + "?"))
      return;
    try {
      const x = await api<{ revoked: number }>(
        "/v1/users/" + account.id + "/sessions",
        { method: "DELETE" },
      );
      setNote(
        "Revoked " + x.revoked + " session(s) for " + account.username + ".",
      );
    } catch (x) {
      setNote(msg(x));
    }
  }
  return (
    <div className="split">
      <section className="panel">
        <p className="eyebrow">USER MANAGEMENT</p>
        <h2>Create user</h2>
        <form onSubmit={add}>
          <label className="field-label">
            Username
            <input name="username" placeholder="Username" required />
          </label>
          <label className="field-label">
            Temporary password
            <input
              name="password"
              type="password"
              placeholder="Temporary password"
              minLength={10}
              required
            />
          </label>
          <select aria-label="Account role" name="role">
            <option value="viewer">Viewer</option>
            <option value="analyst">Analyst</option>
            <option value="auditor">Auditor</option>
            <option value="admin">Admin</option>
          </select>
          <button>Create user</button>
        </form>
        {note && <p className="notice">{note}</p>}
      </section>
      <section className="panel">
        <p className="eyebrow">CURRENT ACCESS</p>
        <h2>Accounts</h2>
        <div className="list">
          {u.map((x) => (
            <div key={x.id}>
              <b>
                {x.username} · {x.role}
                {x.disabled ? " · disabled" : ""}
              </b>
              <button className="quiet" onClick={() => change(x)}>
                {x.disabled ? "Enable" : "Disable"}
              </button>
              <button className="quiet" onClick={() => revoke(x)}>
                Revoke sessions
              </button>
            </div>
          ))}
          {!u.length && <p>Nothing yet.</p>}
        </div>
      </section>
      <OUIImportPanel />
      <RetentionPanel />
      <CollectionsPanel />
    </div>
  );
}
function List({ rows }: { rows: string[] }) {
  return (
    <div className="list">
      {rows.length ? rows.map((x) => <p key={x}>{x}</p>) : <p>Nothing yet.</p>}
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
