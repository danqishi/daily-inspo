// 每日灵感：纯静态页面。数据在 data/index.json（所有日期的目录）和 data/日期.json（当天全文）。
const $app = document.getElementById("app");
const $lightbox = document.getElementById("lightbox");
let INDEX = null;

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const bjNow = () => new Date(Date.now() + 8 * 3600e3);
const todayBJ = () => bjNow().toISOString().slice(0, 10);

async function getJSON(url) {
  const r = await fetch(`${url}?v=${Date.now()}`);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

// 已读标记只存在这台设备的浏览器里
const readKey = (d, s, i) => `read:${d}:${s}:${i}`;
const isRead = (d, s, i) => localStorage.getItem(readKey(d, s, i)) === "1";
function toggleRead(d, s, i) {
  const k = readKey(d, s, i);
  if (localStorage.getItem(k)) localStorage.removeItem(k);
  else localStorage.setItem(k, "1");
  return isRead(d, s, i);
}

// 收藏也只存在这台设备的浏览器里；存一份标题、简介和缩略图，收藏夹不用再去加载当天的数据
const FAV_KEY = "favs";
const loadFavs = () => {
  try { return JSON.parse(localStorage.getItem(FAV_KEY)) || []; } catch { return []; }
};
const favId = (d, s, i) => `${d}|${s}|${i}`;
const isFav = (d, s, i) => loadFavs().some((f) => favId(f.d, f.s, f.i) === favId(d, s, i));
const DAY_CACHE = {};
function toggleFav(d, s, i) {
  let favs = loadFavs();
  const id = favId(d, s, i);
  if (favs.some((f) => favId(f.d, f.s, f.i) === id)) {
    favs = favs.filter((f) => favId(f.d, f.s, f.i) !== id);
  } else {
    const item = DAY_CACHE[d]?.sections?.find((x) => x.id === s)?.items?.[i] || {};
    favs.unshift({
      d, s, i: +i, t: item.title || "", sub: item.subtitle || "",
      m: (item.summary || "").slice(0, 80), img: item.images?.[0]?.src || "", at: Date.now(),
    });
  }
  localStorage.setItem(FAV_KEY, JSON.stringify(favs));
  return isFav(d, s, i);
}
const favLabel = (on) => (on ? "★ 已收藏" : "☆ 收藏");

const sectionMeta = (id) => (INDEX.sections || []).find((s) => s.id === id) || { id, name: id, emoji: "" };

function setNav(name) {
  document.querySelectorAll("[data-nav]").forEach((a) =>
    a.classList.toggle("on", a.dataset.nav === name || (name === "d" && a.dataset.nav === "day")));
}

async function route() {
  if (!INDEX) {
    try {
      INDEX = await getJSON("data/index.json");
    } catch {
      $app.innerHTML = '<div class="empty">还没有内容，第一次运行之后这里就会出现日报。</div>';
      return;
    }
  }
  const parts = decodeURIComponent(location.hash.slice(1)).split("/").filter(Boolean);
  setNav(parts[0] || "day");
  window.scrollTo(0, 0);
  if (parts[0] === "d") return renderDay(parts[1], parts[2]);
  if (parts[0] === "sections") return renderSectionList();
  if (parts[0] === "s") return renderSection(parts[1]);
  if (parts[0] === "favs") return renderFavs(parts[1]);
  if (parts[0] === "search") return renderSearch(parts.slice(1).join("/"));
  return renderHome();
}

function renderHome() {
  const days = INDEX.days || [];
  if (!days.length) {
    $app.innerHTML = '<div class="empty">还没有内容，第一次运行之后这里就会出现日报。</div>';
    return;
  }
  const latest = days[0];
  const good = days.find((d) => d.status !== "failed") || latest;
  let banner = "";
  if (latest.date < todayBJ()) {
    banner = bjNow().getUTCHours() >= 9
      ? `今天的内容还没更新，可能更新失败了。下面是 ${good.date} 的内容。`
      : `今天的内容正在生成，一般 8 点前完成。下面是 ${good.date} 的内容。`;
  } else if (latest.status === "failed") {
    banner = `今日更新失败，下面是 ${good.date} 的内容。`;
  }
  return renderDay(good.date, null, banner);
}

function imagesHTML(images) {
  if (!images?.length) return "";
  const figs = images.map((im) => `
    <figure>
      <img loading="lazy" src="${esc(im.src)}" data-full="${esc(im.full || im.src)}" alt="${esc(im.caption)}">
      <figcaption>${esc(im.caption)}${im.credit ? ` · ${im.page ? `<a href="${esc(im.page)}" target="_blank" rel="noopener">${esc(im.credit)}</a>` : esc(im.credit)}` : ""}</figcaption>
    </figure>`).join("");
  return `<div class="imgs${images.length === 1 ? " one" : ""}">${figs}</div>`;
}

function itemHTML(date, sec, item, i) {
  const read = isRead(date, sec.id, i);
  const fav = isFav(date, sec.id, i);
  return `
  <article class="card${read ? " read" : ""}" id="${esc(sec.id)}-${i}">
    ${item.badge ? `<span class="badge">${esc(item.badge)}</span>` : ""}
    <h3>${esc(item.title)}</h3>
    ${item.subtitle ? `<p class="sub">${esc(item.subtitle)}</p>` : ""}
    ${item.summary ? `<p class="summary">${esc(item.summary)}</p>` : ""}
    ${imagesHTML(item.images)}
    ${item.analysis?.length ? `<dl class="analysis">${item.analysis.map((a) =>
      `<div>${a.label ? `<dt>${esc(a.label)}</dt>` : ""}<dd>${esc(a.text)}</dd></div>`).join("")}</dl>` : ""}
    ${item.links?.length ? `<div class="links">${item.links.map((l) =>
      `<a href="${esc(l.url)}" target="_blank" rel="noopener">${esc(l.name)}</a>`).join("")}</div>` : ""}
    ${item.tags?.length ? `<div class="tags">${item.tags.map((t) => `<span>#${esc(t)}</span>`).join("")}</div>` : ""}
    ${item.source_note ? `<p class="note">${esc(item.source_note)}</p>` : ""}
    <div class="foot"><button class="favbtn${fav ? " on" : ""}" data-fav="${esc(date)}|${esc(sec.id)}|${i}">${favLabel(fav)}</button><button class="readbtn" data-read="${esc(date)}|${esc(sec.id)}|${i}">${read ? "已读 ✓" : "标为已读"}</button></div>
  </article>`;
}

async function renderDay(date, anchor, banner = "") {
  const days = INDEX.days || [];
  const idx = days.findIndex((d) => d.date === date);
  let data;
  try {
    data = await getJSON(`data/${date}.json`);
    DAY_CACHE[date] = data;
  } catch {
    $app.innerHTML = `<div class="empty">找不到 ${esc(date)} 的内容。</div>`;
    return;
  }
  const older = days[idx + 1], newer = idx > 0 ? days[idx - 1] : null;
  const options = days.map((d) => `<option value="${d.date}"${d.date === date ? " selected" : ""}>${d.date} ${d.weekday}</option>`).join("");
  let html = banner ? `<div class="banner">${esc(banner)}</div>` : "";
  if (data.status === "partial") html += '<div class="banner">今天有部分栏目没生成出来。</div>';
  html += `
    <div class="datebar">
      <a class="${older ? "" : "off"}" href="#/d/${older?.date || ""}">‹ 前一天</a>
      <h2>${+date.slice(5, 7)} 月 ${+date.slice(8)} 日<small>${esc(data.weekday || "")}</small></h2>
      <select id="datepick" aria-label="选择日期">${options}</select>
      <a class="${newer ? "" : "off"}" href="#/d/${newer?.date || ""}">后一天 ›</a>
    </div>`;
  for (const sec of data.sections || []) {
    html += `<div class="sec-title">${esc(sec.emoji)} ${esc(sec.name)}</div>`;
    if (sec.status !== "ok" || !sec.items?.length) {
      html += `<div class="card missing">${esc(sec.note || "今天这一栏暂缺")}</div>`;
      continue;
    }
    html += sec.items.map((it, i) => itemHTML(date, sec, it, i)).join("");
  }
  $app.innerHTML = html;
  document.getElementById("datepick").onchange = (e) => (location.hash = `#/d/${e.target.value}`);
  if (anchor) document.getElementById(anchor)?.scrollIntoView({ block: "start" });
}

function renderSectionList() {
  const counts = {};
  for (const d of INDEX.days || []) for (const it of d.items) counts[it.s] = (counts[it.s] || 0) + 1;
  $app.innerHTML = `<div class="sec-grid">${(INDEX.sections || []).map((s) =>
    `<a href="#/s/${s.id}"><b>${esc(s.emoji)}</b>${esc(s.name)}<br><small>共 ${counts[s.id] || 0} 条</small></a>`).join("")}</div>`;
}

function entryHTML(d, it, showSection) {
  const sec = sectionMeta(it.s);
  return `<a class="${isRead(d.date, it.s, it.i) ? "read" : ""}" href="#/d/${d.date}/${it.s}-${it.i}">
    <small>${d.date}${showSection ? ` · ${esc(sec.emoji)} ${esc(sec.name)}` : ""}</small><br>${esc(it.t)}
    ${it.m ? `<p>${esc(it.m)}</p>` : ""}</a>`;
}

function renderSection(id) {
  const sec = sectionMeta(id);
  const rows = [];
  for (const d of INDEX.days || []) for (const it of d.items) if (it.s === id) rows.push(entryHTML(d, it, false));
  $app.innerHTML = `<h2>${esc(sec.emoji)} ${esc(sec.name)}</h2>
    <div class="list">${rows.join("") || '<div class="empty">还没有内容</div>'}</div>`;
}

// 收藏夹：按栏目分类，顶部可切换只看某一类
function renderFavs(cat) {
  const favs = loadFavs();
  if (!favs.length) {
    $app.innerHTML = '<h2>★ 收藏夹</h2><div class="empty">还没有收藏。在每条内容下面点「☆ 收藏」就会出现在这里。</div>';
    return;
  }
  const order = (INDEX.sections || []).map((s) => s.id);
  const groups = {};
  for (const f of favs) (groups[f.s] ||= []).push(f);
  const cats = Object.keys(groups).sort((a, b) =>
    (order.indexOf(a) + 1 || 999) - (order.indexOf(b) + 1 || 999));
  if (cat && !groups[cat]) cat = "";
  const chip = (id, label, n) =>
    `<a class="${(cat || "") === id ? "on" : ""}" href="#/favs${id ? `/${id}` : ""}">${label}<small>${n}</small></a>`;
  const row = (f) => `<div class="fav-row">
    <a href="#/d/${f.d}/${f.s}-${f.i}">
      ${f.img ? `<img loading="lazy" src="${esc(f.img)}" alt="">` : ""}
      <span><small>${f.d}</small><br>${esc(f.t)}${f.sub ? `<p>${esc(f.sub)}</p>` : f.m ? `<p>${esc(f.m)}</p>` : ""}</span>
    </a>
    <button class="favbtn on" data-fav="${esc(f.d)}|${esc(f.s)}|${f.i}" title="取消收藏">★</button></div>`;
  const shown = cat ? [cat] : cats;
  $app.innerHTML = `<h2>★ 收藏夹</h2>
    <div class="chips">${chip("", "全部", favs.length)}${cats.map((id) => {
      const m = sectionMeta(id);
      return chip(id, `${esc(m.emoji)} ${esc(m.name)}`, groups[id].length);
    }).join("")}</div>
    ${shown.map((id) => {
      const m = sectionMeta(id);
      return `${cat ? "" : `<div class="sec-title">${esc(m.emoji)} ${esc(m.name)} · ${groups[id].length}</div>`}
        <div class="list">${groups[id].map(row).join("")}</div>`;
    }).join("")}`;
}

function renderSearch(q) {
  $app.innerHTML = `<input class="searchbox" id="q" type="search" placeholder="搜标题、标签、简介，比如：包豪斯、可灵、爵士" value="${esc(q)}">
    <div class="list" id="results"></div>`;
  const $q = document.getElementById("q");
  const update = () => {
    const words = $q.value.trim().toLowerCase().split(/\s+/).filter(Boolean);
    history.replaceState(null, "", `#/search/${encodeURIComponent($q.value)}`);
    if (!words.length) {
      document.getElementById("results").innerHTML = "";
      return;
    }
    const rows = [];
    for (const d of INDEX.days || []) {
      for (const it of d.items) {
        const hay = `${it.t} ${it.m} ${(it.g || []).join(" ")} ${sectionMeta(it.s).name}`.toLowerCase();
        if (words.every((w) => hay.includes(w))) rows.push(entryHTML(d, it, true));
        if (rows.length >= 200) break;
      }
    }
    document.getElementById("results").innerHTML = rows.join("") || '<div class="empty">没有找到</div>';
  };
  $q.oninput = update;
  update();
  $q.focus();
}

document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-read]");
  if (btn) {
    const [d, s, i] = btn.dataset.read.split("|");
    const read = toggleRead(d, s, i);
    btn.textContent = read ? "已读 ✓" : "标为已读";
    btn.closest(".card").classList.toggle("read", read);
    return;
  }
  const fb = e.target.closest("[data-fav]");
  if (fb) {
    const [d, s, i] = fb.dataset.fav.split("|");
    const on = toggleFav(d, s, i);
    if (location.hash.startsWith("#/favs")) {
      const y = window.scrollY;
      renderFavs(decodeURIComponent(location.hash).split("/")[2]);
      window.scrollTo(0, y);
    } else {
      fb.textContent = favLabel(on);
      fb.classList.toggle("on", on);
    }
    return;
  }
  const img = e.target.closest(".imgs img");
  if (img) {
    $lightbox.querySelector("img").src = img.dataset.full;
    $lightbox.hidden = false;
    return;
  }
  if (e.target.closest("#lightbox")) $lightbox.hidden = true;
});

window.addEventListener("hashchange", route);
route();
