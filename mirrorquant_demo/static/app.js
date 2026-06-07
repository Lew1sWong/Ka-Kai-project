const tickerInput = document.getElementById("ticker-input");
const titleInput = document.getElementById("title-input");
const modeSelect = document.getElementById("mode-select");
const startDateInput = document.getElementById("start-date");
const endDateInput = document.getElementById("end-date");
const createHeroButton = document.getElementById("create-hero-button");
const runSearchButton = document.getElementById("run-search-button");
const heroStatus = document.getElementById("hero-status");

const savedHeroesPanel = document.getElementById("saved-heroes");
const searchRunsPanel = document.getElementById("search-runs");
const heroCard = document.getElementById("hero-card");
const marketWatch = document.getElementById("market-watch");
const matchesPanel = document.getElementById("matches");
const industryChain = document.getElementById("industry-chain");
const headlineRegime = document.getElementById("headline-regime");
const activeMode = document.getElementById("active-mode");
const searchBackend = document.getElementById("search-backend");
const heroRegime = document.getElementById("hero-regime");
const effectiveWindowLabel = document.getElementById("effective-window");

let savedHeroes = [];
let currentHero = null;
let currentSearchRun = null;
let currentSearchRuns = [];

function traitPills(traits = []) {
  return traits.map((trait) => `<span class="pill">${trait}</span>`).join("");
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

function sparklineSvg(values) {
  if (!values.length) {
    return "";
  }

  const step = 100 / Math.max(values.length - 1, 1);
  const points = values
    .map((point, index) => `${index * step},${100 - point}`)
    .join(" ");

  return `
    <svg class="sparkline" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
      <polyline class="sparkline-line" points="${points}"></polyline>
    </svg>
  `;
}

function seriesSparkline(series, fallbackLabel = "fallback") {
  if (!series?.length) {
    return sparklineSvg(sparklineValues(fallbackLabel, fallbackLabel));
  }

  const closeValues = series.map((point) => point.close);
  return sparklineSvg(normalizeSeriesToSparkline(closeValues));
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
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
    return {
      svg: `<div class="hero-chart-empty">No price history available.</div>`,
      points: [],
    };
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

  const yForClose = (close) => (
    padding.top + ((maxClose - close) / closeSpan) * innerHeight
  );

  const points = series.map((point, index) => ({
    ...point,
    index,
    x: xForIndex(index),
    y: yForClose(point.close),
  }));

  const linePath = points
    .map((point, index) => `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`)
    .join(" ");

  const selectedRange = buildWindowRange(series, selectedWindow);
  const effectiveRange = buildWindowRange(series, effectiveWindow);

  const rangeRect = (range, className) => {
    if (!range) {
      return "";
    }
    const startX = xForIndex(range.startIndex);
    const endX = xForIndex(range.endIndex);
    const rectWidth = Math.max(endX - startX, 2);
    return `
      <rect
        class="${className}"
        x="${startX.toFixed(2)}"
        y="${padding.top}"
        width="${rectWidth.toFixed(2)}"
        height="${innerHeight}"
      ></rect>
    `;
  };

  const boundaryLines = (range, className) => {
    if (!range) {
      return "";
    }
    const lines = [range.startIndex, range.endIndex].map((index) => {
      const x = xForIndex(index);
      return `
        <line
          class="${className}"
          x1="${x.toFixed(2)}"
          y1="${padding.top}"
          x2="${x.toFixed(2)}"
          y2="${(height - padding.bottom).toFixed(2)}"
        ></line>
      `;
    });
    return lines.join("");
  };

  const gridLines = Array.from({ length: 4 }, (_, index) => {
    const y = padding.top + (innerHeight / 3) * index;
    return `
      <line
        class="hero-chart-grid"
        x1="${padding.left}"
        y1="${y.toFixed(2)}"
        x2="${(width - padding.right).toFixed(2)}"
        y2="${y.toFixed(2)}"
      ></line>
    `;
  }).join("");

  const svg = `
    <svg
      id="hero-chart-svg"
      class="hero-chart-svg"
      viewBox="0 0 ${width} ${height}"
      preserveAspectRatio="none"
      aria-label="Hero stock price chart"
    >
      ${gridLines}
      ${rangeRect(selectedRange, "hero-chart-range")}
      ${rangeRect(effectiveRange, "hero-chart-effective-range")}
      ${boundaryLines(selectedRange, "hero-chart-boundary")}
      ${boundaryLines(effectiveRange, "hero-chart-effective-boundary")}
      <path class="hero-chart-line" d="${linePath}"></path>
      <line id="hero-chart-focus-line" class="hero-chart-focus-line" x1="0" y1="${padding.top}" x2="0" y2="${height - padding.bottom}" hidden></line>
      <circle id="hero-chart-focus-dot" class="hero-chart-focus-dot" cx="0" cy="0" r="4" hidden></circle>
      <rect
        id="hero-chart-overlay"
        class="hero-chart-overlay"
        x="${padding.left}"
        y="${padding.top}"
        width="${innerWidth}"
        height="${innerHeight}"
      ></rect>
    </svg>
  `;

  return {
    svg,
    points,
    width,
    height,
    padding,
    innerWidth,
    selectedWindow,
    effectiveWindow,
  };
}

function attachHeroChartInteractions(chartModel) {
  if (!chartModel?.points?.length) {
    return;
  }

  const svg = document.getElementById("hero-chart-svg");
  const overlay = document.getElementById("hero-chart-overlay");
  const tooltip = document.getElementById("hero-chart-tooltip");
  const focusLine = document.getElementById("hero-chart-focus-line");
  const focusDot = document.getElementById("hero-chart-focus-dot");

  if (!svg || !overlay || !tooltip || !focusLine || !focusDot) {
    return;
  }

  const updateTooltip = (event) => {
    const overlayRect = overlay.getBoundingClientRect();
    const relativeX = clamp(event.clientX - overlayRect.left, 0, overlayRect.width);
    const progress = relativeX / Math.max(overlayRect.width, 1);
    const pointIndex = clamp(
      Math.round(progress * (chartModel.points.length - 1)),
      0,
      chartModel.points.length - 1,
    );
    const point = chartModel.points[pointIndex];
    const inSelectedWindow = point.date >= chartModel.selectedWindow.start_date
      && point.date <= chartModel.selectedWindow.end_date;
    const inEffectiveWindow = chartModel.effectiveWindow
      && point.date >= chartModel.effectiveWindow.start_date
      && point.date <= chartModel.effectiveWindow.end_date;

    focusLine.removeAttribute("hidden");
    focusDot.removeAttribute("hidden");
    focusLine.setAttribute("x1", point.x);
    focusLine.setAttribute("x2", point.x);
    focusDot.setAttribute("cx", point.x);
    focusDot.setAttribute("cy", point.y);

    tooltip.hidden = false;
    tooltip.innerHTML = `
      <strong>${point.date}</strong>
      <span>Close: ${point.close.toFixed(2)}</span>
      ${inSelectedWindow ? "<span>Inside selected window</span>" : ""}
      ${inEffectiveWindow ? "<span>Inside encoded model window</span>" : ""}
    `;

    const shell = svg.parentElement;
    const shellRect = shell.getBoundingClientRect();
    const left = clamp(
      event.clientX - shellRect.left + 12,
      8,
      shellRect.width - 168,
    );
    const top = clamp(
      event.clientY - shellRect.top - 72,
      8,
      shellRect.height - 72,
    );
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  const clearTooltip = () => {
    tooltip.hidden = true;
    focusLine.setAttribute("hidden", "hidden");
    focusDot.setAttribute("hidden", "hidden");
  };

  overlay.addEventListener("mousemove", updateTooltip);
  overlay.addEventListener("mouseenter", updateTooltip);
  overlay.addEventListener("mouseleave", clearTooltip);
}

function modeLabel(mode) {
  return mode
    .replaceAll("_", " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
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

function setHeroStatus(message) {
  heroStatus.textContent = message;
}

function setLoadingState(action, isLoading) {
  createHeroButton.disabled = isLoading;
  runSearchButton.disabled = isLoading;

  if (action === "create") {
    createHeroButton.textContent = isLoading ? "Saving..." : "Save Hero";
  }
  if (action === "run") {
    runSearchButton.textContent = isLoading ? "Running..." : "Run Search";
  }
}

function renderIdleSummary(hero = null) {
  activeMode.textContent = "Awaiting run";
  searchBackend.textContent = hero ? "Ready to search" : "No active hero";
  heroRegime.textContent = hero ? hero.ticker : "N/A";
  effectiveWindowLabel.textContent = hero
    ? `${hero.start_date} to ${hero.end_date}`
    : "N/A";
}

function renderSummary(mode, matchData) {
  const dna = matchData.hero?.[mode] || {};
  const effectiveWindow = matchData.effective_hero_window;
  const selectedWindow = matchData.selected_window;

  activeMode.textContent = modeLabel(mode);
  searchBackend.textContent = backendLabel(matchData.search_backend);
  heroRegime.textContent = matchData.hero_regime_code || dna.regime_code || "N/A";
  effectiveWindowLabel.textContent = effectiveWindow
    ? `${effectiveWindow.start_date} to ${effectiveWindow.end_date}`
    : `${selectedWindow.start_date} to ${selectedWindow.end_date}`;
}

function renderHero(hero, mode, selectedWindow, effectiveWindow = null, searchMode = null, heroSeries = null) {
  const dna = hero?.[mode] || { confidence: 0, regime_code: "N/A", traits: [] };
  const requestedLabel = `${selectedWindow.start_date} to ${selectedWindow.end_date}`;
  const encodedLabel = effectiveWindow
    ? `${effectiveWindow.start_date} to ${effectiveWindow.end_date} (${effectiveWindow.window_size} trading-day model window)`
    : requestedLabel;
  const backendNote = searchMode === "vqvae"
    ? `<p class="meta">Using trained VQ-VAE Price DNA encoding.</p>`
    : searchMode === "economic_live"
      ? `<p class="meta">Using live macro plus price-window factor matching.</p>`
      : searchMode === "social_live"
        ? `<p class="meta">Using Finnhub company news, NewsAPI article discovery, and FinBERT sentiment scoring aggregated into daily social signals.</p>`
        : searchMode === "social_mvp"
          ? `<p class="meta">Using local Social DNA proxy signals built from ticker narrative profiles and price-persistence features.</p>`
          : "";
  const heroChart = buildHeroChartModel(heroSeries?.series || [], selectedWindow, effectiveWindow);
  const historyLabel = heroSeries?.available_start_date && heroSeries?.available_end_date
    ? `${heroSeries.available_start_date} to ${heroSeries.available_end_date}`
    : requestedLabel;
  const confidencePercent = typeof dna.confidence === "number"
    ? `${Math.round(dna.confidence * 100)}%`
    : "N/A";

  heroCard.innerHTML = `
    <div class="card hero-card">
      <h3>${buildHeroIdentity(hero)}</h3>
      <p class="meta">${hero.title || hero.window_label || "Saved hero window"}</p>
      <div class="hero-chart-shell">
        ${heroChart.svg}
        <div id="hero-chart-tooltip" class="hero-chart-tooltip" hidden></div>
      </div>
      <div class="hero-chart-legend">
        <span><i class="legend-swatch legend-swatch-selected"></i>Selected window</span>
        ${effectiveWindow ? '<span><i class="legend-swatch legend-swatch-effective"></i>Encoded model window</span>' : ""}
      </div>
      <p class="meta">Selected window: ${requestedLabel}</p>
      <p class="meta">Available history: ${historyLabel}</p>
      <p>${hero.summary || "User-defined hero window."}</p>
      <div class="metric-row">
        <div>
          <span class="mini-label">Confidence</span>
          <p class="score">${confidencePercent}</p>
        </div>
        <div>
          <span class="mini-label">Regime Code</span>
          <p class="metric-value">${dna.regime_code || "N/A"}</p>
        </div>
      </div>
      <p class="meta">Encoded slice: ${encodedLabel}</p>
      ${backendNote}
      <div>${traitPills(dna.traits || [])}</div>
    </div>
  `;

  attachHeroChartInteractions(heroChart);
}

function renderHeroDraft(hero, heroSeries = null) {
  if (!hero) {
    heroCard.innerHTML = `<div class="card"><p>Save a hero window to get started.</p></div>`;
    return;
  }

  const selectedWindow = {
    start_date: hero.start_date,
    end_date: hero.end_date,
  };
  const heroChart = buildHeroChartModel(heroSeries?.series || [], selectedWindow, null);
  const historyLabel = heroSeries?.available_start_date && heroSeries?.available_end_date
    ? `${heroSeries.available_start_date} to ${heroSeries.available_end_date}`
    : `${hero.start_date} to ${hero.end_date}`;

  heroCard.innerHTML = `
    <div class="card hero-card">
      <h3>${buildHeroIdentity(hero)}</h3>
      <p class="meta">${hero.title || "Saved hero window"}</p>
      <div class="hero-chart-shell">
        ${heroChart.svg}
        <div id="hero-chart-tooltip" class="hero-chart-tooltip" hidden></div>
      </div>
      <div class="hero-chart-legend">
        <span><i class="legend-swatch legend-swatch-selected"></i>Selected window</span>
      </div>
      <p class="meta">Selected window: ${hero.start_date} to ${hero.end_date}</p>
      <p class="meta">Available history: ${historyLabel}</p>
      <p>${hero.summary || "User-defined hero window."}</p>
      <p class="meta">Run a DNA search to generate a saved result snapshot.</p>
    </div>
  `;

  attachHeroChartInteractions(heroChart);
}

function renderMarketWatch(data) {
  headlineRegime.textContent = data.headline_regime;
  marketWatch.innerHTML = data.indicators.map((indicator) => {
    const chartSvg = seriesSparkline(indicator.series, `${indicator.name}-${indicator.value}`);
    const changeLabel = typeof indicator.change_pct === "number"
      ? `<p class="meta">Last ${indicator.series?.length || 0} sessions: ${indicator.change_pct >= 0 ? "+" : ""}${indicator.change_pct}%</p>`
      : "";

    return `
      <div class="card watch-card">
        <div class="card-topline">
          <div>
            <h3>${indicator.name}</h3>
            ${indicator.symbol ? `<p class="meta">${indicator.symbol}</p>` : ""}
          </div>
          <span class="status-pill">${indicator.status}</span>
        </div>
        <div class="sparkline-shell">
          ${chartSvg}
        </div>
        <p class="score">${indicator.value}</p>
        ${changeLabel}
        <p>${indicator.insight}</p>
      </div>
    `;
  }).join("");
}

function renderMatches(items) {
  if (!items?.length) {
    matchesPanel.innerHTML = `<div class="card"><p>No matches saved for this run yet.</p></div>`;
    return;
  }

  matchesPanel.innerHTML = items.map((item, index) => {
    const scorePct = Math.round(item.score * 100);
    const chartSvg = item.series?.length
      ? seriesSparkline(item.series, `${item.ticker}-${index}`)
      : "";
    const matchedWindow = item.matched_window
      ? `<p class="meta">Matched window: ${item.matched_window.start_date} to ${item.matched_window.end_date}</p>`
      : "";

    return `
      <div class="card match-card">
        <div class="card-topline">
          <div class="match-title">
            <span class="rank-badge">#${index + 1}</span>
            <div>
              <h3>${item.name} (${item.ticker})</h3>
              <p class="meta">${item.sector || "Unknown"}</p>
            </div>
          </div>
          <div class="score-badge">
            <span class="mini-label">${confidenceTone(item.score)}</span>
            <strong>${scorePct}%</strong>
          </div>
        </div>
        <p><strong>${item.regime_label}</strong></p>
        ${matchedWindow}
        ${chartSvg ? `
          <div class="sparkline-shell">
            ${chartSvg}
          </div>
        ` : ""}
        <div class="score-track" aria-hidden="true">
          <span class="score-fill" style="width: ${Math.max(8, Math.min(scorePct, 100))}%"></span>
        </div>
        <p>${item.explanation}</p>
      </div>
    `;
  }).join("");
}

function renderIndustryChain(ticker, relationships = []) {
  if (!relationships.length) {
    industryChain.innerHTML = `
      <div class="card industry-card">
        <h3>${ticker} industry map</h3>
        <p class="meta">No saved relationship map exists for this ticker yet.</p>
      </div>
    `;
    return;
  }

  industryChain.innerHTML = `
    <div class="card industry-card">
      <h3>${ticker} industry map</h3>
      <div class="network-grid" aria-hidden="true">
        ${relationships.map((item, index) => `
          <span class="network-node node-${(index % 4) + 1}"></span>
        `).join("")}
      </div>
      <div class="chain-list">
        ${relationships.map((item) => `
          <article class="chain-item">
            <div class="card-topline">
              <strong>${item.ticker}</strong>
              <span class="status-pill">${item.direction}</span>
            </div>
            <p class="meta">${item.relationship}</p>
            <p>${item.impact}</p>
          </article>
        `).join("")}
      </div>
    </div>
  `;
}

function renderSavedHeroes() {
  if (!savedHeroes.length) {
    savedHeroesPanel.innerHTML = `<div class="card"><p>No heroes saved yet. Create one from any ticker and date range.</p></div>`;
    return;
  }

  savedHeroesPanel.innerHTML = `
    <div class="saved-collection">
      ${savedHeroes.map((hero) => `
        <button
          type="button"
          class="saved-item ${currentHero?.id === hero.id ? "is-active" : ""}"
          data-hero-id="${hero.id}"
        >
          <strong>${hero.title}</strong>
          <span>${buildHeroIdentity(hero)}</span>
          <p class="meta">${hero.start_date} to ${hero.end_date}</p>
          <p class="meta">Updated ${formatDateTime(hero.updated_at)}</p>
        </button>
      `).join("")}
    </div>
  `;

  savedHeroesPanel.querySelectorAll("[data-hero-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectHero(Number(button.dataset.heroId));
    });
  });
}

function renderSearchRuns() {
  if (!currentHero) {
    searchRunsPanel.innerHTML = `<div class="card"><p>Select a saved hero to view its search history.</p></div>`;
    return;
  }

  if (!currentSearchRuns.length) {
    searchRunsPanel.innerHTML = `<div class="card"><p>No saved searches for this hero yet. Run one to create a reusable result snapshot.</p></div>`;
    return;
  }

  searchRunsPanel.innerHTML = `
    <div class="saved-collection">
      ${currentSearchRuns.map((run) => `
        <button
          type="button"
          class="saved-item ${currentSearchRun?.id === run.id ? "is-active" : ""}"
          data-run-id="${run.id}"
        >
          <strong>${modeLabel(run.mode)}</strong>
          <span>${backendLabel(run.search_backend)}</span>
          <p class="meta">${formatDateTime(run.created_at)}</p>
          <p class="meta">${run.top_match ? `Top match: ${run.top_match.ticker} (${Math.round(run.top_match.score * 100)}%)` : "No top match saved"}</p>
        </button>
      `).join("")}
    </div>
  `;

  searchRunsPanel.querySelectorAll("[data-run-id]").forEach((button) => {
    button.addEventListener("click", () => {
      loadSearchRun(Number(button.dataset.runId));
    });
  });
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    let detail = `Request failed: ${response.status}`;
    try {
      const payload = await response.json();
      detail = payload.detail || detail;
    } catch (error) {
      // Keep the default detail.
    }
    throw new Error(detail);
  }
  return response.json();
}

async function postJson(url, payload) {
  return fetchJson(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });
}

function syncFormWithHero(hero) {
  tickerInput.value = hero.ticker;
  titleInput.value = hero.title || "";
  startDateInput.value = hero.start_date;
  endDateInput.value = hero.end_date;
}

function buildHeroPayloadFromForm() {
  return {
    ticker: tickerInput.value.trim().toUpperCase(),
    title: titleInput.value.trim() || null,
    start_date: startDateInput.value,
    end_date: endDateInput.value,
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
  } catch (error) {
    return { ticker, relationships: [] };
  }
}

async function loadSavedHeroes(preferredHeroId = null) {
  const data = await fetchJson("/api/heroes");
  savedHeroes = data.heroes;
  renderSavedHeroes();

  if (!savedHeroes.length) {
    currentHero = null;
    currentSearchRun = null;
    currentSearchRuns = [];
    renderSearchRuns();
    renderIdleSummary();
    renderHeroDraft(null);
    renderMatches([]);
    renderIndustryChain("No hero", []);
    setHeroStatus("No saved hero selected.");
    return;
  }

  const heroToSelect = preferredHeroId
    || currentHero?.id
    || savedHeroes[0]?.id;

  if (heroToSelect) {
    await selectHero(heroToSelect);
  }
}

async function selectHero(heroId) {
  currentHero = await fetchJson(`/api/heroes/${heroId}`);
  currentSearchRun = null;
  syncFormWithHero(currentHero);
  renderSavedHeroes();
  setHeroStatus(`Active hero: ${currentHero.title}`);

  const [searchRunData, heroSeries, chainData] = await Promise.all([
    fetchJson(`/api/heroes/${heroId}/search-runs`),
    fetchHeroSeries(currentHero),
    loadIndustryChain(currentHero.ticker),
  ]);

  currentSearchRuns = searchRunData.search_runs;
  renderSearchRuns();
  renderIndustryChain(currentHero.ticker, chainData.relationships);

  if (currentSearchRuns.length) {
    await loadSearchRun(currentSearchRuns[0].id, heroSeries, chainData);
    return;
  }

  renderIdleSummary(currentHero);
  renderHeroDraft(currentHero, heroSeries);
  renderMatches([]);
}

async function createHeroFromForm() {
  const payload = buildHeroPayloadFromForm();
  if (!payload.ticker || !payload.start_date || !payload.end_date) {
    throw new Error("Ticker, start date, and end date are required.");
  }

  const hero = await postJson("/api/heroes", payload);
  currentHero = hero;
  currentSearchRun = null;
  currentSearchRuns = [];
  await loadSavedHeroes(hero.id);
  return currentHero;
}

async function ensureCurrentHero() {
  if (!currentHero || currentHeroDiffersFromForm()) {
    return createHeroFromForm();
  }
  return currentHero;
}

async function loadSearchRun(searchRunId, heroSeries = null, chainData = null) {
  const run = await fetchJson(`/api/search-runs/${searchRunId}`);
  currentSearchRun = run;
  renderSearchRuns();

  if (!currentHero || currentHero.id !== run.hero_id) {
    currentHero = await fetchJson(`/api/heroes/${run.hero_id}`);
    renderSavedHeroes();
  }

  if (!heroSeries) {
    heroSeries = await fetchHeroSeries(currentHero);
  }
  if (!chainData) {
    chainData = await loadIndustryChain(currentHero.ticker);
  }

  modeSelect.value = run.mode;
  renderSummary(run.mode, run);
  renderHero(
    run.hero,
    run.mode,
    run.selected_window,
    run.effective_hero_window,
    run.search_backend,
    heroSeries,
  );
  renderMatches(run.matches);
  renderIndustryChain(currentHero.ticker, chainData.relationships);
}

async function handleCreateHero() {
  setLoadingState("create", true);
  try {
    const hero = await createHeroFromForm();
    setHeroStatus(`Saved hero ${hero.title}.`);
  } finally {
    setLoadingState("create", false);
  }
}

async function handleRunSearch() {
  setLoadingState("run", true);
  try {
    const hero = await ensureCurrentHero();
    const run = await postJson(`/api/heroes/${hero.id}/search-runs`, {
      mode: modeSelect.value,
    });
    currentSearchRun = run;

    const [searchRunData, heroSeries, chainData] = await Promise.all([
      fetchJson(`/api/heroes/${hero.id}/search-runs`),
      fetchHeroSeries(hero),
      loadIndustryChain(hero.ticker),
    ]);

    currentSearchRuns = searchRunData.search_runs;
    renderSearchRuns();
    renderSummary(run.mode, run);
    renderHero(
      run.hero,
      run.mode,
      run.selected_window,
      run.effective_hero_window,
      run.search_backend,
      heroSeries,
    );
    renderMatches(run.matches);
    renderIndustryChain(hero.ticker, chainData.relationships);
    setHeroStatus(`Saved ${modeLabel(run.mode)} search for ${hero.title}.`);
  } finally {
    setLoadingState("run", false);
  }
}

async function init() {
  renderIdleSummary();
  renderHeroDraft(null);
  renderMatches([]);
  renderSearchRuns();

  const watchData = await fetchJson("/api/market-watch");
  renderMarketWatch(watchData);
  await loadSavedHeroes();
}

createHeroButton.addEventListener("click", () => {
  handleCreateHero().catch((error) => {
    console.error(error);
    setHeroStatus(error.message);
  });
});

runSearchButton.addEventListener("click", () => {
  handleRunSearch().catch((error) => {
    console.error(error);
    setHeroStatus(error.message);
  });
});

init().catch((error) => {
  console.error(error);
  setHeroStatus(error.message);
  matchesPanel.innerHTML = `<div class="card"><p>Failed to load MirrorQuant.</p></div>`;
});
