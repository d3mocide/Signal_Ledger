import { Component, FormEvent, ReactNode, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { api, ApiError, Area, Me, Overview, Run, send } from "./api";
import "./style.css";
type Page =
  | "overview"
  | "surveys"
  | "collections"
  | "inventory"
  | "categories"
  | "vendors"
  | "coverage"
  | "device"
  | "baselines"
  | "anomalies"
  | "reviews"
  | "learning"
  | "comparison"
  | "access"
  | "audit";
const routePages = new Set<Page>(["overview", "surveys", "collections", "inventory", "categories", "vendors", "coverage", "device", "baselines", "anomalies", "reviews", "learning", "comparison", "access", "audit"]);
const pageFromHash = (): Page | null => {
  const value = window.location.hash.replace(/^#/, "").split("?")[0] as Page;
  return value && routePages.has(value) ? value : value ? null : "overview";
};
const deviceIdFromHash = (): number | null => {
  const query = window.location.hash.split("?")[1];
  const value = query ? Number(new URLSearchParams(query).get("id")) : NaN;
  return Number.isInteger(value) && value > 0 ? value : null;
};
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
  category_confidence?: number;
  category_evidence?: string[];
  category_scores?: Record<string, number>;
  category_rule_version?: string;
  category_overridden?: boolean;
  device_roles?: string[];
  role_scores?: Record<string, number>;
  role_evidence?: string[];
  role_rule_version?: string;
  first_seen: string;
  last_seen: string;
  last_protocol?: string | null;
  last_ssid?: string | null;
  last_device_name?: string | null;
  last_device_type?: string | null;
  has_stored_address?: boolean;
};
type DeviceDetail = {
  device: Device;
  summary: { observations: number; runs: number; coarse_cells: number };
  collections: string[];
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
    page: "categories",
    label: "Category view",
    icon: "categories",
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
    label: "Finding queue",
    icon: "anomalies",
    group: "ANALYSIS",
  },
  {
    page: "reviews",
    label: "Evidence review",
    icon: "anomalies",
    group: "",
  },
  { page: "learning", label: "Rule learning", icon: "categories", group: "" },
  { page: "comparison", label: "Run comparison", icon: "baselines", group: "" },
  { page: "baselines", label: "Baselines", icon: "baselines", group: "" },
  {
    page: "surveys",
    label: "Capture imports",
    icon: "surveys",
    group: "COLLECTION",
  },
  {
    page: "collections",
    label: "Collections",
    icon: "collections",
    group: "",
  },
  { page: "access", label: "Administration", icon: "access", group: "" },
  { page: "audit", label: "Audit log", icon: "audit", group: "GOVERNANCE" },
];
const descriptions: Record<Page, string> = {
  overview: "Your discovery landscape, at a glance.",
  inventory: "Explore site-scoped devices and the evidence behind them.",
  categories: "See transparent device-category hypotheses and review coverage.",
  vendors: "See your device inventory grouped and ranked by OUI manufacturer.",
  coverage: "Understand where your collection has observed signals.",
  anomalies: "Review changes against your established baselines.",
  reviews: "Review uncertain device classifications and teach the evidence model.",
  learning: "Review analyst feedback and measure where classification rules need attention.",
  comparison: "Compare completed capture runs without exposing raw device addresses.",
  baselines: "Define expected behavior from completed survey runs.",
  surveys: "Drop a capture to create an import session, or organize sessions when useful.",
  collections: "Create, rename, and review the collections used to group captures.",
  access: "Manage workspace access and local enrichment.",
  audit: "Review the operator actions recorded for this private workspace.",
  device: "Trace an observed device back to its source evidence.",
};
function Icon({ name }: { name: string }) {
  const paths: Record<string, string> = {
    overview: "M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z",
    inventory: "M4 5h16v14H4z M8 9h8 M8 13h5",
    categories: "M4 5h6v6H4z M14 5h6v6h-6z M4 15h6v4H4z M14 15h6v4h-6z",
    vendors: "M4 6h13 M4 12h17 M4 18h9",
    collections: "M3 7h6l2 2h10v10H3z",
    coverage:
      "M12 3v3 M12 18v3 M3 12h3 M18 12h3 M19 12a7 7 0 1 1-14 0 7 7 0 0 1 14 0 M14 12a2 2 0 1 1-4 0 2 2 0 0 1 4 0",
    anomalies: "M12 3 2 20h20L12 3z M12 9v5 M12 17v.1",
    baselines: "M3 17h18 M5 13V8 M10 13V4 M15 13v-3 M20 13V6",
    surveys: "M12 16V3 M7 8l5-5 5 5 M4 14v6h16v-6",
    access: "M12 3 3 7v5c0 5 9 9 9 9s9-4 9-9V7l-9-4z M8 12l3 3 5-6",
    audit: "M5 4h14v16H5z M8 8h8 M8 12h8 M8 16h5",
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
    [page, setPage] = useState<Page>(() => pageFromHash() || "overview"),
    [o, setO] = useState<Overview | null>(null),
    [areas, setAreas] = useState<Area[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [jobs, setJobs] = useState<Job[]>([]),
    [mapDevice, setMapDevice] = useState(""),
    [vendorFilter, setVendorFilter] = useState(""),
    [categoryFilter, setCategoryFilter] = useState(""),
    [roleFilter, setRoleFilter] = useState(""),
    [deviceId, setDeviceId] = useState<number | null>(() => deviceIdFromHash()),
    [note, setNote] = useState(""),
    [loading, setLoading] = useState(true),
    [refresh, setRefresh] = useState(0),
    [updated, setUpdated] = useState(""),
    [importing, setImporting] = useState<string | null>(null);
  const navigate = (next: Page, params: Record<string, string> = {}) => {
    const query = new URLSearchParams(params).toString();
    const hash = `#${next}${query ? "?" + query : ""}`;
    if (window.location.hash !== hash) window.history.pushState({}, "", hash);
    setPage(next);
  };
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
    const syncPage = () => {
      const next = pageFromHash();
      if (next) {
        setPage(next);
        setDeviceId(deviceIdFromHash());
      }
    };
    window.addEventListener("popstate", syncPage);
    window.addEventListener("hashchange", syncPage);
    return () => {
      window.removeEventListener("popstate", syncPage);
      window.removeEventListener("hashchange", syncPage);
    };
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
          href="#overview"
          onClick={(e) => {
            e.preventDefault();
            navigate("overview");
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
            .filter((x) =>
              x.page === "access"
                ? true
                : x.page === "audit"
                  ? ["auditor", "analyst", "admin"].includes(me.role)
                  : true,
            )
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
                    navigate(x.page);
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
              <button onClick={() => navigate("surveys")}>
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
          {importing && (
            <div className="progress-toast" role="status">
              <div className="progress-toast-bar">
                <span />
              </div>
              <div>
                <b>Importing {importing}…</b>
                <small>
                  Large files can take a couple of minutes. You can keep
                  working elsewhere in the meantime.
                </small>
              </div>
            </div>
          )}
          <WorkspaceBoundary key={page + refresh}>
            {page === "overview" && (
              <Dashboard overview={o} jobs={jobs} runs={runs} go={navigate} />
            )}{" "}
            {page === "surveys" && (
              <Surveys
                areas={areas}
                runs={runs}
                reload={load}
                say={setNote}
                role={me.role}
                setImporting={setImporting}
              />
            )}{" "}
            {page === "collections" && (
              <CollectionsPage role={me.role} reload={load} say={setNote} />
            )}{" "}
            {page === "inventory" && (
              <Inventory
                areas={areas}
                showDevice={(x) => {
                  setDeviceId(x);
                  navigate("device", { id: String(x) });
                }}
                mapDevice={(x) => {
                  setMapDevice(String(x));
                  navigate("coverage");
                }}
                initialVendor={vendorFilter}
                initialCategory={categoryFilter}
                initialRole={roleFilter}
              />
            )}{" "}
            {page === "categories" && (
              <CategoryOverview
                areas={areas}
                role={me.role}
                showCategory={(category) => {
                  setCategoryFilter(category);
                  setVendorFilter("");
                  setRoleFilter("");
                  navigate("inventory");
                }}
                showRole={(nextRole) => {
                  setRoleFilter(nextRole);
                  setCategoryFilter("");
                  setVendorFilter("");
                  navigate("inventory");
                }}
              />
            )}{" "}
            {page === "vendors" && (
              <VendorBreakdown
                areas={areas}
                showVendor={(vendor) => {
                  setVendorFilter(vendor);
                  navigate("inventory");
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
                back={() => navigate("inventory")}
                mapDevice={(x) => {
                  setMapDevice(String(x));
                  navigate("coverage");
                }}
                role={me.role}
              />
            )}{" "}
            {page === "baselines" && <Baselines areas={areas} runs={runs} />}{" "}
            {page === "anomalies" && <Anomalies areas={areas} />}{" "}
            {page === "reviews" && (
              <DeviceReviews
                areas={areas}
                role={me.role}
                showDevice={(x) => {
                  setDeviceId(x);
                  navigate("device", { id: String(x) });
                }}
              />
            )}{" "}
            {page === "learning" && <RuleLearning areas={areas} role={me.role} />}
            {page === "comparison" && <RunComparison runs={runs} />}
            {page === "access" && <Access me={me} />}
            {page === "audit" && <AuditEvents />}
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
      <div className="dashboard-columns">
        <div className="dashboard-column wide">
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
        </div>
        <div className="dashboard-column narrow">
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
        </div>
      </div>
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
  );
}
function Surveys({
  areas,
  runs,
  reload,
  say,
  role,
  setImporting,
}: {
  areas: Area[];
  runs: Run[];
  reload: () => void;
  say: (x: string) => void;
  role: string;
  setImporting: (x: string | null) => void;
}) {
  const [busy, setBusy] = useState(false),
    [uploadTarget, setUploadTarget] = useState(""),
    [uploadNewCollectionName, setUploadNewCollectionName] = useState("");
  async function quickUpload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const body = new FormData(form);
    const file = body.get("file");
    if (!(file instanceof File)) return;
    const collectionName =
      uploadTarget === "__new__"
        ? uploadNewCollectionName.trim()
        : uploadTarget;
    if (collectionName) body.set("collection_name", collectionName);
    setBusy(true);
    setImporting(file.name);
    try {
      const response = await fetch("/v1/imports", {
        method: "POST",
        body,
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(await response.text());
      const job = await response.json();
      form.reset();
      setUploadTarget("");
      setUploadNewCollectionName("");
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
      setImporting(null);
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
  async function deleteRun(run: Run) {
    if (
      !window.confirm(
        "Permanently delete \"" +
          run.name +
          "\" and all of its observations and orphaned devices? This cannot be undone.",
      )
    )
      return;
    try {
      await api("/v1/survey-runs/" + run.id, { method: "DELETE" });
      say("Deleted " + run.name + ".");
      setSelected((current) => {
        const next = new Set(current);
        next.delete(run.id);
        return next;
      });
      reload();
    } catch (error) {
      say(msg(error));
    }
  }
  return (
    <div className="capture-flow">
      <section className="panel capture-drop">
        <p className="eyebrow">NEW CAPTURE</p>
        <h2>Drop a WiGLE or Kismet log</h2>
        <p className="muted">Signal Ledger names the import session from the filename and time. Naming and filing into a collection are both optional.</p>
        <form onSubmit={quickUpload}>
          <select aria-label="Source format" name="source_format">
            <option value="wigle">WiGLE CSV</option>
            <option value="kismet">Kismet database / CSV / JSON</option>
          </select>
          <label className="file-drop">
            Source log<span>Choose a WiGLE or Kismet file</span>
            <input name="file" type="file" accept=".csv,.json,.ndjson,.kismet" required />
          </label>
          <label className="field-label">
            Session name (optional)
            <input name="session_name" placeholder="Defaults to the filename" />
          </label>
          <label className="field-label">
            Collection (optional)
            <select
              aria-label="Collection"
              value={uploadTarget}
              onChange={(x) => setUploadTarget(x.target.value)}
            >
              <option value="">Leave unfiled</option>
              {areas.map((x) => (
                <option key={x.id} value={x.name}>
                  {x.name}
                </option>
              ))}
              <option value="__new__">+ New collection…</option>
            </select>
          </label>
          {uploadTarget === "__new__" && (
            <input
              value={uploadNewCollectionName}
              onChange={(x) => setUploadNewCollectionName(x.target.value)}
              placeholder="New collection name"
            />
          )}
          <button disabled={busy}>{busy ? "Importing…" : "Import capture"}</button>
        </form>
        <p className="muted">
          A collection created here defaults to coarse precision. For an
          exact-precision collection, create it first on the Collections
          page.
        </p>
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
              <span>{collectionNames.get(run.collection_id) || "Unfiled"} · {run.completed ? "Imported" : "Processing"}</span>
              {role === "admin" && (
                <button className="quiet" onClick={() => deleteRun(run)}>
                  Delete
                </button>
              )}
            </div>
          ))}
          {!runs.length && <p>No captures yet. Import a log to begin.</p>}
        </div>
      </section>
    </div>
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
    unattributable = rows.find((x) => x.oui_organization === "unattributable"),
    attributed = rows.filter((x) => x.oui_organization !== "unattributable"),
    attributedTotal = attributed.reduce((sum, x) => sum + x.device_count, 0),
    top = attributed.slice(0, 15),
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
            {unattributable
              ? " · " + unattributable.device_count.toLocaleString() + " unattributable"
              : ""}
            {top.length < attributed.length
              ? " · top " + top.length + " attributed vendors charted below"
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
            <p className="muted">No attributed vendors matched.</p>
          )}
        </div>
        <aside>
          <h3>Leading attributed vendor</h3>
          {top[0] ? (
            <p>
              <b>{top[0].oui_organization}</b>
              <br />
              {Math.round((top[0].device_count / attributedTotal) * 100)}% of
              attributed devices
            </p>
          ) : (
            <p className="muted">No attributed devices yet.</p>
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
type CategoryRow = {
  category: string;
  device_count: number;
  share: number;
  mean_confidence: number;
  override_count: number;
};
type RoleRow = { role: string; device_count: number; share: number; mean_score: number; top_evidence: string[] };
type RoleSummary = { roles: RoleRow[]; total_devices: number; role_tagged_devices: number; role_assignments: number; overlap_devices: number };
function CategoryOverview({ areas, role, showCategory, showRole }: { areas: Area[]; role: string; showCategory: (category: string) => void; showRole: (role: string) => void }) {
  const [area, setArea] = useState(""), [rows, setRows] = useState<CategoryRow[]>([]), [roleRows, setRoleRows] = useState<RoleSummary>({ roles: [], total_devices: 0, role_tagged_devices: 0, role_assignments: 0, overlap_devices: 0 }), [loading, setLoading] = useState(false), [error, setError] = useState(""), [rebuilding, setRebuilding] = useState(false), [note, setNote] = useState("");
  async function load(nextArea = area) {
    setLoading(true); setError("");
    try {
      const suffix = nextArea ? "?area_id=" + nextArea : "";
      const [categories, roles] = await Promise.all([api<CategoryRow[]>("/v1/devices/categories" + suffix), api<RoleSummary>("/v1/devices/roles" + suffix)]);
      setRows(categories);
      setRoleRows(roles);
    } catch (x) { setError(msg(x)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  async function rebuild() {
    setRebuilding(true); setNote("");
    try {
      const result = await api<{ updated: number; overridden_skipped: number; rule_version: string }>("/v1/devices/categories/rebuild", { method: "POST" });
      setNote("Rebuilt " + result.updated.toLocaleString() + " device hypotheses with " + result.rule_version + "; skipped " + result.overridden_skipped.toLocaleString() + " analyst override(s).");
      load();
    } catch (x) { setError(msg(x)); }
    finally { setRebuilding(false); }
  }
  const total = rows.reduce((sum, row) => sum + row.device_count, 0);
  const known = rows.filter((row) => row.category !== "unknown").reduce((sum, row) => sum + row.device_count, 0);
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">DEVICE TAXONOMY</p>
          <h2>Category hypotheses</h2>
          <p className="muted">Rules combine vendor, SSID, and protocol evidence. These are review aids, not identity or security conclusions.</p>
        </div>
        <select aria-label="Category collection" value={area} onChange={(event) => { setArea(event.target.value); load(event.target.value); }}>
          <option value="">All collections</option>
          {areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        {(role === "analyst" || role === "admin") && <button className="secondary" onClick={rebuild} disabled={rebuilding}>{rebuilding ? "Rebuilding…" : "Rebuild hypotheses"}</button>}
      </div>
      {error && <p className="warning" role="alert">{error}</p>}
      {note && <p className="notice" role="status">{note}</p>}
      <div className="category-summary taxonomy-summary">
        <div><b>{total.toLocaleString()}</b><span>devices in scope</span></div>
        <div><b>{known.toLocaleString()}</b><span>with a rule match</span></div>
        <div><b>{total ? Math.round((known / total) * 100) : 0}%</b><span>categorized coverage</span></div>
        <div><b>{roleRows.role_tagged_devices.toLocaleString()}</b><span>with a role/context tag</span></div>
        <div><b>{roleRows.overlap_devices.toLocaleString()}</b><span>role overlaps to review</span></div>
      </div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Category</th><th>Devices</th><th>Share</th><th>Mean confidence</th><th>Overrides</th><th></th></tr></thead>
          <tbody>{rows.map((row) => (
            <tr key={row.category}>
              <td><span className="category-chip">{row.category}</span></td>
              <td>{row.device_count.toLocaleString()}</td>
              <td>{(row.share * 100).toFixed(1)}%</td>
              <td>{Math.round(row.mean_confidence * 100)}%</td>
              <td>{row.override_count.toLocaleString()}</td>
              <td><button className="quiet map-action" onClick={() => showCategory(row.category)}>View inventory</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      <div className="taxonomy-subhead"><div><p className="eyebrow">OPERATIONAL CONTEXT</p><h3>Roles and context</h3><p className="muted">Role assignments can overlap; shares are measured against devices in scope.</p></div><span className="muted">{roleRows.role_assignments.toLocaleString()} assignments · {roleRows.role_tagged_devices.toLocaleString()} devices</span></div>
      <div className="table-scroll">
        <table>
          <thead><tr><th>Role / context</th><th>Devices</th><th>Share of scope</th><th>Mean evidence score</th><th>Top evidence</th><th></th></tr></thead>
          <tbody>{roleRows.roles.map((row) => (
            <tr key={row.role}>
              <td><span className="role-chip">{row.role.replaceAll("_", " ")}</span></td>
              <td>{row.device_count.toLocaleString()}</td>
              <td>{(row.share * 100).toFixed(1)}%</td>
              <td>{row.mean_score.toFixed(2)}</td>
              <td className="taxonomy-evidence">{row.top_evidence.length ? row.top_evidence.join(" · ") : "—"}</td>
              <td><button className="quiet map-action" onClick={() => showRole(row.role)}>View inventory</button></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {!roleRows.roles.length && !loading && <p className="muted">No role/context signals have been retained yet.</p>}
      {!rows.length && !loading && <p className="muted">No devices have been imported yet.</p>}
      <p className="muted category-footnote">Rule set: rules-v6. Unknown means no configured signal cleared the evidence threshold. Open a device record to inspect evidence or apply an audited analyst override.</p>
    </section>
  );
}
function Inventory({
  areas,
  showDevice,
  mapDevice,
  initialVendor,
  initialCategory,
  initialRole,
}: {
  areas: Area[];
  showDevice: (id: number) => void;
  mapDevice: (id: number) => void;
  initialVendor: string;
  initialCategory: string;
  initialRole: string;
}) {
  const [a, setA] = useState(""),
    [v, setV] = useState(initialVendor),
    [c, setC] = useState(initialCategory),
    [role, setRole] = useState(initialRole),
    [attributedOnly, setAttributedOnly] = useState(false),
    [sort, setSort] = useState("last_seen"),
    [direction, setDirection] = useState<"asc" | "desc">("desc"),
    [d, setD] = useState<Device[]>([]),
    [total, setTotal] = useState(0),
    [offset, setOffset] = useState(0),
    [loading, setLoading] = useState(false),
    [vendorOptions, setVendorOptions] = useState<string[]>([]),
    [savedViews, setSavedViews] = useState<SavedFilter[]>([]),
    [viewName, setViewName] = useState("");
  const limit = 50;
  async function load(
    next = offset,
    nextSort = sort,
    nextDirection = direction,
    nextAttributedOnly = attributedOnly,
    nextVendor = v,
    nextCategory = c,
    nextRole = role,
    nextArea = a,
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
      if (nextArea) q.set("area_id", nextArea);
      if (nextCategory) q.set("category", nextCategory);
      if (nextRole) q.set("role", nextRole);
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
  useEffect(() => {
    if (initialCategory) {
      setC(initialCategory);
      load(0, sort, direction, attributedOnly, v, initialCategory);
    }
  }, [initialCategory]);
  useEffect(() => {
    if (initialRole) {
      setRole(initialRole);
      load(0, sort, direction, attributedOnly, v, c, initialRole);
    }
  }, [initialRole]);
  useEffect(() => {
    api<{ oui_organization: string }[]>("/v1/devices/vendors").then((rows) =>
      setVendorOptions(rows.map((x) => x.oui_organization)),
    );
  }, []);
  useEffect(() => {
    api<SavedFilter[]>("/v1/saved-filters").then((items) => setSavedViews(items.filter((item) => item.resource === "inventory"))).catch(() => undefined);
  }, []);
  async function saveView() {
    if (!viewName.trim()) return;
    try {
      const saved = await send<SavedFilter>("/v1/saved-filters", { name: viewName.trim(), resource: "inventory", filters: { area_id: a, vendor: v, category: c, role, attributed_only: String(attributedOnly), sort, direction } });
      setSavedViews((items) => [saved, ...items]); setViewName("");
    } catch { /* the inventory remains usable if saving is unavailable */ }
  }
  function applySavedView(item: SavedFilter) {
    const filters = item.filters || {};
    const nextArea = filters.area_id || "", nextVendor = filters.vendor || "", nextCategory = filters.category || "", nextRole = filters.role || "", nextAttributed = filters.attributed_only === "true";
    setA(nextArea); setV(nextVendor); setC(nextCategory); setRole(nextRole); setAttributedOnly(nextAttributed); setSort(filters.sort || "last_seen"); setDirection((filters.direction as "asc" | "desc") || "desc");
    load(0, filters.sort || "last_seen", (filters.direction as "asc" | "desc") || "desc", nextAttributed, nextVendor, nextCategory, nextRole, nextArea);
  }
  const exportQuery = new URLSearchParams({ limit: "5000", vendor: v, category: c, role, attributed_only: String(attributedOnly) });
  if (a) exportQuery.set("area_id", a);
  const exportHref = "/v1/exports/devices.csv?" + exportQuery.toString();
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
    <section className="panel inventory-panel">
      <div className="inventory-header">
        <div>
          <p className="eyebrow">PSEUDONYMOUS INVENTORY</p>
          <h2>Devices from imported runs</h2>
          <p className="muted inventory-description">
            Review device hypotheses and the latest observed network evidence.
          </p>
        </div>
        <label className="inventory-scope">
          <span>Scope</span>
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
        </label>
      </div>
      <form
        className="inventory-filters"
        onSubmit={(event) => {
          event.preventDefault();
          load(0);
        }}
      >
        <label className="inventory-field">
          <span>Vendor evidence</span>
          <input
            value={v}
            onChange={(x) => setV(x.target.value)}
            placeholder="Search OUI organization"
            list="inventory-vendor-options"
          />
        </label>
        <datalist id="inventory-vendor-options">
          {vendorOptions.map((x) => (
            <option key={x} value={x} />
          ))}
        </datalist>
        <label className="inventory-field">
          <span>Category hypothesis</span>
          <select aria-label="Device category" value={c} onChange={(event) => setC(event.target.value)}>
            <option value="">All categories</option>
            {['unknown', 'camera', 'printer', 'network', 'mobile', 'iot', 'bluetooth', 'workstation', 'audio', 'entertainment', 'wearable', 'automotive'].map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label className="inventory-field">
          <span>Role or context</span>
          <select aria-label="Device role or context" value={role} onChange={(event) => setRole(event.target.value)}>
            <option value="">All roles</option>
            {['retail_pos', 'security_access', 'smart_home', 'industrial_ot', 'medical', 'guest_network'].map((item) => <option key={item} value={item}>{item.replaceAll('_', ' ')}</option>)}
          </select>
        </label>
        <label className="inventory-toggle">
          <input
            type="checkbox"
            checked={attributedOnly}
            onChange={(x) => {
              setAttributedOnly(x.target.checked);
            }}
          />
          <span>Attributed only</span>
        </label>
        <div className="inventory-filter-actions">
          <button type="submit">Apply filters</button>
          <button
            type="button"
            className="quiet"
            onClick={() => {
              setV("");
              setC("");
              setRole("");
              setAttributedOnly(false);
              load(0, sort, direction, false, "", "", "");
            }}
          >
            Clear
          </button>
        </div>
      </form>
      <div className="saved-filter-bar inventory-saved-views"><select aria-label="Saved inventory view" defaultValue="" onChange={(event) => { const item = savedViews.find((candidate) => String(candidate.id) === event.target.value); if (item) applySavedView(item); }}><option value="">Saved inventory views</option>{savedViews.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><input aria-label="Saved inventory view name" value={viewName} onChange={(event) => setViewName(event.target.value)} placeholder="Name current view" /><button className="secondary" type="button" onClick={saveView} disabled={!viewName.trim()}>Save view</button><a className="secondary" href={exportHref}>Export CSV</a></div>
      <div className="inventory-summary">
        <p className="muted">
          {total.toLocaleString()} matching devices · showing{" "}
          {total ? offset + 1 : 0}–{Math.min(offset + limit, total)}
        </p>
        <span className="inventory-sort">
          Sorted by {sort === "last_seen" ? "last seen" : sort.replaceAll("_", " ")} {direction === "desc" ? "newest first" : "oldest first"}
        </span>
      </div>
      <div className="table-scroll">
        <table className="inventory-table">
          <thead>
            <tr>
              <th>Device</th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("category")}
                >
                  Category{sortIndicator("category")}
                </button>
              </th>
              <th>Role / context</th>
              <th>
                <button
                  className="sort-header"
                  onClick={() => toggleSort("oui_organization")}
                >
                  Vendor evidence{sortIndicator("oui_organization")}
                </button>
              </th>
              <th>Last radio</th>
              <th>Last network</th>
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
                <td className="device-identity">
                  <button
                    className="token-button"
                    onClick={() => showDevice(x.id)}
                  >
                    <code>{x.token.slice(0, 14)}…</code>
                  </button>
                  <small>site token</small>
                </td>
                <td className="category-cell">
                  <span className="category-chip">{x.category}</span>
                  <small>{x.category_confidence ? `${Math.round(x.category_confidence * 100)}% confidence` : "No hypothesis"}</small>
                </td>
                <td className="role-cell">
                  {x.device_roles?.length ? x.device_roles.map((item) => <span className="role-chip" key={item}>{item.replaceAll("_", " ")}</span>) : <small>No role signal</small>}
                </td>
                <td className="vendor-cell">
                  <span>{x.oui_organization}</span>
                  <small>OUI evidence</small>
                </td>
                <td>{x.last_protocol ? <span className="protocol-pill">{x.last_protocol}</span> : "—"}</td>
                <td className="network-cell">
                  <span>{x.last_device_name || x.last_ssid || "No name observed"}</span>
                  <small>{x.last_ssid ? `SSID · ${x.last_ssid}` : x.last_device_type || "No network name"}</small>
                </td>
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
type SavedFilter = { id: number; name: string; resource: string; filters: Record<string, string> };
type DeviceFingerprint = { summary: { fingerprint_version: string; fingerprint: string; signal_counts: Record<string, number>; activity_windows: string[]; coarse_cell_count: number }; similar: { device_id: number; token_prefix: string; category: string; oui_organization: string; score: number; shared_signals: string[] }[]; disclaimer: string };
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
    [revealError, setRevealError] = useState(""),
    [category, setCategory] = useState(""),
    [categoryNote, setCategoryNote] = useState(""),
    [fingerprint, setFingerprint] = useState<DeviceFingerprint | null>(null);
  useEffect(() => {
    setD(null);
    setAddress("");
    setRevealError("");
    setFingerprint(null);
    api<DeviceDetail>("/v1/devices/" + id)
      .then(setD)
      .catch((x) => setError(msg(x)));
    api<DeviceFingerprint>("/v1/devices/" + id + "/fingerprint")
      .then(setFingerprint)
      .catch(() => undefined);
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
  async function overrideCategory() {
    try {
      const updated = await api<Device>("/v1/devices/" + id + "/category", {
        method: "PATCH",
        body: JSON.stringify({ category }),
      });
      setD((current) => (current ? { ...current, device: updated } : current));
      setCategoryNote("Category override saved and audited.");
    } catch (x) {
      setCategoryNote(msg(x));
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
  const currentCategory = category || x.category;
  const collectionName = d.collections.length ? d.collections.join(", ") : "Unfiled";
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
        {x.category} · {Math.round((x.category_confidence || 0) * 100)}% confidence
        {x.category_overridden ? " · analyst override" : ""}
      </p>
      <p className="muted device-roles-line">
        Roles / context: {x.device_roles?.length ? x.device_roles.map((item) => item.replaceAll("_", " ")).join(", ") : "No role signal"}
      </p>
      <div className="category-review">
        <label className="field-label">
          Review category
          <select value={currentCategory} onChange={(event) => setCategory(event.target.value)}>
            {['unknown', 'camera', 'printer', 'network', 'mobile', 'iot', 'bluetooth', 'workstation', 'audio', 'entertainment', 'wearable', 'automotive'].map((item) => (
              <option key={item} value={item}>{item}</option>
            ))}
          </select>
        </label>
        {(role === "analyst" || role === "admin") && (
          <button className="secondary" onClick={overrideCategory}>Save category override</button>
        )}
        {categoryNote && <span className="muted">{categoryNote}</span>}
      </div>
      {!!x.category_evidence?.length && (
        <div className="category-evidence">
          <p className="muted">Rule set: {x.category_rule_version || "rules-v1"} · Evidence is derived from retained vendor, SSID, and protocol facts.</p>
          <p className="muted">Rule evidence: {x.category_evidence.join(" · ")}</p>
          {!!x.category_scores && <div className="score-list">{Object.entries(x.category_scores).sort(([, left], [, right]) => right - left).slice(0, 5).map(([name, score]) => <span key={name}>{name} <b>{score.toFixed(2)}</b></span>)}</div>}
        </div>
      )}
      {!!x.role_evidence?.length && (
        <div className="category-evidence">
          <p className="muted">Role rules: {x.role_rule_version || "roles-v1"} · Role evidence is derived from retained vendor, SSID, and device name/type facts.</p>
          <p className="muted">Role evidence: {x.role_evidence.join(" · ")}</p>
          {!!x.role_scores && <div className="score-list">{Object.entries(x.role_scores).sort(([, left], [, right]) => right - left).slice(0, 6).map(([name, score]) => <span key={name}>{name.replaceAll("_", " ")} <b>{score.toFixed(2)}</b></span>)}</div>}
        </div>
      )}
      <p className="muted">
        First seen: {new Date(x.first_seen).toLocaleString()} · Last seen:{" "}
        {new Date(x.last_seen).toLocaleString()} · Collection:{" "}
        {collectionName}
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
      {role === "admin" && !x.has_stored_address && (
        <p className="muted">
          No address on file — this device was only captured under
          coarse-precision collections.
        </p>
      )}
      {revealError && <p className="warning">{revealError}</p>}
      {fingerprint && <div className="category-evidence fingerprint-panel"><p className="eyebrow">PRIVACY-SAFE SIMILARITY</p><h3>Related signal profiles</h3><p className="muted">{fingerprint.disclaimer}</p><p className="muted">Fingerprint {fingerprint.summary.fingerprint.slice(0, 12)}… · {fingerprint.summary.fingerprint_version} · {fingerprint.summary.coarse_cell_count} coarse cells · activity windows {fingerprint.summary.activity_windows.join(", ") || "none"}</p>{fingerprint.similar.length ? <div className="list">{fingerprint.similar.map((item) => <div key={item.device_id}><b><code>{item.token_prefix}</code></b><span>{item.category} · {item.oui_organization} · {Math.round(item.score * 100)}% similarity</span><small>{item.shared_signals.join(" · ")}</small></div>)}</div> : <p className="muted">No sufficiently similar profiles found in the bounded candidate set.</p>}</div>}
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
  const canvasRef = useRef<HTMLDivElement>(null),
    [measured, setMeasured] = useState({ width: 1120, height: 460 });
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
  useEffect(() => {
    if (!canvasRef.current) return;
    const el = canvasRef.current;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      if (width > 0 && height > 0) setMeasured({ width, height });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [points.length > 0]);
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
  const W = Math.round(measured.width);
  const H = Math.round(measured.height);
  const left = compact ? 52 : 42;
  const right = compact ? 18 : 42;
  const top = compact ? 44 : 58;
  const bottom = compact ? 46 : 42;
  const plotW = W - left - right;
  const plotH = H - top - bottom;
  const EDGE_PAD = 22; // largest halo radius; keeps points off the axis labels
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
      <div ref={canvasRef} className="local-map-canvas">
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
            haloRadius = 6 + Math.sqrt(p.count / maxCount) * 16;
          return (
            <g key={p.cell}>
              <circle className="map-halo" cx={q.x} cy={q.y} r={haloRadius} />
              <circle className="map-point" cx={q.x} cy={q.y} r={4}>
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
      </div>
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
    [devices, setDevices] = useState<Device[]>([]),
    [vendorOptions, setVendorOptions] = useState<string[]>([]),
    [savedFilters, setSavedFilters] = useState<SavedFilter[]>([]),
    [filterName, setFilterName] = useState("");
  function params(area = a, run = r, device = d, override: Record<string, string> = {}) {
    const q = new URLSearchParams();
    if (area) q.set("area_id", area);
    if (run) q.set("run_id", run);
    if (device) q.set("device_id", device);
    if (override.protocol ?? protocol) q.set("protocol", override.protocol ?? protocol);
    if (override.vendor ?? vendor) q.set("vendor", override.vendor ?? vendor);
    if (override.minRssi ?? minRssi) q.set("min_rssi", override.minRssi ?? minRssi);
    if (override.start ?? start) q.set("start", (override.start ?? start) + "T00:00:00");
    if (override.end ?? end) q.set("end", (override.end ?? end) + "T23:59:59");
    return q;
  }
  async function load(area = a, run = r, device = d, override: Record<string, string> = {}) {
    const q = params(area, run, device, override),
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
    api<SavedFilter[]>("/v1/saved-filters").then(setSavedFilters).catch(() => undefined);
  }, []);
  async function saveCurrentFilter() {
    if (!filterName.trim()) return;
    const filters = { area_id: a, run_id: r, device_id: d, protocol, vendor, minRssi, start, end };
    try {
      const saved = await send<SavedFilter>("/v1/saved-filters", { name: filterName.trim(), resource: "coverage", filters });
      setSavedFilters((items) => [saved, ...items]);
      setFilterName("");
    } catch (x) {
      setTileNotice(true);
    }
  }
  function applySavedFilter(item: SavedFilter) {
    const filters = item.filters || {};
    setA(filters.area_id || ""); setR(filters.run_id || ""); setD(filters.device_id || "");
    setProtocol(filters.protocol || ""); setVendor(filters.vendor || ""); setMinRssi(filters.minRssi || ""); setStart(filters.start || ""); setEnd(filters.end || "");
    load(filters.area_id || "", filters.run_id || "", filters.device_id || "", filters);
  }
  useEffect(() => {
    setD(initialDevice);
    load(a, r, initialDevice);
  }, [initialDevice]);
  useEffect(() => {
    api<{ oui_organization: string }[]>("/v1/devices/vendors").then((rows) =>
      setVendorOptions(rows.map((x) => x.oui_organization)),
    );
  }, []);
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
            .filter((x) => !a || String(x.collection_id) === a)
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
          list="coverage-vendor-options"
        />
        <datalist id="coverage-vendor-options">
          {vendorOptions.map((x) => (
            <option key={x} value={x} />
          ))}
        </datalist>
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
      <div className="saved-filter-bar coverage-saved-filters">
        <select aria-label="Saved coverage filter" defaultValue="" onChange={(event) => {
          const item = savedFilters.find((candidate) => String(candidate.id) === event.target.value);
          if (item) applySavedFilter(item);
        }}>
          <option value="">Saved filters</option>
          {savedFilters.filter((item) => item.resource === "coverage").map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
        </select>
        <input aria-label="Saved filter name" value={filterName} onChange={(event) => setFilterName(event.target.value)} placeholder="Name current filter" />
        <button className="secondary" onClick={saveCurrentFilter} disabled={!filterName.trim()}>Save filter</button>
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
  collection_id: number;
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
  evidence_links: string[];
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
            .filter((x) => x.completed && String(x.collection_id) === a)
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
    [drafts, setDrafts] = useState<Record<number, string>>({}),
    [links, setLinks] = useState<Record<number, string>>({});
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
        body: JSON.stringify({
          status,
          disposition_note: drafts[id] || null,
          evidence_links: (links[id] || "").split("\n").map((item) => item.trim()).filter(Boolean),
        }),
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
            <label className="field-label compact-field">
              Evidence links or local references (one per line)
              <textarea
                value={links[x.id] ?? (x.evidence_links || []).join("\n")}
                onChange={(event) =>
                  setLinks((current) => ({ ...current, [x.id]: event.target.value }))
                }
                placeholder="ticket-123 or https://approved.local/evidence"
                rows={2}
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
type DeviceReviewItem = {
  group_key: string;
  evidence_tier: "actionable" | "sparse" | "no_signal";
  label: string;
  device_count: number;
  observation_count: number;
  priority: number;
  categories: Record<string, number>;
  roles: Record<string, number>;
  evidence: string[];
  representative: { device: Device; review: { status: string; disposition_note: string | null; evidence_links: string[] }; priority: number; last_protocol?: string | null; last_ssid?: string | null; last_device_name?: string | null; last_device_type?: string | null; observation_count: number };
};
type ReviewCounts = Record<"actionable" | "sparse" | "no_signal", { groups: number; devices: number }>;
function DeviceReviews({ areas, role, showDevice }: { areas: Area[]; role: string; showDevice: (id: number) => void }) {
  const pageSize = 24;
  const [area, setArea] = useState(""),
    [status, setStatus] = useState("open"),
    [bucket, setBucket] = useState<"actionable" | "no_signal" | "all">("actionable"),
    [items, setItems] = useState<DeviceReviewItem[]>([]),
    [total, setTotal] = useState(0),
    [deviceTotal, setDeviceTotal] = useState(0),
    [counts, setCounts] = useState<ReviewCounts>({ actionable: { groups: 0, devices: 0 }, sparse: { groups: 0, devices: 0 }, no_signal: { groups: 0, devices: 0 } }),
    [drafts, setDrafts] = useState<Record<string, string>>({}),
    [links, setLinks] = useState<Record<string, string>>({}),
    [contextOpen, setContextOpen] = useState<Record<string, boolean>>({}),
    [overrideCategories, setOverrideCategories] = useState<Record<string, string>>({}),
    [offset, setOffset] = useState(0),
    [note, setNote] = useState("");
  async function load(nextArea = area, nextStatus = status, nextBucket = bucket, nextOffset = offset) {
    const query = new URLSearchParams({ status: nextStatus, bucket: nextBucket, limit: String(pageSize), offset: String(nextOffset) });
    if (nextArea) query.set("area_id", nextArea);
    try {
      const result = await api<{ items: DeviceReviewItem[]; total: number; device_total: number; counts: ReviewCounts }>("/v1/device-reviews?" + query);
      setItems(result.items);
      setTotal(result.total);
      setDeviceTotal(result.device_total);
      setCounts(result.counts);
      setOffset(nextOffset);
    } catch (error) {
      setNote(msg(error));
    }
  }
  useEffect(() => {
    load();
  }, []);
  async function disposition(groupKey: string, nextStatus: string) {
    try {
      await api("/v1/device-review-groups", {
        method: "PATCH",
        body: JSON.stringify({
          group_key: groupKey,
          status: nextStatus,
          area_id: area ? Number(area) : null,
          disposition_note: drafts[groupKey] || null,
          evidence_links: (links[groupKey] || "").split("\n").map((item) => item.trim()).filter(Boolean),
        }),
        headers: { "Content-Type": "application/json" },
      });
      setNote("Group disposition saved and audited.");
      load();
    } catch (error) {
      setNote(msg(error));
    }
  }
  async function overrideCategory(item: DeviceReviewItem) {
    const category = overrideCategories[item.group_key] || item.representative.device.category;
    try {
      await api("/v1/devices/" + item.representative.device.id + "/category", {
        method: "PATCH",
        body: JSON.stringify({ category }),
        headers: { "Content-Type": "application/json" },
      });
      setNote("Category override saved and audited. Review disposition remains separate.");
      load();
    } catch (error) {
      setNote(msg(error));
    }
  }
  return (
    <section className="panel">
      <div className="toolbar">
        <div>
          <p className="eyebrow">EVIDENCE REVIEW</p>
          <h2>Classification triage</h2>
          <p className="muted">{total.toLocaleString()} groups · {deviceTotal.toLocaleString()} devices · repeated evidence is grouped before review.</p>
        </div>
        <div className="toolbar-controls review-controls">
          <select aria-label="Survey area" value={area} onChange={(event) => { setArea(event.target.value); load(event.target.value, status, bucket, 0); }}>
            <option value="">All areas</option>
            {areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
          </select>
          <select aria-label="Review status" value={status} onChange={(event) => { setStatus(event.target.value); load(area, event.target.value, bucket, 0); }}>
            <option value="open">Open</option>
            <option value="needs_review">Needs review</option>
            <option value="confirmed">Confirmed</option>
            <option value="dismissed">Dismissed</option>
            <option value="insufficient_evidence">Insufficient evidence</option>
            <option value="all">All dispositions</option>
          </select>
        </div>
      </div>
      <div className="review-buckets" role="tablist" aria-label="Evidence quality">
        <button className={bucket === "actionable" ? "active" : ""} onClick={() => { setBucket("actionable"); load(area, status, "actionable", 0); }}><b>{counts.actionable.groups.toLocaleString()}</b><span>actionable groups</span><small>{counts.actionable.devices.toLocaleString()} devices</small></button>
        <button className={bucket === "no_signal" ? "active" : ""} onClick={() => { setBucket("no_signal"); load(area, status, "no_signal", 0); }}><b>{counts.no_signal.groups.toLocaleString()}</b><span>no-signal groups</span><small>{counts.no_signal.devices.toLocaleString()} devices</small></button>
        <button className={bucket === "all" ? "active" : ""} onClick={() => { setBucket("all"); load(area, status, "all", 0); }}><b>{(counts.actionable.groups + counts.no_signal.groups).toLocaleString()}</b><span>all groups</span><small>{(counts.actionable.devices + counts.no_signal.devices).toLocaleString()} devices</small></button>
      </div>
      {note && <p className="notice">{note}</p>}
      <div className="list review-list">
        {items.map((item) => {
          const x = item.representative.device;
          const key = item.group_key;
          return (
            <div key={key} className="review-card">
              <div className="review-card-header">
                <div>
                  <b>{item.label}</b>
                  <span>{item.device_count.toLocaleString()} devices · {item.observation_count.toLocaleString()} observations · priority {Math.round(item.priority * 100)}</span>
                </div>
                <span className={item.evidence_tier === "no_signal" ? "category-chip review-tier-none" : "category-chip"}>{item.evidence_tier.replaceAll("_", " ")}</span>
              </div>
              <div className="review-meta">
                <span><small>Category mix</small>{Object.entries(item.categories).map(([name, count]) => `${name} (${count})`).join(" · ")}</span>
                <span><small>Role mix</small>{Object.entries(item.roles).map(([name, count]) => `${name.replaceAll("_", " ")} (${count})`).join(" · ") || "None"}</span>
                <span><small>Representative</small>{x.last_device_name || x.last_ssid || x.last_device_type || x.oui_organization} · {x.last_protocol || "unknown protocol"}</span>
              </div>
              <div className="review-evidence-block">
                <small>Retained evidence</small>
                <span>{item.evidence.length ? item.evidence.join(" · ") : "No usable vendor, name, SSID, type, or rule evidence."}</span>
              </div>
              {item.device_count === 1 && (role === "analyst" || role === "admin") && <div className="review-override"><label className="field-label">Override category<select aria-label="Override category" value={overrideCategories[key] || x.category} onChange={(event) => setOverrideCategories((current) => ({ ...current, [key]: event.target.value }))}>{['unknown', 'camera', 'printer', 'network', 'mobile', 'iot', 'bluetooth', 'workstation', 'audio', 'entertainment', 'wearable', 'automotive'].map((category) => <option key={category} value={category}>{category}</option>)}</select></label><button className="quiet" onClick={() => overrideCategory(item)}>Apply override</button></div>}
              <button className="review-context-toggle" onClick={() => setContextOpen((current) => ({ ...current, [key]: !current[key] }))}>{contextOpen[key] || drafts[key] || links[key] ? "Hide review context" : "Add review context (optional)"}</button>
              {(contextOpen[key] || drafts[key] || links[key]) && <div className="review-fields"><label className="field-label compact-field">Review note<input value={drafts[key] ?? item.representative.review.disposition_note ?? ""} onChange={(event) => setDrafts((current) => ({ ...current, [key]: event.target.value }))} placeholder="Optional handoff context" /></label><label className="field-label compact-field">Evidence references<textarea rows={2} value={links[key] ?? (item.representative.review.evidence_links || []).join("\n")} onChange={(event) => setLinks((current) => ({ ...current, [key]: event.target.value }))} placeholder="ticket-123 or one local reference per line" /></label></div>}
              <div className="review-actions">
                <button className="quiet" onClick={() => showDevice(x.id)}>Open evidence</button>
                {(role === "analyst" || role === "admin") && <><button className="quiet" onClick={() => disposition(key, "confirmed")}>Confirm group</button><button className="quiet" onClick={() => disposition(key, item.evidence_tier === "no_signal" ? "insufficient_evidence" : "dismissed")}>{item.evidence_tier === "no_signal" ? "Mark insufficient evidence" : "Dismiss group"}</button><button className="quiet" onClick={() => disposition(key, "needs_review")}>Needs review</button></>}
              </div>
            </div>
          );
        })}
        {!items.length && <p>No classification reviews for this selection.</p>}
      </div>
      {total > 0 && <div className="pager review-pager" aria-label="Evidence review pages">
        <button className="quiet" disabled={offset === 0} onClick={() => load(area, status, bucket, Math.max(0, offset - pageSize))}>Previous</button>
        <span>Page {Math.floor(offset / pageSize) + 1} of {Math.ceil(total / pageSize).toLocaleString()}</span>
        <button className="quiet" disabled={offset + pageSize >= total} onClick={() => load(area, status, bucket, offset + pageSize)}>Next</button>
      </div>}
    </section>
  );
}
type RuleProposal = { id: number; rule_version: string; revision: number; target_category: string; matcher: Record<string, string[] | string>; evidence: string[]; support_count: number; status: string; created_by: string; review_note?: string | null; created_at: string };
type LearningSummary = { reviewed: number; dispositions: Record<string, number>; category_overrides: number; by_category: { category: string; count: number }[]; rule_proposals: Record<string, number>; false_positive_rate: number | null; interpretation: string };
function RuleLearning({ areas, role }: { areas: Area[]; role: string }) {
  const [area, setArea] = useState(""), [start, setStart] = useState(""), [end, setEnd] = useState(""), [summary, setSummary] = useState<LearningSummary | null>(null), [proposals, setProposals] = useState<RuleProposal[]>([]), [note, setNote] = useState(""), [loading, setLoading] = useState(false);
  const canReview = role === "analyst" || role === "admin";
  async function load() {
    setLoading(true); setNote("");
    const query = new URLSearchParams(); if (area) query.set("area_id", area); if (start) query.set("start", start + "T00:00:00"); if (end) query.set("end", end + "T23:59:59");
    try {
      const [nextSummary, nextProposals] = await Promise.all([api<LearningSummary>("/v1/learning/summary?" + query), api<RuleProposal[]>("/v1/rule-proposals?status=all&limit=100")]);
      setSummary(nextSummary); setProposals(nextProposals);
    } catch (error) { setNote(msg(error)); }
    finally { setLoading(false); }
  }
  useEffect(() => { load(); }, []);
  async function updateProposal(id: number, status: string) {
    try { await api("/v1/rule-proposals/" + id, { method: "PATCH", body: JSON.stringify({ status }), headers: { "Content-Type": "application/json" } }); setNote("Proposal disposition saved and audited. Rule promotion remains manual."); load(); }
    catch (error) { setNote(msg(error)); }
  }
  const matcherText = (matcher: RuleProposal["matcher"]) => Object.entries(matcher || {}).map(([key, value]) => `${key}: ${Array.isArray(value) ? value.join(", ") : value}`).join(" · ");
  return <section className="panel">
    <div className="toolbar"><div><p className="eyebrow">ANALYST LEARNING</p><h2>Rule feedback loop</h2><p className="muted">Overrides become versioned proposals for review. Nothing here silently changes production rules.</p></div><div className="toolbar-controls learning-controls"><select aria-label="Learning collection" value={area} onChange={(event) => setArea(event.target.value)}><option value="">All collections</option>{areas.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select><input aria-label="Learning start date" type="date" value={start} onChange={(event) => setStart(event.target.value)} /><input aria-label="Learning end date" type="date" value={end} onChange={(event) => setEnd(event.target.value)} /><button onClick={load} disabled={loading}>{loading ? "Loading…" : "Apply"}</button></div></div>
    {note && <p className="notice">{note}</p>}
    {summary && <><div className="category-summary taxonomy-summary"><div><b>{summary.reviewed.toLocaleString()}</b><span>reviewed devices</span></div><div><b>{summary.category_overrides.toLocaleString()}</b><span>analyst overrides</span></div><div><b>{summary.false_positive_rate === null ? "—" : Math.round(summary.false_positive_rate * 100) + "%"}</b><span>dismissed among confirmed/dismissed</span></div><div><b>{(summary.rule_proposals.open || 0).toLocaleString()}</b><span>open proposals</span></div></div><p className="muted">{summary.interpretation}</p></>}
    <div className="taxonomy-subhead"><div><p className="eyebrow">PROPOSALS</p><h3>Candidate rule changes</h3></div><span className="muted">Accepted proposals require deliberate rule implementation.</span></div>
    <div className="list learning-proposals">{proposals.map((proposal) => <div key={proposal.id} className="proposal-row"><div><b>{proposal.target_category} · {proposal.rule_version} revision {proposal.revision}</b><span>{proposal.support_count.toLocaleString()} supporting override(s) · {proposal.status}</span><small>{matcherText(proposal.matcher)}</small><small>{proposal.evidence?.length ? proposal.evidence.join(" · ") : "No retained rule evidence"}</small></div>{canReview && <div className="review-actions">{proposal.status !== "accepted" && <button className="quiet" onClick={() => updateProposal(proposal.id, "accepted")}>Accept proposal</button>}{proposal.status !== "rejected" && <button className="quiet" onClick={() => updateProposal(proposal.id, "rejected")}>Reject</button>}<button className="quiet" onClick={() => updateProposal(proposal.id, "needs_review")}>Needs review</button></div>}</div>)}{!proposals.length && <p className="muted">No analyst proposals yet. Apply a category override from evidence review to seed one.</p>}</div>
    <div className="taxonomy-subhead"><div><p className="eyebrow">FALSE-POSITIVE SIGNALS</p><h3>What the selected scope is teaching us</h3></div></div><div className="table-scroll"><table><thead><tr><th>Current category</th><th>Reviewed devices</th></tr></thead><tbody>{summary?.by_category.map((item) => <tr key={item.category}><td><span className="category-chip">{item.category}</span></td><td>{item.count.toLocaleString()}</td></tr>)}</tbody></table></div>
  </section>;
}
type ComparisonItem = { device_id: number; token_prefix: string; category: string; category_confidence: number; oui_organization: string; roles: string[]; observation_count: number; changed_fields: string[] };
type ComparisonResult = { left: { id: number; name: string }; right: { id: number; name: string }; counts: Record<string, number>; new: ComparisonItem[]; returning: ComparisonItem[]; disappeared: ComparisonItem[]; changed: ComparisonItem[]; truncated: boolean };
function RunComparison({ runs }: { runs: Run[] }) {
  const completedRuns = runs.filter((run) => run.completed);
  const [left, setLeft] = useState(""), [right, setRight] = useState(""), [result, setResult] = useState<ComparisonResult | null>(null), [note, setNote] = useState("");
  useEffect(() => { if (completedRuns.length > 1) { setLeft(String(completedRuns[completedRuns.length - 1].id)); setRight(String(completedRuns[0].id)); } }, [runs]);
  async function compare() { if (!left || !right || left === right) { setNote("Choose two different capture runs."); return; } try { setNote(""); setResult(await api<ComparisonResult>(`/v1/import-comparison?left_run_id=${left}&right_run_id=${right}&limit=100`)); } catch (error) { setNote(msg(error)); } }
  const rows = (items: ComparisonItem[]) => <div className="table-scroll"><table><thead><tr><th>Site token</th><th>Category</th><th>Vendor</th><th>Observations</th><th>Changed fields</th></tr></thead><tbody>{items.map((item) => <tr key={item.device_id}><td><code>{item.token_prefix}</code></td><td>{item.category}</td><td>{item.oui_organization}</td><td>{item.observation_count}</td><td>{item.changed_fields.join(", ") || "—"}</td></tr>)}</tbody></table></div>;
  return <section className="panel"><div className="toolbar"><div><p className="eyebrow">IMPORT COMPARISON</p><h2>Run-to-run change</h2><p className="muted">Compare pseudonymous device presence and retained facts. Raw addresses are never included.</p></div><div className="toolbar-controls comparison-controls"><select aria-label="Earlier capture run" value={left} onChange={(event) => setLeft(event.target.value)}><option value="">Earlier run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.name}</option>)}</select><select aria-label="Later capture run" value={right} onChange={(event) => setRight(event.target.value)}><option value="">Later run</option>{completedRuns.map((run) => <option key={run.id} value={run.id}>{run.name}</option>)}</select><button onClick={compare} disabled={completedRuns.length < 2}>Compare</button></div></div>{note && <p className="warning">{note}</p>}{!completedRuns.length && <p className="muted">Complete at least two capture runs to compare them.</p>}{result && <><div className="category-summary taxonomy-summary">{["new", "returning", "changed", "disappeared"].map((key) => <div key={key}><b>{(result.counts[key] || 0).toLocaleString()}</b><span>{key} devices</span></div>)}</div>{result.truncated && <p className="muted">Some lists are capped at 100 devices; counts are complete.</p>}<div className="taxonomy-subhead"><div><p className="eyebrow">NEW</p><h3>New in {result.right.name}</h3></div></div>{rows(result.new)}<div className="taxonomy-subhead"><div><p className="eyebrow">RETURNING</p><h3>Present in both runs</h3></div></div>{rows(result.returning)}<div className="taxonomy-subhead"><div><p className="eyebrow">CHANGED</p><h3>Changed retained facts</h3></div></div>{rows(result.changed)}<div className="taxonomy-subhead"><div><p className="eyebrow">DISAPPEARED</p><h3>Only in {result.left.name}</h3></div></div>{rows(result.disappeared)}</>}</section>;
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
    [note, setNote] = useState(""),
    [rawDays, setRawDays] = useState("30"),
    [normalizedDays, setNormalizedDays] = useState("365"),
    [preset, setPreset] = useState("custom");
  useEffect(() => {
    api<{ raw_retention_days: number; normalized_retention_days: number }>("/v1/retention/settings")
      .then((x) => {
        setRawDays(String(x.raw_retention_days));
        setNormalizedDays(String(x.normalized_retention_days));
      })
      .catch((x) => setNote(msg(x)));
  }, []);
  async function saveSettings(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      const x = await api<{ raw_retention_days: number; normalized_retention_days: number }>("/v1/retention/settings", {
        method: "PATCH",
        body: JSON.stringify({ raw_retention_days: Number(rawDays), normalized_retention_days: Number(normalizedDays) }),
      });
      setRawDays(String(x.raw_retention_days));
      setNormalizedDays(String(x.normalized_retention_days));
      setNote("Retention settings saved and audited.");
      if (p) preview();
    } catch (x) {
      setNote(msg(x));
    }
  }
  function choosePreset(value: string) {
    setPreset(value);
    if (value !== "custom") {
      setRawDays(value);
      setNormalizedDays(value);
    }
  }
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
      <form className="retention-settings" onSubmit={saveSettings}>
        <label className="field-label">Preset<select value={preset} onChange={(event) => choosePreset(event.target.value)}><option value="custom">Custom</option><option value="30">30 days</option><option value="90">90 days</option><option value="180">180 days</option></select></label>
        <label className="field-label">Raw upload days<input type="number" min="1" max="3650" value={rawDays} onChange={(event) => setRawDays(event.target.value)} /></label>
        <label className="field-label">Normalized evidence days<input type="number" min="1" max="3650" value={normalizedDays} onChange={(event) => setNormalizedDays(event.target.value)} /></label>
        <button className="secondary">Save retention windows</button>
      </form>
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
          <label className="field-label compact-field" htmlFor="retention-confirm">
            Type PURGE to run the reviewed sweep
          </label>
          <div className="purge-row">
            <input
              id="retention-confirm"
              value={confirm}
              onChange={(x) => setConfirm(x.target.value)}
              aria-label="Retention confirmation"
            />
            <button disabled={confirm !== "PURGE"} onClick={purge}>
              Purge reviewed candidates
            </button>
          </div>
        </div>
      )}
      {note && <p className="notice">{note}</p>}
    </section>
  );
}
function CollectionsPage({
  role,
  reload,
  say,
}: {
  role: string;
  reload: () => void;
  say: (x: string) => void;
}) {
  const [areas, setAreas] = useState<Area[]>([]);
  const canCreate = role === "analyst" || role === "admin";
  async function load() {
    setAreas(await api<Area[]>("/v1/survey-areas"));
  }
  useEffect(() => {
    load();
  }, []);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget,
      f = new FormData(form);
    try {
      const polygonText = String(f.get("polygon_json") || "").trim();
      let polygon: unknown = undefined;
      if (polygonText) {
        try { polygon = JSON.parse(polygonText); } catch { throw new Error("Polygon must be valid JSON"); }
      }
      await send("/v1/survey-areas", {
        name: f.get("name"),
        authorization_ref: f.get("authorization_ref"),
        precision: f.get("precision"),
        polygon,
      });
      form.reset();
      say("Collection created.");
      load();
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  async function rename(e: FormEvent<HTMLFormElement>, id: number) {
    e.preventDefault();
    const name = new FormData(e.currentTarget).get("name");
    try {
      await api("/v1/survey-areas/" + id, {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      say("Renamed.");
      load();
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  async function remove(area: Area) {
    if (
      !window.confirm(
        "Permanently delete the collection \"" + area.name + "\"?",
      )
    )
      return;
    try {
      await api("/v1/survey-areas/" + area.id, { method: "DELETE" });
      say("Deleted " + area.name + ".");
      load();
      reload();
    } catch (x) {
      say(msg(x));
    }
  }
  return (
    <div className="split">
      {canCreate && (
        <section className="panel">
          <p className="eyebrow">NEW COLLECTION</p>
          <h2>Create a collection</h2>
          <p className="muted">
            Use a collection only when you want to compare or filter a set of
            captures. Precision is set here and cannot be changed later:
            "exact" retains each device's real address, encrypted, for later
            admin review; "coarse" never does.
          </p>
          <form onSubmit={create}>
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
            <label className="field-label">
              Optional approved boundary (GeoJSON Polygon)
              <textarea name="polygon_json" rows={3} placeholder={'{"type":"Polygon","coordinates":[[[-122.7,45.4],[-122.6,45.4],[-122.6,45.5],[-122.7,45.4]]]}'} />
            </label>
            <button>Create collection</button>
          </form>
        </section>
      )}
      <section className="panel">
        <p className="eyebrow">COLLECTION MANAGEMENT</p>
        <h2>Collections</h2>
        <p className="muted">
          Assign captures to a collection from the Surveys page, either at
          import time or afterward.
          {role === "admin"
            ? " Rename one here, or delete one once it has no runs."
            : ""}
        </p>
        <div className="list">
          {areas.map((x) => (
            <div key={x.id}>
              {role === "admin" ? (
                <form className="inline-form" onSubmit={(e) => rename(e, x.id)}>
                  <input name="name" defaultValue={x.name} required />
                  <button className="secondary">Rename</button>
                  <button
                    type="button"
                    className="secondary danger"
                    disabled={!!x.run_count}
                    title={
                      x.run_count
                        ? "Refile or delete this collection's runs first"
                        : undefined
                    }
                    onClick={() => remove(x)}
                  >
                    Delete
                  </button>
                </form>
              ) : (
                <b>{x.name}</b>
              )}
              <span>
                {x.precision} · {(x.run_count ?? 0).toLocaleString()} runs ·{" "}
                {(x.device_count ?? 0).toLocaleString()} devices
              </span>
            </div>
          ))}
          {!areas.length && <p>No collections yet.</p>}
        </div>
      </section>
    </div>
  );
}
function Access({ me }: { me: Me }) {
  const [u, setU] = useState<Account[]>([]),
    [note, setNote] = useState(""),
    [currentPassword, setCurrentPassword] = useState(""),
    [newPassword, setNewPassword] = useState("");
  async function load() {
    setU(await api<Account[]>("/v1/users"));
  }
  useEffect(() => {
    if (me.role === "admin") load();
  }, [me.role]);
  if (me.role !== "admin")
    return (
      <section className="panel">
        <p className="eyebrow">YOUR CREDENTIALS</p>
        <h2>Change password</h2>
        <form onSubmit={changeOwnPassword}>
          <label className="field-label">Current password<input type="password" minLength={1} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
          <label className="field-label">New password<input type="password" minLength={10} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
          <button>Change password</button>
        </form>
        {note && <p className="notice">{note}</p>}
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
  async function changeOwnPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      await api("/v1/auth/password", {
        method: "POST",
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      });
      setCurrentPassword("");
      setNewPassword("");
      setNote("Your password changed; other sessions were revoked.");
    } catch (x) {
      setNote(msg(x));
    }
  }
  async function resetPassword(account: Account) {
    const next = window.prompt("New password for " + account.username + " (10+ characters):");
    if (!next) return;
    try {
      await api("/v1/users/" + account.id + "/password", {
        method: "POST",
        body: JSON.stringify({ new_password: next }),
      });
      setNote("Password reset for " + account.username + "; their sessions were revoked.");
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
        <p className="eyebrow">YOUR CREDENTIALS</p>
        <h2>Change password</h2>
        <form onSubmit={changeOwnPassword}>
          <label className="field-label">Current password<input type="password" minLength={1} value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
          <label className="field-label">New password<input type="password" minLength={10} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
          <button>Change password</button>
        </form>
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
              <button className="quiet" onClick={() => resetPassword(x)}>
                Reset password
              </button>
            </div>
          ))}
          {!u.length && <p>Nothing yet.</p>}
        </div>
      </section>
      <OUIImportPanel />
      <RetentionPanel />
    </div>
  );
}
type AuditItem = {
  id: number;
  actor: string;
  role: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  detail: Record<string, unknown>;
  created_at: string;
};
function AuditEvents() {
  const [items, setItems] = useState<AuditItem[]>([]), [error, setError] = useState("");
  useEffect(() => {
    api<AuditItem[]>("/v1/audit-events?limit=200").then(setItems).catch((x) => setError(msg(x)));
  }, []);
  return (
    <section className="panel">
      <div className="panel-heading">
        <div><p className="eyebrow">GOVERNANCE</p><h2>Audit log</h2></div>
        <span className="tag">{items.length} recent events</span>
      </div>
      <p className="muted">Authentication, imports, policy changes, review decisions, and destructive actions are recorded without secrets or raw device addresses.</p>
      {error && <p className="warning">{error}</p>}
      <div className="table-scroll">
        <table>
          <thead><tr><th>When</th><th>Actor</th><th>Action</th><th>Resource</th><th>Details</th></tr></thead>
          <tbody>{items.map((item) => (
            <tr key={item.id}>
              <td>{new Date(item.created_at).toLocaleString()}</td>
              <td>{item.actor} · {item.role}</td>
              <td>{item.action}</td>
              <td>{item.resource_type}{item.resource_id ? " #" + item.resource_id : ""}</td>
              <td><code>{JSON.stringify(item.detail)}</code></td>
            </tr>
          ))}</tbody>
        </table>
      </div>
      {!items.length && !error && <p className="muted">No audit events yet.</p>}
    </section>
  );
}
createRoot(document.getElementById("root")!).render(<App />);
