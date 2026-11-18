// ---------- helpers ----------

// Scraped text goes into innerHTML, so everything is escaped first (prevents XSS).
const esc = s => String(s ?? "").replace(/[&<>"']/g, c =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = u => (/^https?:\/\//i.test(u || "") ? u : "#");
const fmt = s => (s ? esc(String(s).replace(/\s+/g, " ")) : "—");
const date = s => s
  ? new Date(s).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })
  : "—";
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} returned ${r.status}`);
  return r.json();
}

const matchQuery = (q, ...fields) => {
  q = q.trim().toLowerCase();
  return !q || fields.some(f => (f || "").toLowerCase().includes(q));
};

const isRemote = i => /work\s*from\s*home|remote/i.test(i.location || "");
const isMumbai = i => /mumbai/i.test(i.location || "");

const NEAR_MUMBAI = ["mumbai", "navi mumbai", "thane", "panvel", "kalyan", "vasai", "palghar"];
const isNearMumbai = h => {
  const t = `${h.city || ""} ${h.location_raw || ""}`.toLowerCase();
  return NEAR_MUMBAI.some(c => t.includes(c));
};

const when = h => {
  if (h.starts_at && h.ends_at) return `${date(h.starts_at)} – ${date(h.ends_at)}`;
  if (h.starts_at) return date(h.starts_at);
  if (h.ends_at) return `ends ${date(h.ends_at)}`;
  return "Date TBA";
};

const daysUntil = s => Math.ceil((new Date(s) - Date.now()) / 86400000);

function ago(iso) {
  const m = Math.round((Date.now() - new Date(iso)) / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.round(m / 60);
  if (h < 48) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

// ---------- cards ----------

const intCard = i => `
<div class="card">
<h3><a href="${esc(safeUrl(i.url))}" target="_blank" rel="noopener noreferrer">${esc(i.title)}</a></h3>
<div class="co">${esc(i.company) || "—"}</div>
<div class="meta">
<span class="pill">${fmt(i.location)}</span>
<span class="pill pay">${fmt(i.stipend)}</span>
${i.duration ? `<span class="pill">${fmt(i.duration)}</span>` : ""}
${i.posted ? `<span class="pill">${fmt(i.posted)}</span>` : ""}
</div>
</div>`;

function regPill(h) {
  if (!h.reg_ends_at) return "";
  const d = daysUntil(h.reg_ends_at);
  if (d < 0) return "";
  const label = d === 0 ? "Registration closes today" : `Registration closes in ${d} day${d === 1 ? "" : "s"}`;
  return `<span class="pill ${d <= 3 ? "warn" : ""}">${label}</span>`;
}

const hackCard = h => `
<div class="card">
<h3><a href="${esc(safeUrl(h.url))}" target="_blank" rel="noopener noreferrer">${esc(h.name)}</a></h3>
<div class="co">${h.is_online ? "Online" : esc(h.city || h.location_raw || "Location TBA")} · <span class="cap">${esc(h.status)}</span></div>
<div class="meta">
<span class="pill">${h.is_online ? "Remote" : "In person"}</span>
<span class="pill">${when(h)}</span>
<span class="pill pay">${h.participants_count} registered</span>
${regPill(h)}
${h.themes && h.themes !== "No Restrictions" ? `<span class="pill">${esc(h.themes)}</span>` : ""}
</div>
</div>`;

const section = (title, count, inner) => `
<section class="block">
<h2>${title} <span class="count">${count}</span></h2>
${inner}
</section>`;

const grid = (items, render, empty) =>
  items.length ? `<div class="grid">${items.map(render).join("")}</div>`
               : `<div class="empty">${empty}</div>`;

const searchBox = placeholder =>
  `<input id="search" class="search" type="search" placeholder="${placeholder}" autocomplete="off">`;

// ---------- view: internships ----------

function mountInternships(all) {
  const app = document.getElementById("app");
  if (!all.length) {
    app.innerHTML = `
    <header class="page-head"><h1>Internships</h1></header>
    <div class="empty">No data yet. Click <b>Refresh data</b> (top right) to fetch the latest listings.</div>`;
    return;
  }

  app.innerHTML = `
  <header class="page-head">
    <h1>Internships</h1>
    <p class="sub" id="int-sub"></p>
    ${searchBox("Search title, company or city…")}
  </header>
  <div id="results"></div>`;

  const draw = q => {
    const list = all.filter(i => matchQuery(q, i.title, i.company, i.location));
    const remote = list.filter(isRemote);
    const mumbai = list.filter(i => !isRemote(i) && isMumbai(i));
    const other = list.filter(i => !isRemote(i) && !isMumbai(i));
    document.getElementById("int-sub").textContent =
      `${list.length} of ${all.length} listings · Internshala`;
    document.getElementById("results").innerHTML =
      section("Mumbai", mumbai.length, grid(mumbai, intCard, "No Mumbai internships match.")) +
      section("Remote", remote.length, grid(remote, intCard, "No remote internships match.")) +
      (other.length ? section("Other", other.length, grid(other, intCard, "")) : "");
  };

  draw("");
  document.getElementById("search").oninput = e => draw(e.target.value);
}

// ---------- view: hackathons ----------

const matchFilter = (h, filter) => {
  if (filter === "online") return h.is_online;
  if (filter === "mumbai") return !h.is_online && isNearMumbai(h);
  if (filter === "person") return !h.is_online && h.in_india === true;
  if (filter.startsWith("src:")) return h.source === filter.slice(4);
  return true;
};

function mountHackathons(hacks) {
  const app = document.getElementById("app");
  if (!hacks.length) {
    app.innerHTML = `
    <header class="page-head"><h1>Hackathons</h1></header>
    <div class="empty">No open hackathons yet. Click <b>Refresh data</b> (top right) to fetch them.</div>`;
    return;
  }

  const filters = [["all", "All"], ["online", "Online"], ["mumbai", "Near Mumbai"], ["person", "In person"]];
  // only offer per-source filters when there is more than one source to choose from
  const sources = [...new Set(hacks.map(h => h.source))];
  if (sources.length > 1) sources.forEach(s => filters.push([`src:${s}`, `${s} only`]));

  let active = "all", q = "";

  app.innerHTML = `
  <header class="page-head">
    <h1>Hackathons</h1>
    <p class="sub" id="hack-sub"></p>
    ${searchBox("Search name, city or theme…")}
  </header>
  <div class="filters" id="hack-filters"></div>
  <div id="hack-list"></div>`;

  const draw = () => {
    const visible = h => matchQuery(q, h.name, h.city, h.location_raw, h.themes);
    document.getElementById("hack-filters").innerHTML = filters.map(([key, label]) => {
      const n = hacks.filter(h => visible(h) && matchFilter(h, key)).length;
      return `<button class="fbtn${key === active ? " on" : ""}" data-f="${esc(key)}">${esc(label)} <span class="count">${n}</span></button>`;
    }).join("");
    const list = hacks.filter(h => visible(h) && matchFilter(h, active));
    document.getElementById("hack-sub").textContent = `${list.length} of ${hacks.length} open events`;
    document.getElementById("hack-list").innerHTML = grid(list, hackCard, "Nothing matches right now.");
  };

  draw();
  document.getElementById("search").oninput = e => { q = e.target.value; draw(); };
  document.getElementById("hack-filters").onclick = e => {
    const btn = e.target.closest(".fbtn");
    if (!btn) return;
    active = btn.dataset.f;
    draw();
  };
}

// ---------- refresh button (lives in the nav, works on both pages) ----------

const setMsg = t => { document.getElementById("refresh-msg").textContent = t; };

async function showLastUpdated() {
  try {
    const s = await getJSON("/refresh/status");
    if (s.running) setMsg("Refresh in progress…");
    else if (s.last_finished) setMsg(`Updated ${ago(s.last_finished)}`);
  } catch { /* status is cosmetic */ }
}

async function waitForRefresh(before) {
  for (let i = 0; i < 150; i++) {            // up to ~5 minutes
    await sleep(2000);
    const s = await getJSON("/refresh/status");
    if (s.running) { setMsg("Scraping…"); continue; }
    if (s.last_started !== before) return s; // a newer run has finished
  }
  return null;
}

function bindRefresh() {
  const btn = document.getElementById("refresh");
  btn.onclick = async () => {
    btn.disabled = true;
    setMsg("Starting…");
    try {
      let before = (await getJSON("/refresh/status")).last_started;
      const r = await fetch("/refresh", { method: "POST" });
      const body = await r.json();

      if (r.status === 429) {
        setMsg(`Refreshed recently — try again in ${Math.ceil(body.retry_in / 60)} min`);
        return;
      }
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      if (body.status === "already_running") before = null;

      const s = await waitForRefresh(before);
      if (!s) setMsg("Still running — check back in a few minutes");
      else if (s.last_ok) {
        setMsg(`Done: ${s.new_internships} new internships, ${s.new_hackathons} new hackathons`);
        await route();
      } else setMsg(`Refresh failed: ${s.error || "see server logs"}`);
    } catch {
      setMsg("Refresh failed — try again");
    } finally {
      btn.disabled = false;
    }
  };
}

// ---------- router ----------

let renderId = 0; // ignores results from a page the user already navigated away from

async function route() {
  const id = ++renderId;
  const path = location.pathname.replace(/\/+$/, "") || "/";
  const app = document.getElementById("app");

  document.querySelectorAll("nav .links a").forEach(a =>
    a.classList.toggle("on", a.getAttribute("href") === path));
  document.title = (path === "/hackathons" ? "Hackathons" : "Internships") + " · Mumbai";
  app.innerHTML = `<div class="empty">Loading…</div>`;

  try {
    if (path === "/hackathons") {
      const hacks = await getJSON("/api/hackathons");
      if (id === renderId) mountHackathons(hacks);
    } else {
      const ints = await getJSON("/api/internships?limit=200");
      if (id === renderId) mountInternships(ints);
    }
  } catch {
    if (id !== renderId) return;
    app.innerHTML = `<div class="empty">Couldn't load data. <button id="retry" class="fbtn">Retry</button></div>`;
    document.getElementById("retry").onclick = route;
  }
}

document.addEventListener("click", e => {
  const a = e.target.closest("nav .links a, nav .brand");
  if (!a) return;
  e.preventDefault();
  history.pushState({}, "", a.getAttribute("href"));
  route();
});
window.addEventListener("popstate", route);

bindRefresh();
showLastUpdated();
route();
