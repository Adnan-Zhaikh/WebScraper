const fmt = s => s ? s.replace(/\s+/g, " ") : "—";
const date = s => s ? new Date(s).toLocaleDateString("en-IN", {day:"numeric", month:"short", year:"numeric"}) : "—";

const isRemote = i => /work\s*from\s*home|remote/i.test(i.location || "");
const isMumbai = i => /mumbai/i.test(i.location || "");

const NEAR_MUMBAI = ["mumbai","navi mumbai","thane","pune","panvel","kalyan","vasai","palghar","nashik"];
const isNearMumbai = h => {
  const t = `${h.city || ""} ${h.location_raw || ""}`.toLowerCase();
  return NEAR_MUMBAI.some(c => t.includes(c));
};

const intCard = i => `
  <div class="card">
    <h3><a href="${i.url}" target="_blank" rel="noopener">${i.title}</a></h3>
    <div class="co">${i.company || "—"}</div>
    <div class="meta">
      <span class="pill">${fmt(i.location)}</span>
      <span class="pill pay">${fmt(i.stipend)}</span>
      ${i.duration ? `<span class="pill">${fmt(i.duration)}</span>` : ""}
    </div>
  </div>`;

const hackCard = h => `
  <div class="card">
    <h3><a href="${h.url}" target="_blank" rel="noopener">${h.name}</a></h3>
    <div class="co">${h.is_online ? "Online" : (h.city || h.location_raw || "Location TBA")} · ${h.status}</div>
    <div class="meta">
      <span class="pill">${h.is_online ? "Remote" : "In person"}</span>
      <span class="pill">${date(h.starts_at)}</span>
      <span class="pill pay">${h.participants_count} registered</span>
      ${h.themes && h.themes !== "No Restrictions" ? `<span class="pill">${h.themes}</span>` : ""}
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

// ---------- view: internships ----------

async function internshipsView() {
  const ints = await fetch("/api/internships?limit=200").then(r => r.json());
  const remote = ints.filter(isRemote);
  const mumbai = ints.filter(i => isMumbai(i) && !isRemote(i));

  return `
    <header class="page-head">
      <h1>Internships</h1>
      <p class="sub">${ints.length} listings · Internshala</p>
      <button id="refresh" class="fbtn">Refresh data</button>
      <span id="refresh-msg" class="sub"></span>
    </header>
    ${section("Mumbai", mumbai.length, grid(mumbai, intCard, "No Mumbai internships right now."))}
    ${section("Remote", remote.length, grid(remote, intCard, "No remote internships right now."))}
  `;
}

// ---------- view: hackathons ----------

async function hackathonsView() {
  const hacks = await fetch("/api/hackathons").then(r => r.json());

  return `
    <header class="page-head">
      <h1>Hackathons</h1>
      <p class="sub">${hacks.length} events · Devfolio</p>
    </header>
    <div class="filters" id="hack-filters">
      <button class="fbtn on" data-f="all">All</button>
      <button class="fbtn" data-f="online">Online</button>
      <button class="fbtn" data-f="mumbai">Near Mumbai</button>
      <button class="fbtn" data-f="person">In person</button>
    </div>
    <div id="hack-list"></div>
  `;
}

function bindHackathons(hacks) {
  const render = filter => {
    const list = hacks.filter(h => {
      if (filter === "online") return h.is_online === 1;
      if (filter === "mumbai") return h.is_online === 0 && isNearMumbai(h);
      if (filter === "person") return h.is_online === 0 && h.in_india === 1;
      return true;
    });
    document.getElementById("hack-list").innerHTML =
      grid(list, hackCard, "Nothing here right now.");
  };

  render("all");
  document.querySelectorAll("#hack-filters .fbtn").forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll("#hack-filters .fbtn").forEach(b => b.classList.toggle("on", b === btn));
      render(btn.dataset.f);
    };
  });
}

// ---------- refresh button ----------

function bindRefresh() {
  const btn = document.getElementById("refresh");
  if (!btn) return;
  btn.onclick = async () => {
    const msg = document.getElementById("refresh-msg");
    btn.disabled = true;
    msg.textContent = "starting…";
    await fetch("/refresh", { method: "POST" });

    const poll = setInterval(async () => {
      const s = await fetch("/refresh/status").then(r => r.json());
      if (s.running) { msg.textContent = "scraping…"; return; }
      clearInterval(poll);
      msg.textContent = s.result?.ok ? "done — reloading" : "failed, check logs";
      btn.disabled = false;
      if (s.result?.ok) setTimeout(() => location.reload(), 800);
    }, 2000);
  };
}

// ---------- router ----------

async function route() {
  const path = location.pathname;
  const app = document.getElementById("app");
  document.querySelectorAll("nav .links a").forEach(a =>
    a.classList.toggle("on", a.getAttribute("href") === path));

  if (path === "/hackathons") {
    app.innerHTML = await hackathonsView();
    bindHackathons(await fetch("/api/hackathons").then(r => r.json()));
  } else {
    app.innerHTML = await internshipsView();
    bindRefresh();
  }
}

document.addEventListener("click", e => {
  const a = e.target.closest("nav .links a");
  if (!a) return;
  e.preventDefault();
  history.pushState({}, "", a.getAttribute("href"));
  route();
});
window.addEventListener("popstate", route);
route();
