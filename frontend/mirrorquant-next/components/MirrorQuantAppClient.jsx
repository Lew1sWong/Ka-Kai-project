import Image from "next/image";
import { useEffect, useRef, useState } from "react";

const API_BASE = (
  (typeof process !== "undefined" && process.env?.NEXT_PUBLIC_API_BASE_URL)
  || ""
).trim().replace(/\/$/, "");
const REQUEST_TIMEOUT_MS = 8000;
const landingTickerItems = [
  "Save any ticker window as a hero",
  "Price DNA powered by trained VQ-VAE retrieval",
  "Economic DNA adds macro and factor context",
  "Social DNA blends narrative and sentiment signals",
  "Saved search runs preserve ranked evidence",
  "Market watch keeps every run grounded in regime context",
];
const landingPreviewSeries = [102, 104, 106, 105, 109, 114, 118, 121, 119, 123, 129, 136];
const landingMetrics = [
  { value: "3", label: "DNA search engines" },
  { value: "40D", label: "Learned VQ-VAE encoded window" },
  { value: "Any", label: "Ticker and date range can become a hero" },
  { value: "Saved", label: "Heroes, runs, and ranked matches persist" },
];
const capabilityCards = [
  {
    icon: "P",
    title: "Price DNA retrieval",
    copy: "Use the trained VQ-VAE to match latent breakout behavior instead of screening only by sector labels.",
  },
  {
    icon: "E",
    title: "Economic DNA context",
    copy: "Compare a hero window against macro regime and stock-factor behavior to explain when the move made sense.",
  },
  {
    icon: "S",
    title: "Social DNA layer",
    copy: "Blend local narrative profiles with scored news and sentiment signals to capture attention, tone, and controversy.",
  },
  {
    icon: "H",
    title: "Saved heroes",
    copy: "Turn any ticker plus date range into a reusable hero window instead of being limited to prewritten showcase cases.",
  },
  {
    icon: "R",
    title: "Search history",
    copy: "Persist search runs and ranked matches so you can revisit the exact output that produced a prior idea.",
  },
  {
    icon: "M",
    title: "Market framing",
    copy: "Layer live or proxy market-watch context on top of search output so the match is anchored in current tape conditions.",
  },
];
const workspaceSidebarItems = [
  { id: "workspace-command-center", label: "Overview", detail: "Command center", icon: "overview" },
  { id: "workspace-launchpad", label: "Launchpad", detail: "Signal setup", icon: "launchpad" },
  { id: "workspace-saved-heroes", label: "Saved Heroes", detail: "Reusable windows", icon: "heroes" },
  { id: "workspace-search-history", label: "Search History", detail: "Ranked runs", icon: "history" },
  { id: "workspace-hero-window", label: "Hero Window", detail: "Price view", icon: "window" },
  { id: "workspace-mirror-matches", label: "Mirror Matches", detail: "Top analogs", icon: "matches" },
  { id: "workspace-market-watch", label: "Market Watch", detail: "Tape context", icon: "watch" },
  { id: "workspace-industry-chain", label: "Industry Chain", detail: "Peer links", icon: "chain" },
];

function WorkspaceSidebarIcon({ icon }) {
  const commonProps = {
    className: "workspace-nav-icon",
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: "1.8",
    strokeLinecap: "round",
    strokeLinejoin: "round",
    "aria-hidden": "true",
  };

  switch (icon) {
    case "overview":
      return (
        <svg {...commonProps}>
          <rect x="4" y="4" width="6" height="6" rx="1.4" />
          <rect x="14" y="4" width="6" height="6" rx="1.4" />
          <rect x="4" y="14" width="6" height="6" rx="1.4" />
          <rect x="14" y="14" width="6" height="6" rx="1.4" />
        </svg>
      );
    case "launchpad":
      return (
        <svg {...commonProps}>
          <path d="M5 16.5c2.6 0 2.6-9 5.2-9s2.6 9 5.2 9 2.6-6 3.1-6" />
          <path d="M17.3 10.5 19.5 10l.5 2.2" />
        </svg>
      );
    case "heroes":
      return (
        <svg {...commonProps}>
          <path d="M7 5.5h8a2 2 0 0 1 2 2v11l-6-3-6 3v-11a2 2 0 0 1 2-2Z" />
        </svg>
      );
    case "history":
      return (
        <svg {...commonProps}>
          <path d="M4.5 12a7.5 7.5 0 1 0 2.2-5.3" />
          <path d="M4.5 6.5v4h4" />
          <path d="M12 8.5v4l2.8 1.7" />
        </svg>
      );
    case "window":
      return (
        <svg {...commonProps}>
          <rect x="4" y="5" width="16" height="14" rx="2.4" />
          <path d="M4 9.5h16" />
          <path d="m9 15 2.5-2.5 2 2 3.5-4" />
        </svg>
      );
    case "matches":
      return (
        <svg {...commonProps}>
          <path d="M7 7h9.5" />
          <path d="m13.5 3.5 3.5 3.5-3.5 3.5" />
          <path d="M17 17H7.5" />
          <path d="m10.5 20.5-3.5-3.5 3.5-3.5" />
        </svg>
      );
    case "watch":
      return (
        <svg {...commonProps}>
          <path d="M12 4.5 6.2 7v5c0 3.8 2.2 6.3 5.8 7.5 3.6-1.2 5.8-3.7 5.8-7.5V7L12 4.5Z" />
          <path d="m9.5 12 1.6 1.7 3.5-3.7" />
        </svg>
      );
    case "chain":
      return (
        <svg {...commonProps}>
          <path d="M9.5 8.5 7 11a3 3 0 0 0 4.2 4.2l2.3-2.3" />
          <path d="m14.5 15.5 2.5-2.5A3 3 0 0 0 12.8 8.8l-2.3 2.3" />
        </svg>
      );
    default:
      return null;
  }
}

function apiUrl(path) {
  return `${API_BASE}${path}`;
}

async function fetchJson(path, options = {}) {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);
  let response;

  try {
    response = await fetch(apiUrl(path), {
      credentials: "include",
      ...options,
      signal: controller.signal,
    });
  } catch (error) {
    if (error?.name === "AbortError") {
      throw new Error("MirrorQuant API timed out. Make sure the backend is running on http://127.0.0.1:8000.");
    }
    throw error;
  } finally {
    clearTimeout(timeoutId);
  }

  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch {
      // Keep the default detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

async function postJson(path, payload) {
  return fetchJson(path, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

async function loginUser(payload) {
  return postJson("/api/auth/login", payload);
}

async function registerUser(payload) {
  return postJson("/api/auth/register", payload);
}

async function resendVerificationEmail() {
  return postJson("/api/auth/resend-verification", {});
}

async function logoutUser() {
  return postJson("/api/auth/logout", {});
}

async function fetchCurrentUser() {
  return fetchJson("/api/auth/me");
}

function traitPills(traits = []) {
  return traits.map((trait) => (
    <span key={trait} className="pill">
      {trait}
    </span>
  ));
}

function hashString(value) {
  return value.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
}

function sparklineValues(label, value) {
  const seed = hashString(`${label}-${value}`);
  return Array.from({ length: 8 }, (_, index) => {
    const wave = Math.sin((seed + index * 13) / 9);
    const drift = Math.cos((seed + index * 7) / 11);
    return Math.round(44 + wave * 18 + drift * 10);
  });
}

function normalizeSeriesToSparkline(values) {
  if (!values.length) {
    return [];
  }

  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;

  return values.map((value) => Math.round(((value - min) / span) * 80 + 10));
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function sparklinePoints(values) {
  if (!values.length) {
    return "";
  }

  const step = 100 / Math.max(values.length - 1, 1);
  return values
    .map((point, index) => `${index * step},${100 - point}`)
    .join(" ");
}

function buildWindowRange(series, window) {
  if (!series?.length || !window) {
    return null;
  }

  const startIndex = series.findIndex((point) => point.date >= window.start_date);
  let endIndex = -1;
  for (let index = series.length - 1; index >= 0; index -= 1) {
    if (series[index].date <= window.end_date) {
      endIndex = index;
      break;
    }
  }

  if (startIndex === -1 || endIndex === -1 || endIndex < startIndex) {
    return null;
  }

  return { startIndex, endIndex };
}

function buildHeroChartModel(series, selectedWindow, effectiveWindow = null) {
  if (!series?.length) {
    return { empty: true, points: [] };
  }

  const width = 760;
  const height = 240;
  const padding = { top: 14, right: 16, bottom: 26, left: 16 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;

  const closes = series.map((point) => point.close);
  const rawMin = Math.min(...closes);
  const rawMax = Math.max(...closes);
  const buffer = Math.max((rawMax - rawMin) * 0.08, rawMax * 0.01, 1);
  const minClose = rawMin - buffer;
  const maxClose = rawMax + buffer;
  const closeSpan = maxClose - minClose || 1;

  const xForIndex = (index) => {
    if (series.length === 1) {
      return padding.left + innerWidth / 2;
    }
    return padding.left + (index / (series.length - 1)) * innerWidth;
  };

  const yForClose = (close) => padding.top + ((maxClose - close) / closeSpan) * innerHeight;

  const points = series.map((point, index) => ({
    ...point,
    index,
    x: xForIndex(index),
    y: yForClose(point.close),
  }));

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  return {
    empty: false,
    points,
    width,
    height,
    padding,
    innerWidth,
    selectedRange: buildWindowRange(series, selectedWindow),
    effectiveRange: buildWindowRange(series, effectiveWindow),
    linePath,
  };
}

function modeLabel(mode) {
  return mode.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase());
}

function backendLabel(searchMode) {
  if (searchMode === "vqvae") {
    return "Trained VQ-VAE";
  }
  if (searchMode === "economic_live") {
    return "Live Macro + Price Factors";
  }
  if (searchMode === "social_mvp") {
    return "Proxy Social Signal Blend";
  }
  if (searchMode === "social_live") {
    return "Finnhub + NewsAPI + FinBERT";
  }
  return "Live Search";
}

function confidenceTone(score) {
  if (score >= 0.9) {
    return "High";
  }
  if (score >= 0.75) {
    return "Strong";
  }
  if (score >= 0.6) {
    return "Moderate";
  }
  return "Weak";
}

function formatDateTime(value) {
  if (!value) {
    return "";
  }
  return new Date(value).toLocaleString();
}

function buildHeroIdentity(hero) {
  if (!hero) {
    return "No hero selected";
  }
  if (hero.name && hero.name !== hero.ticker) {
    return `${hero.name} (${hero.ticker})`;
  }
  return hero.ticker;
}

function LandingPreviewChart() {
  const canvasRef = useRef(null);

  useEffect(() => {
    function drawChart() {
      const canvas = canvasRef.current;
      if (!canvas) {
        return;
      }

      const rect = canvas.getBoundingClientRect();
      const width = Math.max(Math.round(rect.width), 320);
      const height = Math.max(Math.round(rect.height), 220);
      const ratio = window.devicePixelRatio || 1;

      canvas.width = width * ratio;
      canvas.height = height * ratio;

      const context = canvas.getContext("2d");
      context.setTransform(1, 0, 0, 1, 0, 0);
      context.scale(ratio, ratio);
      context.clearRect(0, 0, width, height);

      const gradient = context.createLinearGradient(0, 0, 0, height);
      gradient.addColorStop(0, "rgba(87, 213, 176, 0.32)");
      gradient.addColorStop(1, "rgba(87, 213, 176, 0.02)");

      context.strokeStyle = "rgba(151, 180, 255, 0.12)";
      context.lineWidth = 1;
      for (let index = 0; index < 5; index += 1) {
        const y = 20 + ((height - 40) / 4) * index;
        context.beginPath();
        context.moveTo(0, y);
        context.lineTo(width, y);
        context.stroke();
      }

      const min = Math.min(...landingPreviewSeries);
      const max = Math.max(...landingPreviewSeries);
      const span = max - min || 1;
      const leftPad = 10;
      const rightPad = 10;
      const topPad = 18;
      const bottomPad = 24;
      const usableWidth = width - leftPad - rightPad;
      const usableHeight = height - topPad - bottomPad;

      const points = landingPreviewSeries.map((value, index) => ({
        x: leftPad + (usableWidth / (landingPreviewSeries.length - 1)) * index,
        y: topPad + ((max - value) / span) * usableHeight,
      }));

      context.beginPath();
      points.forEach((point, index) => {
        if (index === 0) {
          context.moveTo(point.x, point.y);
        } else {
          context.lineTo(point.x, point.y);
        }
      });
      context.lineTo(points[points.length - 1].x, height - bottomPad + 4);
      context.lineTo(points[0].x, height - bottomPad + 4);
      context.closePath();
      context.fillStyle = gradient;
      context.fill();

      context.beginPath();
      points.forEach((point, index) => {
        if (index === 0) {
          context.moveTo(point.x, point.y);
        } else {
          context.lineTo(point.x, point.y);
        }
      });
      context.strokeStyle = "#66f0cb";
      context.lineWidth = 3;
      context.lineJoin = "round";
      context.lineCap = "round";
      context.stroke();

      const finalPoint = points[points.length - 1];
      context.beginPath();
      context.arc(finalPoint.x, finalPoint.y, 5, 0, Math.PI * 2);
      context.fillStyle = "#f7fafc";
      context.fill();
      context.lineWidth = 2;
      context.strokeStyle = "#66f0cb";
      context.stroke();
    }

    drawChart();
    window.addEventListener("resize", drawChart);
    return () => window.removeEventListener("resize", drawChart);
  }, []);

  return <canvas ref={canvasRef} id="landing-chart" className="preview-chart" aria-label="MirrorQuant landing chart" />;
}

function Sparkline({ series, fallbackLabel }) {
  const values = series?.length
    ? normalizeSeriesToSparkline(series.map((point) => point.close))
    : sparklineValues(fallbackLabel, fallbackLabel);
  const points = sparklinePoints(values);

  return (
    <svg className="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <polyline className="sparkline-line" points={points}></polyline>
    </svg>
  );
}

function HeroChart({ series, selectedWindow, effectiveWindow }) {
  const overlayRef = useRef(null);
  const chartModel = buildHeroChartModel(series || [], selectedWindow, effectiveWindow);
  const [tooltip, setTooltip] = useState({ hidden: true });

  if (chartModel.empty) {
    return <div className="hero-chart-empty">No price history available.</div>;
  }

  function updateTooltip(event) {
    const overlay = overlayRef.current;
    if (!overlay) {
      return;
    }

    const overlayRect = overlay.getBoundingClientRect();
    const relativeX = clamp(event.clientX - overlayRect.left, 0, overlayRect.width);
    const progress = relativeX / Math.max(overlayRect.width, 1);
    const pointIndex = clamp(
      Math.round(progress * (chartModel.points.length - 1)),
      0,
      chartModel.points.length - 1,
    );
    const point = chartModel.points[pointIndex];
    const inSelectedWindow = point.date >= selectedWindow.start_date && point.date <= selectedWindow.end_date;
    const inEffectiveWindow = effectiveWindow
      && point.date >= effectiveWindow.start_date
      && point.date <= effectiveWindow.end_date;

    const shellRect = overlay.parentElement.getBoundingClientRect();
    const left = clamp(event.clientX - shellRect.left + 12, 8, shellRect.width - 168);
    const top = clamp(event.clientY - shellRect.top - 72, 8, shellRect.height - 72);

    setTooltip({
      hidden: false,
      left,
      top,
      point,
      inSelectedWindow,
      inEffectiveWindow,
    });
  }

  function clearTooltip() {
    setTooltip({ hidden: true });
  }

  function renderRange(range, className) {
    if (!range) {
      return null;
    }
    const startX = chartModel.points[range.startIndex].x;
    const endX = chartModel.points[range.endIndex].x;
    const width = Math.max(endX - startX, 2);

    return (
      <rect
        className={className}
        x={startX.toFixed(2)}
        y={chartModel.padding.top}
        width={width.toFixed(2)}
        height={chartModel.height - chartModel.padding.top - chartModel.padding.bottom}
      ></rect>
    );
  }

  function renderBoundaries(range, className) {
    if (!range) {
      return null;
    }

    return [range.startIndex, range.endIndex].map((index) => {
      const x = chartModel.points[index].x;
      return (
        <line
          key={`${className}-${index}`}
          className={className}
          x1={x.toFixed(2)}
          y1={chartModel.padding.top}
          x2={x.toFixed(2)}
          y2={(chartModel.height - chartModel.padding.bottom).toFixed(2)}
        ></line>
      );
    });
  }

  const focusVisible = !tooltip.hidden && tooltip.point;

  return (
    <>
      <svg
        id="hero-chart-svg"
        className="hero-chart-svg"
        viewBox={`0 0 ${chartModel.width} ${chartModel.height}`}
        preserveAspectRatio="none"
        aria-label="Hero stock price chart"
      >
        {Array.from({ length: 4 }, (_, index) => {
          const y = chartModel.padding.top + ((chartModel.height - chartModel.padding.top - chartModel.padding.bottom) / 3) * index;
          return (
            <line
              key={`grid-${index}`}
              className="hero-chart-grid"
              x1={chartModel.padding.left}
              y1={y.toFixed(2)}
              x2={(chartModel.width - chartModel.padding.right).toFixed(2)}
              y2={y.toFixed(2)}
            ></line>
          );
        })}
        {renderRange(chartModel.selectedRange, "hero-chart-range")}
        {renderRange(chartModel.effectiveRange, "hero-chart-effective-range")}
        {renderBoundaries(chartModel.selectedRange, "hero-chart-boundary")}
        {renderBoundaries(chartModel.effectiveRange, "hero-chart-effective-boundary")}
        <path className="hero-chart-line" d={chartModel.linePath}></path>
        <line
          className="hero-chart-focus-line"
          x1={focusVisible ? tooltip.point.x : 0}
          y1={chartModel.padding.top}
          x2={focusVisible ? tooltip.point.x : 0}
          y2={chartModel.height - chartModel.padding.bottom}
          hidden={!focusVisible}
        ></line>
        <circle
          className="hero-chart-focus-dot"
          cx={focusVisible ? tooltip.point.x : 0}
          cy={focusVisible ? tooltip.point.y : 0}
          r="4"
          hidden={!focusVisible}
        ></circle>
        <rect
          ref={overlayRef}
          className="hero-chart-overlay"
          x={chartModel.padding.left}
          y={chartModel.padding.top}
          width={chartModel.innerWidth}
          height={chartModel.height - chartModel.padding.top - chartModel.padding.bottom}
          onMouseMove={updateTooltip}
          onMouseEnter={updateTooltip}
          onMouseLeave={clearTooltip}
        ></rect>
      </svg>
      {!tooltip.hidden && tooltip.point ? (
        <div className="hero-chart-tooltip" style={{ left: tooltip.left, top: tooltip.top }}>
          <strong>{tooltip.point.date}</strong>
          <span>Close: {tooltip.point.close.toFixed(2)}</span>
          {tooltip.inSelectedWindow ? <span>Inside selected window</span> : null}
          {tooltip.inEffectiveWindow ? <span>Inside encoded model window</span> : null}
        </div>
      ) : null}
    </>
  );
}

function HeroCard({ hero, run, heroSeries }) {
  if (!hero) {
    return (
      <div className="card">
        <p>Save a hero window to get started.</p>
      </div>
    );
  }

  const selectedWindow = run?.selected_window || {
    start_date: hero.start_date,
    end_date: hero.end_date,
  };
  const effectiveWindow = run?.effective_hero_window || null;
  const mode = run?.mode || "price_dna";
  const dna = run?.hero?.[mode] || hero?.[mode] || { confidence: 0, regime_code: "N/A", traits: [] };
  const requestedLabel = `${selectedWindow.start_date} to ${selectedWindow.end_date}`;
  const encodedLabel = effectiveWindow
    ? `${effectiveWindow.start_date} to ${effectiveWindow.end_date} (${effectiveWindow.window_size} trading-day model window)`
    : requestedLabel;
  const historyLabel = heroSeries?.available_start_date && heroSeries?.available_end_date
    ? `${heroSeries.available_start_date} to ${heroSeries.available_end_date}`
    : requestedLabel;
  const confidencePercent = typeof dna.confidence === "number"
    ? `${Math.round(dna.confidence * 100)}%`
    : "N/A";

  let backendNote = null;
  if (run?.search_backend === "vqvae") {
    backendNote = "Using trained VQ-VAE Price DNA encoding.";
  } else if (run?.search_backend === "economic_live") {
    backendNote = "Using live macro plus price-window factor matching.";
  } else if (run?.search_backend === "social_live") {
    backendNote = "Using Finnhub company news, NewsAPI article discovery, and FinBERT sentiment scoring aggregated into daily social signals.";
  } else if (run?.search_backend === "social_mvp") {
    backendNote = "Using local Social DNA proxy signals built from ticker narrative profiles and price-persistence features.";
  }

  return (
    <div className="card hero-card">
      <h3>{buildHeroIdentity(run?.hero || hero)}</h3>
      <p className="meta">{hero.title || hero.window_label || "Saved hero window"}</p>
      <div className="hero-chart-shell">
        <HeroChart
          series={heroSeries?.series || []}
          selectedWindow={selectedWindow}
          effectiveWindow={effectiveWindow}
        />
      </div>
      <div className="hero-chart-legend">
        <span><i className="legend-swatch legend-swatch-selected"></i>Selected window</span>
        {effectiveWindow ? (
          <span><i className="legend-swatch legend-swatch-effective"></i>Encoded model window</span>
        ) : null}
      </div>
      <p className="meta">Selected window: {requestedLabel}</p>
      <p className="meta">Available history: {historyLabel}</p>
      <p>{hero.summary || "User-defined hero window."}</p>
      {run ? (
        <>
          <div className="metric-row">
            <div>
              <span className="mini-label">Confidence</span>
              <p className="score">{confidencePercent}</p>
            </div>
            <div>
              <span className="mini-label">Regime Code</span>
              <p className="metric-value">{dna.regime_code || "N/A"}</p>
            </div>
          </div>
          <p className="meta">Encoded slice: {encodedLabel}</p>
          {backendNote ? <p className="meta">{backendNote}</p> : null}
          <div>{traitPills(dna.traits || [])}</div>
        </>
      ) : (
        <p className="meta">Run a DNA search to generate a saved result snapshot.</p>
      )}
    </div>
  );
}

function App({ initialView = "landing", onEnterPlatform = null, onShowLanding = null }) {
  const [showApp, setShowApp] = useState(initialView === "workspace");
  const [activeWorkspaceSection, setActiveWorkspaceSection] = useState("workspace-command-center");
  const [savedHeroes, setSavedHeroes] = useState([]);
  const [currentHero, setCurrentHero] = useState(null);
  const [currentSearchRuns, setCurrentSearchRuns] = useState([]);
  const [currentSearchRun, setCurrentSearchRun] = useState(null);
  const [heroSeries, setHeroSeries] = useState(null);
  const [industryChain, setIndustryChain] = useState({ ticker: "No hero", relationships: [] });
  const [marketWatch, setMarketWatch] = useState(null);
  const [heroStatus, setHeroStatus] = useState("No saved hero selected.");
  const [loadingCreate, setLoadingCreate] = useState(false);
  const [loadingRun, setLoadingRun] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [authMode, setAuthMode] = useState("login");
  const [authError, setAuthError] = useState("");
  const [verificationNotice, setVerificationNotice] = useState("");
  const [verificationLink, setVerificationLink] = useState("");
  const [verificationLoading, setVerificationLoading] = useState(false);
  const [form, setForm] = useState({
    ticker: "",
    title: "",
    mode: "price_dna",
    start_date: "",
    end_date: "",
  });
  const [loginForm, setLoginForm] = useState({
    email: "",
    password: "",
    confirm_password: "",
  });
  const initPromiseRef = useRef(null);

  function resetWorkspaceState() {
    setSavedHeroes([]);
    setCurrentHero(null);
    setCurrentSearchRuns([]);
    setCurrentSearchRun(null);
    setHeroSeries(null);
    setIndustryChain({ ticker: "No hero", relationships: [] });
    setMarketWatch(null);
    setHeroStatus("No saved hero selected.");
    initPromiseRef.current = null;
  }

  useEffect(() => {
    async function loadCurrentUser() {
      try {
        const data = await fetchCurrentUser();
        setCurrentUser(data.user);
      } catch (error) {
        setCurrentUser(null);
      } finally {
        setAuthLoading(false);
      }
    }

    loadCurrentUser();
  }, []);

  useEffect(() => {
    document.body.classList.toggle("landing-active", !showApp);
    return () => document.body.classList.remove("landing-active");
  }, [showApp]);

  useEffect(() => {
    if (!showApp) {
      return undefined;
    }

    const sections = workspaceSidebarItems
      .map((item) => document.getElementById(item.id))
      .filter(Boolean);

    if (!sections.length) {
      return undefined;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        const nextActive = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];

        if (nextActive?.target?.id) {
          setActiveWorkspaceSection(nextActive.target.id);
        }
      },
      {
        rootMargin: "-20% 0px -55% 0px",
        threshold: [0.15, 0.35, 0.6],
      },
    );

    sections.forEach((section) => observer.observe(section));
    return () => observer.disconnect();
  }, [showApp]);

  useEffect(() => {
    if (initialView !== "workspace" || authLoading || !currentUser?.is_verified) {
      return;
    }

    enterPlatform().catch((error) => {
      setHeroStatus(error.message);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialView, authLoading, currentUser]);

  function syncFormWithHero(hero) {
    setForm((current) => ({
      ...current,
      ticker: hero.ticker,
      title: hero.title || "",
      start_date: hero.start_date,
      end_date: hero.end_date,
    }));
  }

  function buildHeroPayloadFromForm() {
    return {
      ticker: form.ticker.trim().toUpperCase(),
      title: form.title.trim() || null,
      start_date: form.start_date,
      end_date: form.end_date,
      notes: null,
    };
  }

  function currentHeroDiffersFromForm() {
    if (!currentHero) {
      return true;
    }

    const payload = buildHeroPayloadFromForm();
    return (
      payload.ticker !== currentHero.ticker
      || payload.title !== (currentHero.title || null)
      || payload.start_date !== currentHero.start_date
      || payload.end_date !== currentHero.end_date
    );
  }

  async function fetchHeroSeries(hero) {
    return fetchJson(
      `/api/price-series?ticker=${hero.ticker}&start_date=${hero.start_date}&end_date=${hero.end_date}`,
    );
  }

  async function loadIndustryChain(ticker) {
    try {
      return await fetchJson(`/api/industry-chain/${ticker}`);
    } catch {
      return { ticker, relationships: [] };
    }
  }

  async function loadSearchRun(searchRunId, options = {}) {
    const run = await fetchJson(`/api/search-runs/${searchRunId}`);
    let activeHero = options.hero || currentHero;

    if (!activeHero || activeHero.id !== run.hero_id) {
      activeHero = await fetchJson(`/api/heroes/${run.hero_id}`);
      setCurrentHero(activeHero);
      syncFormWithHero(activeHero);
    }

    const nextHeroSeries = options.heroSeries || await fetchHeroSeries(activeHero);
    const nextChain = options.chainData || await loadIndustryChain(activeHero.ticker);

    setCurrentSearchRun(run);
    setHeroSeries(nextHeroSeries);
    setIndustryChain(nextChain);
    setForm((current) => ({ ...current, mode: run.mode }));
    return run;
  }

  async function selectHero(heroId) {
    const hero = await fetchJson(`/api/heroes/${heroId}`);
    setCurrentHero(hero);
    syncFormWithHero(hero);
    setHeroStatus(`Active hero: ${hero.title || buildHeroIdentity(hero)}`);

    const [searchRunData, nextHeroSeries, nextChain] = await Promise.all([
      fetchJson(`/api/heroes/${heroId}/search-runs`),
      fetchHeroSeries(hero),
      loadIndustryChain(hero.ticker),
    ]);

    setCurrentSearchRuns(searchRunData.search_runs);
    setHeroSeries(nextHeroSeries);
    setIndustryChain(nextChain);

    if (searchRunData.search_runs.length) {
      await loadSearchRun(searchRunData.search_runs[0].id, {
        hero,
        heroSeries: nextHeroSeries,
        chainData: nextChain,
      });
      return;
    }

    setCurrentSearchRun(null);
  }

  async function loadSavedHeroes(preferredHeroId = null) {
    const data = await fetchJson("/api/heroes");
    setSavedHeroes(data.heroes);

    if (!data.heroes.length) {
      setCurrentHero(null);
      setCurrentSearchRun(null);
      setCurrentSearchRuns([]);
      setHeroSeries(null);
      setIndustryChain({ ticker: "No hero", relationships: [] });
      setHeroStatus("No saved hero selected.");
      return;
    }

    const heroToSelect = preferredHeroId || currentHero?.id || data.heroes[0]?.id;
    if (heroToSelect) {
      await selectHero(heroToSelect);
    }
  }

  async function createHeroFromForm() {
    const payload = buildHeroPayloadFromForm();
    if (!payload.ticker || !payload.start_date || !payload.end_date) {
      throw new Error("Ticker, start date, and end date are required.");
    }

    const hero = await postJson("/api/heroes", payload);
    await loadSavedHeroes(hero.id);
    return hero;
  }

  async function ensureCurrentHero() {
    if (!currentHero || currentHeroDiffersFromForm()) {
      return createHeroFromForm();
    }
    return currentHero;
  }

  async function initDashboard() {
    setHeroStatus("Loading saved MirrorQuant workspace...");
    const watchData = await fetchJson("/api/market-watch");
    setMarketWatch(watchData);
    await loadSavedHeroes();
  }

  async function enterPlatform(nextUser = null) {
    if (onEnterPlatform) {
      onEnterPlatform();
      return;
    }
    setShowApp(true);
    const activeUser = nextUser || currentUser;
    if (!activeUser || !activeUser.is_verified) {
      return;
    }
    if (!initPromiseRef.current) {
      initPromiseRef.current = initDashboard().catch((error) => {
        initPromiseRef.current = null;
        throw error;
      });
    }
    try {
      await initPromiseRef.current;
    } catch (error) {
      setHeroStatus(error.message);
    }
  }

  function switchAuthMode(nextMode) {
    setAuthMode(nextMode);
    setAuthError("");
    setVerificationNotice("");
    setVerificationLink("");
    setLoginForm((current) => ({
      ...current,
      password: "",
      confirm_password: "",
    }));
  }

  async function handleAuthSubmit(event) {
    event.preventDefault();
    setAuthError("");
    setVerificationNotice("");
    setVerificationLink("");

    try {
      const payload = {
        email: loginForm.email,
        password: loginForm.password,
      };
      const data = authMode === "register"
        ? await registerUser({
          ...payload,
          confirm_password: loginForm.confirm_password,
        })
        : await loginUser(payload);
      setCurrentUser(data.user);
      if (authMode === "register") {
        setVerificationNotice(
          data.verification_delivery === "smtp"
            ? "Verification email sent. Open your inbox, then come back here."
            : "Verification email is in local dev mode. Use the link below to verify this account."
        );
        setVerificationLink(data.verification_url || "");
      }
      setLoginForm({
        email: loginForm.email,
        password: "",
        confirm_password: "",
      });
    } catch (error) {
      setAuthError(error.message);
    }
  }

  async function handleRefreshSession() {
    setVerificationLoading(true);
    setAuthError("");
    try {
      const data = await fetchCurrentUser();
      setCurrentUser(data.user);
      if (data.user?.is_verified) {
        setVerificationNotice("Email verified. Your workspace is ready.");
        setVerificationLink("");
        await enterPlatform(data.user);
      } else {
        setVerificationNotice("This account is still waiting for verification. Open the email link first, then try again.");
      }
    } catch (error) {
      setAuthError(error.message);
    } finally {
      setVerificationLoading(false);
    }
  }

  async function handleResendVerification() {
    setVerificationLoading(true);
    setAuthError("");
    try {
      const data = await resendVerificationEmail();
      setCurrentUser(data.user);
      if (data.already_verified) {
        setVerificationNotice("This account is already verified.");
        setVerificationLink("");
        await enterPlatform(data.user);
      } else {
        setVerificationNotice(
          data.verification_delivery === "smtp"
            ? "Verification email sent again. Check your inbox."
            : "Local dev verification link generated again. Open the link below."
        );
        setVerificationLink(data.verification_url || "");
      }
    } catch (error) {
      setAuthError(error.message);
    } finally {
      setVerificationLoading(false);
    }
  }

  async function handleLogout() {
    setAuthError("");
    setVerificationNotice("");
    setVerificationLink("");
    try {
      await logoutUser();
    } catch {
      // If logout fails, still clear local state so the user can recover.
    } finally {
      setCurrentUser(null);
      resetWorkspaceState();
      setLoginForm((current) => ({
        ...current,
        password: "",
        confirm_password: "",
      }));
    }
  }

  function showLanding() {
    if (onShowLanding) {
      onShowLanding();
      return;
    }
    setShowApp(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function scrollToWorkspaceSection(sectionId) {
    setActiveWorkspaceSection(sectionId);
    document.getElementById(sectionId)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  async function handleCreateHero() {
    setLoadingCreate(true);
    try {
      const hero = await createHeroFromForm();
      setHeroStatus(`Saved hero ${hero.title || buildHeroIdentity(hero)}.`);
    } catch (error) {
      setHeroStatus(error.message);
    } finally {
      setLoadingCreate(false);
    }
  }

  async function handleRunSearch() {
    setLoadingRun(true);
    try {
      const hero = await ensureCurrentHero();
      const run = await postJson(`/api/heroes/${hero.id}/search-runs`, {
        mode: form.mode,
      });

      const [searchRunData, nextHeroSeries, nextChain] = await Promise.all([
        fetchJson(`/api/heroes/${hero.id}/search-runs`),
        fetchHeroSeries(hero),
        loadIndustryChain(hero.ticker),
      ]);

      setCurrentSearchRuns(searchRunData.search_runs);
      setHeroSeries(nextHeroSeries);
      setIndustryChain(nextChain);
      setCurrentSearchRun(run);
      setHeroStatus(`Saved ${modeLabel(run.mode)} search for ${hero.title || buildHeroIdentity(hero)}.`);
    } catch (error) {
      setHeroStatus(error.message);
    } finally {
      setLoadingRun(false);
    }
  }

  async function handleArchiveHero() {
    if (!currentHero) {
      setHeroStatus("Select a hero before archiving.");
      return;
    }

    try {
      await postJson(`/api/heroes/${currentHero.id}/archive`, {});
      await loadSavedHeroes();
      setHeroStatus(`Archived hero ${currentHero.title || buildHeroIdentity(currentHero)}.`);
    } catch (error) {
      setHeroStatus(error.message);
    }
  }

  const summaryMode = currentSearchRun ? modeLabel(currentSearchRun.mode) : "Awaiting run";
  const summaryBackend = currentSearchRun
    ? backendLabel(currentSearchRun.search_backend)
    : currentHero
      ? "Ready to search"
      : "No active hero";
  const summaryHeroRegime = currentSearchRun
    ? currentSearchRun.hero_regime_code || currentSearchRun.hero?.[currentSearchRun.mode]?.regime_code || "N/A"
    : currentHero
      ? currentHero.ticker
      : "N/A";
  const summaryWindow = currentSearchRun?.effective_hero_window
    ? `${currentSearchRun.effective_hero_window.start_date} to ${currentSearchRun.effective_hero_window.end_date}`
    : currentSearchRun?.selected_window
      ? `${currentSearchRun.selected_window.start_date} to ${currentSearchRun.selected_window.end_date}`
      : currentHero
        ? `${currentHero.start_date} to ${currentHero.end_date}`
        : "N/A";
  const heroCount = savedHeroes.length;
  const runCount = currentSearchRuns.length;
  const topMatch = currentSearchRun?.matches?.[0] || null;
  const activeHeroLabel = currentHero ? buildHeroIdentity(currentHero) : "No hero selected";
  const activeModeLabel = form.mode ? modeLabel(form.mode) : "Price DNA";
  const regimeHeadline = marketWatch?.headline_regime || "Loading regime";
  const topMatchLabel = topMatch
    ? `${topMatch.ticker} ${Math.round(topMatch.score * 100)}%`
    : "No saved match";
  const sidebarSnapshotTitle = topMatch
    ? "Snapshot ready"
    : currentHero
      ? "Hero armed"
      : "Awaiting setup";
  const sidebarSnapshotMeta = currentSearchRun
    ? `${summaryMode} · ${summaryBackend}`
    : currentHero
      ? `${activeHeroLabel} ready for search`
      : "Save a hero window to arm the workspace.";
  const sidebarSnapshotValue = topMatch
    ? topMatchLabel
    : `${heroCount} saved hero${heroCount === 1 ? "" : "es"}`;
  const sidebarSnapshotFootnote = `${runCount} saved run${runCount === 1 ? "" : "s"} in workspace`;

  if (showApp && authLoading) {
    return (
      <main className="page auth-shell">
        <section className="panel auth-card">
          <p className="app-eyebrow">MirrorQuant workspace</p>
          <h1 className="auth-title">Checking your session...</h1>
          <p className="panel-kicker">Loading your internal research workspace.</p>
        </section>
      </main>
    );
  }

  if (showApp && !currentUser) {
    const isRegisterMode = authMode === "register";
    return (
      <main className="page auth-shell">
        <section className="panel auth-card">
          <p className="app-eyebrow">Internal Access</p>
          <h1 className="auth-title">
            {isRegisterMode ? "Create your MirrorQuant account" : "Log in to MirrorQuant"}
          </h1>
          <p className="panel-kicker">
            {isRegisterMode
              ? "Create an account to save hero windows, persist search runs, and reopen your workspace later."
              : "Use your account to open the saved hero workspace and search history."}
          </p>
          <div className="auth-mode-toggle" role="tablist" aria-label="Authentication mode">
            <button
              type="button"
              className={`auth-mode-button ${!isRegisterMode ? "is-active" : ""}`}
              onClick={() => switchAuthMode("login")}
            >
              Log in
            </button>
            <button
              type="button"
              className={`auth-mode-button ${isRegisterMode ? "is-active" : ""}`}
              onClick={() => switchAuthMode("register")}
            >
              Create account
            </button>
          </div>
          <form className="auth-form" onSubmit={handleAuthSubmit}>
            <div className="control-field">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                placeholder="local-dev@mirrorquant.app"
                value={loginForm.email}
                onChange={(event) =>
                  setLoginForm((current) => ({
                    ...current,
                    email: event.target.value,
                  }))
                }
              />
            </div>
            <div className="control-field">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                placeholder="Enter password"
                value={loginForm.password}
                onChange={(event) =>
                  setLoginForm((current) => ({
                    ...current,
                    password: event.target.value,
                  }))
                }
              />
            </div>
            {isRegisterMode ? (
              <div className="control-field">
                <label htmlFor="register-confirm-password">Confirm password</label>
                <input
                  id="register-confirm-password"
                  type="password"
                  placeholder="Re-enter password"
                  value={loginForm.confirm_password}
                  onChange={(event) =>
                    setLoginForm((current) => ({
                      ...current,
                      confirm_password: event.target.value,
                    }))
                  }
                />
              </div>
            ) : null}
            <div className="auth-actions">
              <button type="submit">{isRegisterMode ? "Create account" : "Log in"}</button>
              <button type="button" className="secondary-button" onClick={showLanding}>
                Back To Landing
              </button>
            </div>
            {authError ? <p className="auth-error">{authError}</p> : null}
          </form>
        </section>
      </main>
    );
  }

  if (showApp && currentUser && !currentUser.is_verified) {
    return (
      <main className="page auth-shell">
        <section className="panel auth-card">
          <p className="app-eyebrow">Verify Email</p>
          <h1 className="auth-title">Check your inbox for {currentUser.email}</h1>
          <p className="panel-kicker">
            Verify your email before using saved heroes, search history, and the MirrorQuant workspace.
          </p>
          <div className="auth-form">
            <div className="auth-actions">
              <button type="button" onClick={handleRefreshSession} disabled={verificationLoading}>
                {verificationLoading ? "Refreshing..." : "I already verified"}
              </button>
              <button
                type="button"
                className="secondary-button"
                onClick={handleResendVerification}
                disabled={verificationLoading}
              >
                Resend verification
              </button>
            </div>
            {verificationNotice ? <p className="auth-success">{verificationNotice}</p> : null}
            {verificationLink ? (
              <a className="auth-link" href={verificationLink}>
                Open verification link
              </a>
            ) : null}
            {authError ? <p className="auth-error">{authError}</p> : null}
            <div className="auth-actions">
              <button type="button" className="secondary-button" onClick={handleLogout}>
                Logout
              </button>
              <button type="button" className="secondary-button" onClick={showLanding}>
                Back To Landing
              </button>
            </div>
          </div>
        </section>
      </main>
    );
  }

  return (
    <>
      {!showApp ? (
        <div id="landing-shell" className="landing-shell">
          <nav className="landing-nav">
            <button className="landing-logo" type="button" onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}>
              <span className="landing-logo-mark">MQ</span>
              <span className="landing-logo-copy">
                <strong>MirrorQuant</strong>
                <small>Behavioral market DNA</small>
              </span>
            </button>
            <div className="landing-nav-links">
              <button type="button" onClick={() => document.getElementById("capabilities")?.scrollIntoView({ behavior: "smooth" })}>Capabilities</button>
              <button type="button" onClick={() => document.getElementById("workflow")?.scrollIntoView({ behavior: "smooth" })}>Workflow</button>
              <button type="button" onClick={() => document.getElementById("launch")?.scrollIntoView({ behavior: "smooth" })}>Launch</button>
            </div>
            <button className="landing-nav-cta" type="button" onClick={enterPlatform}>Enter Platform</button>
          </nav>

          <div className="landing-ticker-wrap">
            <div className="landing-ticker-inner">
              {[...landingTickerItems, ...landingTickerItems].map((item, index) => (
                <span key={`${item}-${index}`} className="landing-ticker-item">{item}</span>
              ))}
            </div>
          </div>

          <section id="top" className="landing-hero">
            <div className="landing-copy fade-up is-visible">
              <div className="landing-eyebrow">
                <span className="landing-eyebrow-dot"></span>
                Productized quant discovery workflow
              </div>
              <h1 className="landing-title">
                Find stocks that express the same
                {" "}
                <em>behavioral DNA</em>
                {" "}
                as your best idea.
              </h1>
              <p className="landing-sub">
                MirrorQuant lets you save any ticker window as a hero, run Price, Economic,
                or Social DNA searches on demand, and come back later to the exact ranked
                result snapshot that generated the idea.
              </p>
              <div className="landing-actions">
                <button className="landing-btn landing-btn-primary" type="button" onClick={enterPlatform}>
                  Open MirrorQuant
                </button>
                <button
                  className="landing-btn landing-btn-ghost"
                  type="button"
                  onClick={() => document.getElementById("workflow")?.scrollIntoView({ behavior: "smooth" })}
                >
                  See how it works
                </button>
              </div>
            </div>

            <div className="landing-preview fade-up delay-2 is-visible">
              <div className="preview-card">
                <div className="preview-header">
                  <div>
                    <div className="preview-label">Saved hero</div>
                    <div className="preview-title">MSFT · 2023-01-03 to 2023-04-03</div>
                    <div className="preview-note">Encoded through the Price DNA engine</div>
                  </div>
                  <div className="preview-badges">
                    <span className="preview-badge preview-badge-live">Price DNA</span>
                    <span className="preview-badge preview-badge-soft">Saved run</span>
                  </div>
                </div>
                <LandingPreviewChart />
                <div className="preview-stats">
                  <div className="preview-stat">
                    <label>Search modes</label>
                    <span>3 engines</span>
                  </div>
                  <div className="preview-stat">
                    <label>Model window</label>
                    <span>40 trading days</span>
                  </div>
                  <div className="preview-stat">
                    <label>Return shape</label>
                    <span>Breakout profile</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <section className="landing-metrics">
            <div className="landing-metrics-inner">
              {landingMetrics.map((metric, index) => (
                <div key={metric.label} className={`landing-metric fade-up delay-${Math.min(index, 3)} is-visible`}>
                  <div className="landing-metric-number">{metric.value}</div>
                  <div className="landing-metric-label">{metric.label}</div>
                </div>
              ))}
            </div>
          </section>

          <section id="capabilities" className="landing-section">
            <div className="landing-section-head fade-up is-visible">
              <div>
                <div className="landing-section-label">Platform capabilities</div>
                <h2 className="landing-section-title">Built for discovery, recall, and explainability.</h2>
              </div>
              <p className="landing-section-sub">
                MirrorQuant is not just a chart toy. It is a workflow for storing hero ideas,
                running multiple search lenses, and reopening the exact evidence later.
              </p>
            </div>

            <div className="landing-feature-grid">
              {capabilityCards.map((card, index) => (
                <article
                  key={card.title}
                  className={`landing-feature-card fade-up ${index % 3 === 1 ? "delay-1" : index % 3 === 2 ? "delay-2" : ""} is-visible`}
                >
                  <div className="landing-feature-icon">{card.icon}</div>
                  <h3>{card.title}</h3>
                  <p>{card.copy}</p>
                </article>
              ))}
            </div>
          </section>

          <section id="workflow" className="landing-workflow">
            <div className="landing-workflow-copy fade-up is-visible">
              <div className="landing-section-label">Core workflow</div>
              <h2 className="landing-section-title">From hero idea to saved result in two API calls.</h2>
              <p className="landing-section-sub">
                The product flow is simple on purpose: create a hero, run a search mode,
                then reopen the saved run later from history.
              </p>
              <div className="landing-checks">
                <div><span>01</span> Save a hero from any ticker and date range.</div>
                <div><span>02</span> Run Price, Economic, or Social DNA against that hero.</div>
                <div><span>03</span> Reopen the exact ranked run from saved history.</div>
              </div>
            </div>

            <div className="landing-code-card fade-up delay-2 is-visible">
              <div className="landing-code-line"><span className="landing-code-ln">1</span><span><span className="landing-code-kw">const</span> hero = <span className="landing-code-kw">await</span> api.post(<span className="landing-code-str">"/api/heroes"</span>, {"{"}</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">2</span><span>&nbsp;&nbsp;ticker: <span className="landing-code-str">"MSFT"</span>,</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">3</span><span>&nbsp;&nbsp;start_date: <span className="landing-code-str">"2023-01-03"</span>,</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">4</span><span>&nbsp;&nbsp;end_date: <span className="landing-code-str">"2023-04-03"</span></span></div>
              <div className="landing-code-line"><span className="landing-code-ln">5</span><span>{"});"}</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">6</span><span></span></div>
              <div className="landing-code-line"><span className="landing-code-ln">7</span><span><span className="landing-code-kw">const</span> run = <span className="landing-code-kw">await</span> api.post(</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">8</span><span>&nbsp;&nbsp;<span className="landing-code-str">`/api/heroes/${"${hero.id}"}/search-runs`</span>,</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">9</span><span>&nbsp;&nbsp;{"{ mode: "}<span className="landing-code-str">"price_dna"</span>{" }"}</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">10</span><span>{");"}</span></div>
              <div className="landing-code-line"><span className="landing-code-ln">11</span><span></span></div>
              <div className="landing-code-line"><span className="landing-code-ln">12</span><span><span className="landing-code-cm">// reopen later:</span></span></div>
              <div className="landing-code-line"><span className="landing-code-ln">13</span><span><span className="landing-code-kw">const</span> savedRun = <span className="landing-code-kw">await</span> api.get(<span className="landing-code-str">`/api/search-runs/${"${run.id}"}`</span>);</span></div>
            </div>
          </section>

          <section id="launch" className="landing-cta-section fade-up is-visible">
            <div className="landing-cta-box">
              <div className="landing-eyebrow landing-eyebrow-inline">
                <span className="landing-eyebrow-dot"></span>
                Main dashboard included
              </div>
              <h2>Ready to open the search workspace?</h2>
              <p>
                Enter the platform to save hero windows, run DNA searches, inspect market context,
                and reopen prior ranked results.
              </p>
              <div className="landing-actions landing-actions-centered">
                <button className="landing-btn landing-btn-primary" type="button" onClick={enterPlatform}>
                  Enter MirrorQuant
                </button>
                <button
                  className="landing-btn landing-btn-ghost"
                  type="button"
                  onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
                >
                  Back to top
                </button>
              </div>
            </div>
          </section>

          <footer className="landing-footer">
            <p>MirrorQuant turns saved hero windows into reusable market retrieval workflows.</p>
            <div className="landing-footer-links">
              <button type="button" onClick={() => document.getElementById("capabilities")?.scrollIntoView({ behavior: "smooth" })}>Capabilities</button>
              <button type="button" onClick={() => document.getElementById("workflow")?.scrollIntoView({ behavior: "smooth" })}>Workflow</button>
              <button type="button" onClick={enterPlatform}>Open Platform</button>
            </div>
          </footer>
        </div>
      ) : (
        <main id="app-shell" className="page app-shell">
          <section className="app-topbar panel dashboard-topbar">
            <div>
              <p className="app-eyebrow">MirrorQuant workspace</p>
              <h2 className="app-shell-title">Saved heroes, search history, and live DNA retrieval.</h2>
              {currentUser ? <p className="panel-kicker">Signed in as {currentUser.email}</p> : null}
            </div>
            <div className="app-topbar-actions">
              <button type="button" className="secondary-button" onClick={handleLogout}>Logout</button>
              <button type="button" className="secondary-button" onClick={showLanding}>Back To Landing</button>
            </div>
          </section>

          <div className="workspace-frame">
            <aside className="panel workspace-quicklinks" aria-label="Workspace quicklinks">
              <button
                type="button"
                className="workspace-brand"
                onClick={() => scrollToWorkspaceSection("workspace-command-center")}
                aria-label="Jump to MirrorQuant overview"
              >
                <span className="workspace-brand-mark">
                  <Image
                    src="/mirrorquant-logo.png"
                    alt="MirrorQuant logo"
                    width={72}
                    height={72}
                    className="workspace-brand-image"
                  />
                </span>
                <span className="workspace-brand-copy">
                  <strong>MirrorQuant</strong>
                  <small>Discover patterns. See opportunities.</small>
                </span>
              </button>
              <div className="workspace-quicklinks-head">
                <p className="app-eyebrow">Workspace</p>
              </div>
              <nav className="workspace-quicklinks-list" aria-label="Workspace sections">
                {workspaceSidebarItems.map((item) => {
                  const isActive = activeWorkspaceSection === item.id;
                  return (
                    <button
                      key={item.id}
                      type="button"
                      className={`workspace-quicklink ${isActive ? "is-active" : ""}`}
                      onClick={() => scrollToWorkspaceSection(item.id)}
                      aria-current={isActive ? "true" : undefined}
                    >
                      <span className="workspace-quicklink-icon">
                        <WorkspaceSidebarIcon icon={item.icon} />
                      </span>
                      <span className="workspace-quicklink-copy">
                        <strong>{item.label}</strong>
                        <small>{item.detail}</small>
                      </span>
                    </button>
                  );
                })}
              </nav>
              <div className="workspace-quicklinks-footer">
                <div className="workspace-quicklinks-user">
                  <span className="workspace-quicklinks-user-email">{currentUser?.email}</span>
                  <span className="workspace-live-dot" aria-hidden="true"></span>
                </div>
                <article className="workspace-sidebar-card">
                  <p className="workspace-sidebar-card-title">{sidebarSnapshotTitle}</p>
                  <p className="workspace-sidebar-card-copy">{sidebarSnapshotMeta}</p>
                  <strong>{sidebarSnapshotValue}</strong>
                  <span>{sidebarSnapshotFootnote}</span>
                </article>
              </div>
            </aside>

            <div className="workspace-content">
              <section id="workspace-command-center" className="workspace-overview">
                <article className="panel workspace-command">
                  <div className="workspace-command-copy">
                    <p className="app-eyebrow">Production quant dashboard</p>
                    <h1 className="app-title">MirrorQuant</h1>
                    <p className="app-lede">
                      Save a hero window, launch Price, Economic, or Social DNA, and reopen the exact ranked run later.
                    </p>
                  </div>
                  <div className="workspace-command-band">
                    <article className="workspace-band-card">
                      <span className="tile-label">Active hero</span>
                      <strong>{activeHeroLabel}</strong>
                      <p className="meta">Reusable reference window for the next run.</p>
                    </article>
                    <article className="workspace-band-card">
                      <span className="tile-label">Mode armed</span>
                      <strong>{activeModeLabel}</strong>
                      <p className="meta">Selected engine for the next saved search.</p>
                    </article>
                    <article className="workspace-band-card">
                      <span className="tile-label">Top saved match</span>
                      <strong>{topMatchLabel}</strong>
                      <p className="meta">Latest ranked analog from the active run.</p>
                    </article>
                  </div>
                </article>

                <aside className="workspace-overview-side">
                  <article className="app-hero-badge workspace-regime-card">
                    <span>Headline regime</span>
                    <strong>{regimeHeadline}</strong>
                    <p className="meta">Macro tone and market weather around the current tape.</p>
                  </article>
                  <article className="panel workspace-status-card">
                    <div className="workspace-status-head">
                      <p className="app-eyebrow">System status</p>
                      <span className="status-pill">{loadingRun ? "Running" : "Ready"}</span>
                    </div>
                    <p className="workspace-status-copy">{heroStatus}</p>
                    <div className="workspace-status-actions">
                      <button id="create-hero-button" type="button" disabled={loadingCreate || loadingRun} onClick={handleCreateHero}>
                        {loadingCreate ? "Saving..." : "Save Hero"}
                      </button>
                      <button id="run-search-button" type="button" className="secondary-button" disabled={loadingCreate || loadingRun} onClick={handleRunSearch}>
                        {loadingRun ? "Running..." : "Run Search"}
                      </button>
                      <button
                        type="button"
                        className="archive-button"
                        disabled={loadingCreate || loadingRun || !currentHero}
                        onClick={handleArchiveHero}
                      >
                        Archive Hero
                      </button>
                    </div>
                  </article>
                </aside>
              </section>

              <section className="summary-band dashboard-summary-band" aria-label="Active search summary">
                <article className="summary-tile">
                  <span className="tile-label">Active Mode</span>
                  <strong>{summaryMode}</strong>
                </article>
                <article className="summary-tile">
                  <span className="tile-label">Search Engine</span>
                  <strong>{summaryBackend}</strong>
                </article>
                <article className="summary-tile">
                  <span className="tile-label">Hero Regime</span>
                  <strong>{summaryHeroRegime}</strong>
                </article>
                <article className="summary-tile">
                  <span className="tile-label">Encoded Window</span>
                  <strong>{summaryWindow}</strong>
                </article>
                <article className="summary-tile">
                  <span className="tile-label">Saved Heroes</span>
                  <strong>{heroCount}</strong>
                </article>
                <article className="summary-tile">
                  <span className="tile-label">Saved Runs</span>
                  <strong>{runCount}</strong>
                </article>
              </section>

              <section id="workspace-launchpad" className="panel controls workspace-controls">
                <div className="controls-header">
                  <div>
                    <p className="app-eyebrow">Signal launchpad</p>
                    <h2>Configure the next hero window</h2>
                    <p className="panel-kicker">The form below still drives save, search, and archive exactly as before.</p>
                  </div>
                </div>
                <div className="control-field">
                  <label htmlFor="ticker-input">Ticker</label>
                  <input
                    id="ticker-input"
                    type="text"
                    placeholder="AAPL"
                    maxLength="16"
                    value={form.ticker}
                    onChange={(event) => setForm((current) => ({ ...current, ticker: event.target.value }))}
                  />
                </div>
                <div className="control-field">
                  <label htmlFor="title-input">Hero title</label>
                  <input
                    id="title-input"
                    type="text"
                    placeholder="Optional saved label"
                    value={form.title}
                    onChange={(event) => setForm((current) => ({ ...current, title: event.target.value }))}
                  />
                </div>
                <div className="control-field">
                  <label htmlFor="mode-select">DNA mode</label>
                  <select
                    id="mode-select"
                    value={form.mode}
                    onChange={(event) => setForm((current) => ({ ...current, mode: event.target.value }))}
                  >
                    <option value="price_dna">Price DNA</option>
                    <option value="economic_dna">Economic DNA</option>
                    <option value="social_dna">Social DNA</option>
                  </select>
                </div>
                <div className="control-field">
                  <label htmlFor="start-date">Start date</label>
                  <input
                    id="start-date"
                    type="date"
                    value={form.start_date}
                    onChange={(event) => setForm((current) => ({ ...current, start_date: event.target.value }))}
                  />
                </div>
                <div className="control-field">
                  <label htmlFor="end-date">End date</label>
                  <input
                    id="end-date"
                    type="date"
                    value={form.end_date}
                    onChange={(event) => setForm((current) => ({ ...current, end_date: event.target.value }))}
                  />
                </div>
              </section>

              <section className="workspace-grid">
            <div className="workspace-sidebar">
              <article id="workspace-saved-heroes" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Saved Heroes</h2>
                    <p className="panel-kicker">Reusable ticker windows you can reopen and search again.</p>
                  </div>
                </div>
                <div className="stack">
                  {!savedHeroes.length ? (
                    <div className="card"><p>No heroes saved yet. Create one from any ticker and date range.</p></div>
                  ) : (
                    <div className="saved-collection">
                      {savedHeroes.map((hero) => (
                        <button
                          key={hero.id}
                          type="button"
                          className={`saved-item ${currentHero?.id === hero.id ? "is-active" : ""}`}
                          onClick={() => selectHero(hero.id).catch((error) => setHeroStatus(error.message))}
                        >
                          <strong>{hero.title || buildHeroIdentity(hero)}</strong>
                          <span>{buildHeroIdentity(hero)}</span>
                          <p className="meta">{hero.start_date} to {hero.end_date}</p>
                          <p className="meta">Updated {formatDateTime(hero.updated_at)}</p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </article>

              <article id="workspace-search-history" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Search History</h2>
                    <p className="panel-kicker">Saved DNA runs and their top matches for the active hero.</p>
                  </div>
                </div>
                <div className="stack">
                  {!currentHero ? (
                    <div className="card"><p>Select a saved hero to view its search history.</p></div>
                  ) : !currentSearchRuns.length ? (
                    <div className="card"><p>No saved searches for this hero yet. Run one to create a reusable result snapshot.</p></div>
                  ) : (
                    <div className="saved-collection">
                      {currentSearchRuns.map((run) => (
                        <button
                          key={run.id}
                          type="button"
                          className={`saved-item ${currentSearchRun?.id === run.id ? "is-active" : ""}`}
                          onClick={() => loadSearchRun(run.id).catch((error) => setHeroStatus(error.message))}
                        >
                          <strong>{modeLabel(run.mode)}</strong>
                          <span>{backendLabel(run.search_backend)}</span>
                          <p className="meta">{formatDateTime(run.created_at)}</p>
                          <p className="meta">
                            {run.top_match
                              ? `Top match: ${run.top_match.ticker} (${Math.round(run.top_match.score * 100)}%)`
                              : "No top match saved"}
                          </p>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </article>
            </div>

            <div className="workspace-main">
              <article id="workspace-hero-window" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Hero Window</h2>
                    <p className="panel-kicker">The active saved reference window and its latest DNA snapshot.</p>
                  </div>
                </div>
                <div className="stack">
                  <HeroCard hero={currentHero} run={currentSearchRun} heroSeries={heroSeries} />
                </div>
              </article>

              <article id="workspace-mirror-matches" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Mirror Matches</h2>
                    <p className="panel-kicker">Top latent analogs ranked by hidden behavioral similarity.</p>
                  </div>
                </div>
                <div className="stack">
                  {!currentSearchRun?.matches?.length ? (
                    <div className="card"><p>No matches saved for this run yet.</p></div>
                  ) : (
                    currentSearchRun.matches.map((item, index) => {
                      const scorePct = Math.round(item.score * 100);
                      return (
                        <div key={`${item.ticker}-${index}`} className="card match-card">
                          <div className="card-topline">
                            <div className="match-title">
                              <span className="rank-badge">#{index + 1}</span>
                              <div>
                                <h3>{item.name} ({item.ticker})</h3>
                                <p className="meta">{item.sector || "Unknown"}</p>
                              </div>
                            </div>
                            <div className="score-badge">
                              <span className="mini-label">{confidenceTone(item.score)}</span>
                              <strong>{scorePct}%</strong>
                            </div>
                          </div>
                          <p><strong>{item.regime_label}</strong></p>
                          {item.matched_window ? (
                            <p className="meta">
                              Matched window: {item.matched_window.start_date} to {item.matched_window.end_date}
                            </p>
                          ) : null}
                          {item.series?.length ? (
                            <div className="sparkline-shell">
                              <Sparkline series={item.series} fallbackLabel={`${item.ticker}-${index}`} />
                            </div>
                          ) : null}
                          <div className="score-track" aria-hidden="true">
                            <span className="score-fill" style={{ width: `${Math.max(8, Math.min(scorePct, 100))}%` }}></span>
                          </div>
                          <p>{item.explanation}</p>
                        </div>
                      );
                    })
                  )}
                </div>
              </article>
            </div>

            <div className="workspace-context">
              <article id="workspace-market-watch" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Market Watch</h2>
                    <p className="panel-kicker">Macro weather and risk tone around the current regime.</p>
                  </div>
                </div>
                <div className="stack">
                  {!marketWatch ? (
                    <div className="card"><p>Loading market watch...</p></div>
                  ) : (
                    marketWatch.indicators.map((indicator) => (
                      <div key={`${indicator.name}-${indicator.value}`} className="card watch-card">
                        <div className="card-topline">
                          <div>
                            <h3>{indicator.name}</h3>
                            {indicator.symbol ? <p className="meta">{indicator.symbol}</p> : null}
                          </div>
                          <span className="status-pill">{indicator.status}</span>
                        </div>
                        <div className="sparkline-shell">
                          <Sparkline series={indicator.series} fallbackLabel={`${indicator.name}-${indicator.value}`} />
                        </div>
                        <p className="score">{indicator.value}</p>
                        {typeof indicator.change_pct === "number" ? (
                          <p className="meta">
                            Last {indicator.series?.length || 0} sessions: {indicator.change_pct >= 0 ? "+" : ""}{indicator.change_pct}%
                          </p>
                        ) : null}
                        <p>{indicator.insight}</p>
                      </div>
                    ))
                  )}
                </div>
              </article>

              <article id="workspace-industry-chain" className="panel workspace-panel">
                <div className="panel-header">
                  <div>
                    <h2>Industry Chain</h2>
                    <p className="panel-kicker">Why a quant match may still make sense in real-world market structure.</p>
                  </div>
                </div>
                <div className="stack">
                  {!industryChain.relationships?.length ? (
                    <div className="card industry-card">
                      <h3>{industryChain.ticker} industry map</h3>
                      <p className="meta">No saved relationship map exists for this ticker yet.</p>
                    </div>
                  ) : (
                    <div className="card industry-card">
                      <h3>{industryChain.ticker} industry map</h3>
                      <div className="network-grid" aria-hidden="true">
                        {industryChain.relationships.map((item, index) => (
                          <span key={`${item.ticker}-${index}`} className={`network-node node-${(index % 4) + 1}`}></span>
                        ))}
                      </div>
                      <div className="chain-list">
                        {industryChain.relationships.map((item, index) => (
                          <article key={`${item.ticker}-${item.direction}-${index}`} className="chain-item">
                            <div className="card-topline">
                              <strong>{item.ticker}</strong>
                              <span className="status-pill">{item.direction}</span>
                            </div>
                            <p className="meta">{item.relationship}</p>
                            <p>{item.impact}</p>
                          </article>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </article>
            </div>
              </section>
            </div>
          </div>
        </main>
      )}
    </>
  );
}

export default App;
