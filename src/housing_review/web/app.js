const AGENTS = [
  { id: "zoning_analyst", label: "Zoning", about: "Permitted uses, dimensional limits, and parking rules." },
  { id: "demographic_analyst", label: "Demographic", about: "Population, household, and housing stock trends." },
  { id: "pro_forma_analyst", label: "Cost and feasibility", about: "Land value, nearby sales, and estimated construction cost." },
  { id: "equity_analyst", label: "Equity", about: "Housing cost burden and income levels in the surrounding area." },
  { id: "sustainability_analyst", label: "Sustainability", about: "Transit access, flood risk, and carbon impact." },
];

const TYPOLOGY_LABELS = {
  duplex: "Duplex",
  apartment: "Apartment",
  townhome: "Townhome",
  adu: "Accessory dwelling",
  senior_housing: "Senior housing",
  detached_single_family: "Detached house",
};

const SUPPORTED_SITE = {
  label: "170 Aidan Ct, Pittsburgh, PA 15226",
  pin: "0139F00077000000",
};

const CHEVRON_UP =
  '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M10 4 4 12h12z"/></svg>';
const CHEVRON_DOWN =
  '<svg viewBox="0 0 20 20" aria-hidden="true"><path fill="currentColor" d="M10 16 4 8h12z"/></svg>';
const DRAG_HANDLE =
  '<svg class="drag-handle" viewBox="0 0 16 24" aria-hidden="true"><circle cx="5" cy="5" r="1.7" fill="currentColor"/><circle cx="11" cy="5" r="1.7" fill="currentColor"/><circle cx="5" cy="12" r="1.7" fill="currentColor"/><circle cx="11" cy="12" r="1.7" fill="currentColor"/><circle cx="5" cy="19" r="1.7" fill="currentColor"/><circle cx="11" cy="19" r="1.7" fill="currentColor"/></svg>';

const state = {
  demo: null,
  siteId: null,
  analysis: null,
  order: AGENTS.map((item) => item.id),
  view: null,
  map: null,
  sortable: null,
  suggestIndex: 0,
};

function esc(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function agentMeta(id) {
  const key = typeof id === "string" ? id : String(id ?? "");
  return AGENTS.find((item) => item.id === key) || { id: key, label: key, about: "" };
}

function resolveSite(raw) {
  const text = raw.trim().toLowerCase();
  const compact = text.replace(/[^a-z0-9]/g, "");
  if (!text) return null;
  if (compact.includes("0139f00077000000")) return "0139F00077000000";
  if (compact.includes("139f77") || text.includes("139-f-77")) return "0139F00077000000";
  if (text.includes("170") && text.includes("aidan")) return "0139F00077000000";
  return null;
}

function sourceHref(source) {
  const match = String(source).match(/https?:\/\/[^\s)]+/i);
  return match ? match[0] : null;
}

function setStatus(message) {
  const el = document.getElementById("site-status");
  if (el) el.textContent = message;
}

function hideCoverage() {
  const note = document.getElementById("coverage-note");
  if (note) note.hidden = true;
}

function showCoverage() {
  const note = document.getElementById("coverage-note");
  if (note) note.hidden = false;
}

function showView(name) {
  document.querySelectorAll(".view").forEach((node) => node.classList.remove("is-active"));
  document.getElementById(`view-${name}`).classList.add("is-active");
  document.body.dataset.view = name;
  const shell = document.getElementById("shell");
  const landing = document.getElementById("view-landing");
  if (name === "landing") {
    shell.hidden = true;
    landing.classList.add("is-active");
  } else {
    shell.hidden = false;
    landing.classList.remove("is-active");
  }
  if (name === "input") {
    resetSearch();
    window.setTimeout(() => {
      if (state.map) state.map.invalidateSize();
    }, 80);
  }
}

function resetSearch() {
  const input = document.getElementById("site-input");
  input.value = "";
  hideSuggestions();
  hideCoverage();
  setStatus("");
}

function initMap() {
  if (!state.demo || state.map || typeof L === "undefined") return;
  const mapEl = document.getElementById("site-map");
  state.map = L.map(mapEl, { scrollWheelZoom: false, attributionControl: true });
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    subdomains: "abc",
    attribution: "&copy; OpenStreetMap",
  }).addTo(state.map);
  const layer = L.geoJSON(state.demo.geometry, {
    style: { color: "#232323", weight: 3, fillColor: "#FCC113", fillOpacity: 0.5 },
  }).addTo(state.map);
  state.map.fitBounds(layer.getBounds(), { padding: [36, 36], maxZoom: 18 });
  mapEl.setAttribute("aria-label", state.demo.map_description);
  document.getElementById("map-figcaption").textContent =
    `${state.demo.address}. PIN ${state.demo.site_id}. ${state.demo.zoning_district}, about ${state.demo.lot_acreage} acres.`;
}

function queryMatchesSupported(query) {
  const q = query.trim().toLowerCase();
  if (q.length < 2) return false;
  const compact = q.replace(/[^a-z0-9]/g, "");
  return (
    SUPPORTED_SITE.label.toLowerCase().includes(q) ||
    (compact.length >= 2 && SUPPORTED_SITE.pin.toLowerCase().includes(compact))
  );
}

function hideSuggestions() {
  const list = document.getElementById("suggest-list");
  const input = document.getElementById("site-input");
  list.replaceChildren();
  list.hidden = true;
  input.setAttribute("aria-expanded", "false");
  input.removeAttribute("aria-activedescendant");
}

function highlightSuggestion(index) {
  const options = [...document.querySelectorAll("#suggest-list [role='option']")];
  if (!options.length) return;
  const next = Math.max(0, Math.min(index, options.length - 1));
  state.suggestIndex = next;
  options.forEach((option, i) => {
    option.setAttribute("aria-selected", i === next ? "true" : "false");
  });
  document.getElementById("site-input").setAttribute("aria-activedescendant", options[next].id);
}

function chooseSuggestion() {
  const input = document.getElementById("site-input");
  input.value = SUPPORTED_SITE.label;
  hideSuggestions();
  hideCoverage();
}

function renderSuggestions(query) {
  const list = document.getElementById("suggest-list");
  const input = document.getElementById("site-input");
  hideCoverage();
  if (!queryMatchesSupported(query)) {
    hideSuggestions();
    return;
  }
  list.replaceChildren();
  const option = document.createElement("li");
  option.id = "suggest-0";
  option.setAttribute("role", "option");
  option.textContent = SUPPORTED_SITE.label;
  option.setAttribute("aria-selected", "false");
  option.addEventListener("mousedown", (event) => {
    event.preventDefault();
    chooseSuggestion();
  });
  option.addEventListener("mouseenter", () => highlightSuggestion(0));
  list.append(option);
  list.hidden = false;
  input.setAttribute("aria-expanded", "true");
  input.removeAttribute("aria-activedescendant");
  state.suggestIndex = -1;
}

function renderRanker() {
  const list = document.getElementById("ranker-list");
  list.replaceChildren();
  state.order.forEach((id, index) => {
    const meta = agentMeta(id);
    const item = document.createElement("li");
    item.className = "ranker-item";
    item.dataset.agent = id;
    item.innerHTML = `
      ${DRAG_HANDLE}
      <span class="rank-badge" aria-hidden="true">${index + 1}</span>
      <div class="ranker-copy">
        <strong class="ranker-name">${esc(meta.label)}</strong>
        <p class="ranker-about">${esc(meta.about)}</p>
      </div>
      <div class="ranker-buttons">
        <button type="button" class="icon-btn move-up" data-agent="${esc(id)}" aria-label="Move ${esc(meta.label)} up" ${index === 0 ? "disabled" : ""}>${CHEVRON_UP}</button>
        <button type="button" class="icon-btn move-down" data-agent="${esc(id)}" aria-label="Move ${esc(meta.label)} down" ${index === state.order.length - 1 ? "disabled" : ""}>${CHEVRON_DOWN}</button>
      </div>
    `;
    list.append(item);
  });
  list.querySelectorAll(".move-up").forEach((button) => {
    button.addEventListener("click", () => moveAgent(button.dataset.agent, -1, "up"));
  });
  list.querySelectorAll(".move-down").forEach((button) => {
    button.addEventListener("click", () => moveAgent(button.dataset.agent, 1, "down"));
  });
  if (state.sortable) state.sortable.destroy();
  state.sortable = Sortable.create(list, {
    animation: 180,
    filter: ".icon-btn, .ranker-buttons",
    preventOnFilter: false,
    onEnd() {
      state.order = [...list.querySelectorAll(".ranker-item")].map((row) => row.dataset.agent);
      renderRanker();
    },
  });
}

function moveAgent(id, delta, direction) {
  const index = state.order.indexOf(id);
  const next = index + delta;
  if (next < 0 || next >= state.order.length) return;
  const copy = [...state.order];
  [copy[index], copy[next]] = [copy[next], copy[index]];
  state.order = copy;
  renderRanker();
  const focusSel = direction === "up" ? `.move-up[data-agent="${id}"]` : `.move-down[data-agent="${id}"]`;
  const target = document.querySelector(focusSel);
  if (target && !target.disabled) target.focus();
}

function claimsFor(typology) {
  const items = [];
  for (const assessment of state.analysis.round_1.assessments) {
    if (assessment.typology !== typology) continue;
    for (const claim of assessment.claims || []) {
      items.push({ agent: assessment.agent, ...claim });
    }
  }
  return items;
}

function findingText(row) {
  const name = TYPOLOGY_LABELS[row.typology] || row.typology;
  const dispute = (row.factual_disputes || [])[0] || (row.value_disputes || [])[0];
  const top = [...row.contributions].sort((a, b) => b.contribution - a.contribution)[0];
  const lens = agentMeta(top.agent).label;
  if (dispute) {
    const extra = dispute.framing || dispute.resolution_needed || "";
    return `${name} scores ${row.weighted_score.toFixed(1)} of 10. ${dispute.issue} ${extra}`.trim();
  }
  return `${name} scores ${row.weighted_score.toFixed(1)} of 10. ${lens} is the strongest factor.`;
}

function renderResults() {
  const list = document.getElementById("results-list");
  list.replaceChildren();
  for (const row of state.view.ranking) {
    const card = document.createElement("li");
    card.className = "result-card";
    card.innerHTML = `
      <span class="ord" aria-hidden="true">${row.rank}</span>
      <h2>${esc(TYPOLOGY_LABELS[row.typology] || row.typology)}</h2>
      <span class="score">${row.weighted_score.toFixed(1)}</span>
      <button type="button" class="source-link" data-typology="${esc(row.typology)}">Source</button>
    `;
    list.append(card);
  }
  list.querySelectorAll(".source-link").forEach((button) => {
    button.addEventListener("click", () => openDetail(button.dataset.typology));
  });
}

function openDetail(typology) {
  const row = state.view.ranking.find((item) => item.typology === typology);
  if (!row) return;
  document.getElementById("detail-heading").textContent = TYPOLOGY_LABELS[typology] || typology;
  document.getElementById("detail-score").textContent = `${row.weighted_score.toFixed(1)} of 10`;
  document.getElementById("detail-finding").textContent = findingText(row);
  const sources = document.getElementById("detail-sources");
  sources.replaceChildren();
  const seen = new Set();
  for (const claim of claimsFor(typology)) {
    const href = sourceHref(claim.source);
    const key = href || claim.source;
    if (seen.has(key)) continue;
    seen.add(key);
    const li = document.createElement("li");
    const lens = agentMeta(claim.agent).label;
    const label = (claim.source || "").split(";")[0].slice(0, 140);
    const caption = `${lens}: ${label}`;
    if (href) {
      li.innerHTML = `<a href="${esc(href)}" target="_blank" rel="noreferrer">${esc(caption)}</a>`;
    } else {
      li.textContent = caption;
    }
    sources.append(li);
    if (sources.children.length >= 8) break;
  }
  const gaps = document.getElementById("detail-gaps");
  gaps.replaceChildren();
  for (const group of row.cannot_determine || []) {
    const lens = agentMeta(group.agent).label;
    for (const note of group.cannot_determine || []) {
      const li = document.createElement("li");
      li.textContent = `${lens}: ${note}`;
      gaps.append(li);
    }
  }
  if (!gaps.children.length) {
    const li = document.createElement("li");
    li.textContent = "No extra gaps are listed for this housing type.";
    gaps.append(li);
  }
  showView("detail");
  document.getElementById("detail-heading").focus();
}

function renderSliders() {
  const host = document.getElementById("slider-list");
  host.replaceChildren();
  for (const agent of AGENTS) {
    const share = state.view.weights[agent.id];
    const row = document.createElement("div");
    row.className = "slider-row";
    row.innerHTML = `
      <label for="w-${agent.id}">
        <span>${esc(agent.label)}</span>
        <span id="w-val-${agent.id}">${Math.round(share * 100)}%</span>
      </label>
      <input id="w-${agent.id}" type="range" min="1" max="100" value="${Math.round(share * 100)}" data-agent="${agent.id}" />
    `;
    host.append(row);
  }
  host.querySelectorAll("input[type=range]").forEach((input) => {
    input.addEventListener("input", onSlider);
  });
}

let sliderTimer = 0;
function onSlider() {
  clearTimeout(sliderTimer);
  sliderTimer = setTimeout(pushWeights, 80);
}

async function pushWeights() {
  if (!state.siteId) return;
  const weights = {};
  for (const agent of AGENTS) {
    weights[agent.id] = Number(document.getElementById(`w-${agent.id}`).value);
  }
  const response = await fetch(`/weighted-view/${state.siteId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ weights }),
  });
  if (!response.ok) {
    setStatus(await errorText(response));
    return;
  }
  const payload = await response.json();
  state.view = payload.view;
  renderResults();
  for (const agent of AGENTS) {
    document.getElementById(`w-val-${agent.id}`).textContent = `${Math.round(state.view.weights[agent.id] * 100)}%`;
  }
}

async function errorText(response) {
  try {
    const body = await response.json();
    const detail = body.detail;
    return typeof detail === "string" ? detail : response.statusText;
  } catch {
    return response.statusText;
  }
}

async function loadAnalysis(siteId) {
  hideCoverage();
  setStatus("Loading saved scores.");
  const response = await fetch(`/analysis/${encodeURIComponent(siteId)}`);
  if (!response.ok) {
    setStatus(await errorText(response));
    return;
  }
  state.siteId = siteId;
  state.analysis = await response.json();
  renderRanker();
  showView("ranking");
  document.getElementById("ranker-heading").focus();
}

async function submitRanking() {
  if (!state.siteId) return;
  const response = await fetch(`/weighted-view/${state.siteId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ preference_order: state.order }),
  });
  if (!response.ok) {
    setStatus(await errorText(response));
    return;
  }
  const payload = await response.json();
  state.view = payload.view;
  renderResults();
  renderSliders();
  showView("results");
  document.getElementById("results-heading").focus();
}

async function init() {
  state.demo = await (await fetch("/demo-site")).json();
  document.getElementById("get-started").addEventListener("click", () => {
    showView("input");
    initMap();
    document.getElementById("site-input").focus();
  });
  document.getElementById("home-link").addEventListener("click", () => showView("landing"));
  const input = document.getElementById("site-input");
  input.addEventListener("input", () => {
    setStatus("");
    renderSuggestions(input.value);
  });
  input.addEventListener("keydown", (event) => {
    const list = document.getElementById("suggest-list");
    const open = !list.hidden;
    if (event.key === "Escape") {
      hideSuggestions();
      return;
    }
    if (event.key === "ArrowDown") {
      event.preventDefault();
      if (!open) renderSuggestions(input.value);
      highlightSuggestion(state.suggestIndex < 0 ? 0 : state.suggestIndex + 1);
      return;
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) renderSuggestions(input.value);
      highlightSuggestion(state.suggestIndex < 0 ? 0 : state.suggestIndex - 1);
      return;
    }
    if (event.key === "Enter" && open) {
      event.preventDefault();
      chooseSuggestion();
    }
  });
  input.addEventListener("blur", () => {
    window.setTimeout(() => {
      if (document.activeElement === input) return;
      hideSuggestions();
    }, 120);
  });
  document.getElementById("coverage-fill").addEventListener("click", () => {
    chooseSuggestion();
    input.focus();
  });
  document.getElementById("site-form").addEventListener("submit", async (event) => {
    event.preventDefault();
    hideSuggestions();
    const resolved = resolveSite(input.value);
    if (!resolved) {
      setStatus("");
      showCoverage();
      return;
    }
    hideCoverage();
    await loadAnalysis(resolved);
  });
  document.getElementById("ranker-submit").addEventListener("click", submitRanking);
  document.getElementById("detail-back").addEventListener("click", () => {
    showView("results");
    document.getElementById("results-heading").focus();
  });
  document.getElementById("help-open").addEventListener("click", () => {
    document.getElementById("help-panel").showModal();
  });
}

init().catch((err) => setStatus(String(err)));
