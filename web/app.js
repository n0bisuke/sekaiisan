// 日本の世界遺産・国宝建造物マップ — Leaflet + OpenStreetMap
const DATA_URL = "data/heritage.json";

// tier -> {color, label, point} （heritage.json の tiers で上書きされる想成だがフォールバックも用意）
const TIERS = {
  "world":              { color: "#ffc400", label: "世界遺産",        point: 3 },
  "tentative_official": { color: "#7d8da1", label: "公式暫定リスト",  point: 2 },
  "tentative":          { color: "#b9c0c9", label: "暫定リスト候補",  point: 2 },
  "national_treasure":  { color: "#8a4b2e", label: "国宝建造物",      point: 1 },
  "geopark":            { color: "#c1440e", label: "世界ジオパーク",  point: 1 },
};
const TIER_ORDER = ["world", "tentative_official", "tentative", "national_treasure", "geopark"];
const CATEGORIES = ["文化遺産", "自然遺産", "混合遺産", "ジオパーク"];

const map = L.map("map").setView([36.2, 138.2], 5);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 19,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
}).addTo(map);

const clusters = L.markerClusterGroup({
  showCoverageOnHover: false,
  maxClusterRadius: 55,
  iconCreateFunction(c) {
    return L.divIcon({
      html: `<div class="heritage-cluster"><span>${c.getChildCount()}</span></div>`,
      className: "heritage-cluster-wrap", iconSize: [40, 40],
    });
  },
});
map.addLayer(clusters);

function refreshMapSize() { map.invalidateSize(); }
window.addEventListener("resize", refreshMapSize);
window.addEventListener("orientationchange", () => setTimeout(refreshMapSize, 200));
window.addEventListener("load", () => setTimeout(refreshMapSize, 100));
setTimeout(refreshMapSize, 300);

const listEl = document.getElementById("list");
const countEl = document.getElementById("count");
const searchEl = document.getElementById("search");
const prefEl = document.getElementById("prefFilter");
const tierField = document.getElementById("tierFilter");
const catField = document.getElementById("catFilter");

let ITEMS = [];
const markersById = new Map();
let activeId = null;
let activeTiers = new Set(TIER_ORDER);
let activeCats = new Set(CATEGORIES);

const styleTag = document.createElement("style");
styleTag.textContent = `
.heritage-cluster { width:40px;height:40px;border-radius:50%;background:#b8860b;color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;
  box-shadow:0 1px 4px rgba(0,0,0,.4);border:2px solid #fff; }`;
document.head.appendChild(styleTag);

function esc(t) {
  return String(t ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
function tierInfo(t) { return TIERS[t] || { color: "#888", label: t, point: 0 }; }

function pinIcon(color) {
  return L.divIcon({
    className: "heritage-pin",
    html: `<svg width="26" height="34" viewBox="0 0 28 36" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 0C6.3 0 0 6.3 0 14c0 10 14 22 14 22s14-12 14-22C28 6.3 21.7 0 14 0z" fill="${color}" stroke="#fff" stroke-width="1.5"/>
      <circle cx="14" cy="14" r="5.5" fill="#fff"/></svg>`,
    iconSize: [26, 34], iconAnchor: [13, 34], popupAnchor: [0, -32],
  });
}

function popupHtml(it) {
  const ti = tierInfo(it.tier);
  const hasLL = it.lat != null && it.lon != null;
  const dir = hasLL ? `https://www.google.com/maps/dir/?api=1&destination=${it.lat},${it.lon}` : "#";
  const sv = hasLL ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${it.lat},${it.lon}` : "#";
  const gsearch = `https://www.google.com/search?q=${encodeURIComponent(it.name)}`;
  const yearStr = it.year ? `${it.year}年登録` : "";
  const catStr = it.category || "";
  const headExtra = [catStr, yearStr].filter(Boolean).join("・");
  const bld = it.buildings && it.buildings.length
    ? `<p class="pnote">国宝建造物: ${esc(it.buildings.join("、"))}</p>` : "";
  const note = it.note ? `<p class="pnote">${esc(it.note)}</p>` : "";
  const sub = it.sub && !it.buildings.length ? `<p class="pnote">${esc(it.sub)}</p>` : "";
  return `
    <p class="pname"><span class="ptag" style="background:${ti.color}">${esc(ti.label)}</span> ${esc(it.name)}</p>
    ${headExtra ? `<p class="pcat">${esc(headExtra)}</p>` : ""}
    <p class="paddr">${esc(it.prefectures.join("・"))}</p>
    ${bld}${note}${sub}
    <div class="plinks">
      <a class="lk s" href="${esc(gsearch)}" target="_blank" rel="noopener">調べる</a>
      ${hasLL ? `<a class="lk g" href="${dir}" target="_blank" rel="noopener">経路</a>` : ""}
      ${hasLL ? `<a class="lk g" href="${sv}" target="_blank" rel="noopener">ストビュー</a>` : ""}
    </div>`;
}

function passesFilter(it) {
  if (!activeTiers.has(it.tier)) return false;
  if (!activeCats.has(it.category)) return false;
  const q = searchEl.value.trim().toLowerCase();
  if (q && !(it.name + " " + it.prefectures.join(" ") + " " + (it.note || "")).toLowerCase().includes(q)) return false;
  const pref = prefEl.value;
  if (pref && !it.prefectures.includes(pref)) return false;
  return true;
}

function buildMarkers() {
  clusters.clearLayers();
  markersById.clear();
  ITEMS.forEach(it => {
    if (it.lat == null || it.lon == null) return;
    if (!passesFilter(it)) return;
    const m = L.marker([it.lat, it.lon], { icon: pinIcon(tierInfo(it.tier).color), title: it.name });
    m.bindPopup(popupHtml(it), { maxWidth: 280 });
    m.on("click", () => setActive(it.id, false));
    m.itemId = it.id;
    clusters.addLayer(m);
    markersById.set(it.id, m);
  });
}

function buildPrefFilter() {
  const prefs = [...new Set(ITEMS.flatMap(it => it.prefectures).filter(Boolean))].sort();
  prefs.forEach(p => {
    const o = document.createElement("option");
    o.value = p; o.textContent = p;
    prefEl.appendChild(o);
  });
}

function buildTierFilter() {
  const counts = {};
  ITEMS.forEach(it => { counts[it.tier] = (counts[it.tier] || 0) + 1; });
  TIER_ORDER.forEach(t => {
    const id = "tf_" + t;
    const lbl = document.createElement("label");
    lbl.className = "brand-chip";
    const ti = tierInfo(t);
    lbl.innerHTML = `<input type="checkbox" data-tier="${esc(t)}" checked />
      <span class="dot" style="background:${ti.color}"></span>${esc(ti.label)}
      <em>${counts[t] || 0}</em>`;
    tierField.appendChild(lbl);
  });
  tierField.querySelectorAll("input[type=checkbox]").forEach(cb =>
    cb.addEventListener("change", () => {
      activeTiers = new Set([...tierField.querySelectorAll("input:checked")].map(c => c.dataset.tier));
      renderList(); buildMarkers();
    }));
}

function buildCatFilter() {
  const counts = {};
  ITEMS.forEach(it => { counts[it.category] = (counts[it.category] || 0) + 1; });
  CATEGORIES.forEach(c => {
    const lbl = document.createElement("label");
    lbl.className = "brand-chip";
    lbl.innerHTML = `<input type="checkbox" data-cat="${esc(c)}" checked />
      <span class="dot" style="background:#444"></span>${esc(c)}
      <em>${counts[c] || 0}</em>`;
    catField.appendChild(lbl);
  });
  catField.querySelectorAll("input[type=checkbox]").forEach(cb =>
    cb.addEventListener("change", () => {
      activeCats = new Set([...catField.querySelectorAll("input:checked")].map(c => c.dataset.cat));
      renderList(); buildMarkers();
    }));
}

function renderList() {
  const filtered = ITEMS.filter(passesFilter);
  listEl.innerHTML = "";
  const frag = document.createDocumentFragment();
  filtered.forEach(it => {
    const li = document.createElement("li");
    const ti = tierInfo(it.tier);
    li.className = (it.lat != null ? "has-coord " : "") + (it.id === activeId ? "active" : "");
    li.dataset.id = it.id;
    const meta = [it.category, it.prefectures.join("・"), it.year ? it.year + "年" : ""]
      .filter(Boolean).join("・");
    li.innerHTML = `
      <span class="name"><span class="dot" style="background:${ti.color}"></span>${esc(it.name)}</span>
      <span class="meta">${esc(meta)}</span>
      ${it.lat == null ? '<span class="badge">座標未取得</span>' : ''}`;
    li.addEventListener("click", () => setActive(it.id, true));
    frag.appendChild(li);
  });
  if (!filtered.length) {
    const li = document.createElement("li");
    li.style.cursor = "default";
    li.innerHTML = `<span class="meta">該当する物件がありません</span>`;
    frag.appendChild(li);
  }
  listEl.appendChild(frag);
  const withCoord = ITEMS.filter(it => it.lat != null).length;
  countEl.textContent = `${ITEMS.length}件中 ${withCoord}件を地図表示 ／ リスト ${filtered.length}件`;
}

function setActive(id, fly) {
  activeId = id;
  renderList();
  const li = listEl.querySelector(`li[data-id="${id}"]`);
  if (li) li.scrollIntoView({ block: "nearest", behavior: "smooth" });
  const m = markersById.get(id);
  if (m && fly) {
    if (window.matchMedia("(max-width: 720px)").matches) closeSidebarDrawer();
    clusters.zoomToShowLayer(m, () => m.openPopup());
  } else if (m) m.openPopup();
}

/* ===== Ranking (per-prefecture points) ===== */
const PREF_ORDER = [
  "北海道","青森県","岩手県","宮城県","秋田県","山形県","福島県",
  "茨城県","栃木県","群馬県","埼玉県","千葉県","東京都","神奈川県",
  "新潟県","富山県","石川県","福井県","山梨県","長野県",
  "岐阜県","静岡県","愛知県","三重県",
  "滋賀県","京都府","大阪府","兵庫県","奈良県","和歌山県",
  "鳥取県","島根県","岡山県","広島県","山口県",
  "徳島県","香川県","愛媛県","高知県",
  "福岡県","佐賀県","長崎県","熊本県","大分県","宮崎県","鹿児島県","沖縄県",
];

function computeRanking() {
  const sc = {};
  PREF_ORDER.forEach(p => { sc[p] = { pref: p, point: 0, world: 0, tentative: 0, national: 0, geopark: 0, count: 0 }; });
  ITEMS.forEach(it => {
    if (it.point <= 0) return; // overlap は上位がAlready加点済み → 加算しない
    it.prefectures.forEach(p => {
      if (!sc[p]) sc[p] = { pref: p, point: 0, world: 0, tentative: 0, national: 0, geopark: 0, count: 0 };
      const r = sc[p];
      r.point += it.point;
      r.count += 1;
      if (it.tier === "world") r.world += 1;
      else if (it.tier === "tentative" || it.tier === "tentative_official") r.tentative += 1;
      else if (it.tier === "national_treasure") r.national += 1;
      else if (it.tier === "geopark") r.geopark += 1;
    });
  });
  return Object.values(sc);
}

let rankSort = "point";
function renderRanking() {
  const rows = computeRanking();
  rows.sort((a, b) => {
    if (rankSort === "world") return b.world - a.world || b.point - a.point;
    if (rankSort === "count") return b.count - a.count || b.point - a.point;
    return b.point - a.point || b.world - a.world || b.count - a.count;
  });
  rows.forEach((r, i) => { r.rank = i + 1; });
  const tb = document.querySelector("#rankingTable tbody");
  tb.innerHTML = "";
  const frag = document.createDocumentFragment();
  const maxPt = Math.max(...rows.map(r => r.point));
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.dataset.pref = r.pref;
    const medal = r.rank === 1 ? "🥇" : r.rank === 2 ? "🥈" : r.rank === 3 ? "🥉" : r.rank;
    const barW = maxPt ? (r.point / maxPt * 100).toFixed(1) : 0;
    const z = (n) => n ? n : `<span class="zero">0</span>`;
    tr.innerHTML = `
      <td class="r">${medal}</td>
      <td class="pt">
        <div class="devbar"><span style="width:${barW}%;background:#b8860b"></span></div>
        <b>${r.point}</b>
      </td>
      <td class="pref">${esc(r.pref)}</td>
      <td class="n">${r.world ? r.world : '<span class="zero">0</span>'}</td>
      <td class="n">${z(r.tentative)}</td>
      <td class="n">${z(r.national)}</td>
      <td class="n">${z(r.geopark)}</td>
      <td class="n">${r.count}</td>`;
    tr.addEventListener("click", () => {
      prefEl.value = r.pref;
      searchEl.value = "";
      // この都道府県の tier/cat フィルタは維持したままリスト表示
      renderList(); buildMarkers();
      switchView("map");
      const ms = ITEMS.filter(it => it.prefectures.includes(r.pref) && it.lat != null && passesFilter(it));
      if (ms.length) {
        const lats = ms.map(s => s.lat), lons = ms.map(s => s.lon);
        map.fitBounds([[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], { padding: [40, 40] });
      }
    });
    frag.appendChild(tr);
  });
  tb.appendChild(frag);
  const top = rows[0];
  const total = rows.reduce((a, b) => a + b.point, 0);
  document.getElementById("rankingSummary").innerHTML =
    `全国合計 <b>${total}</b> pt ／ 1位 <b>${esc(top.pref)}</b>（${top.point} pt／世界遺産${top.world}・暫定${top.tentative}・国宝${top.national}・ジオパーク${top.geopark}）`;
}

/* tab switching */
function switchView(view) {
  const isMap = view === "map";
  document.querySelectorAll(".tab").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.getElementById("app").classList.toggle("hidden", !isMap);
  document.getElementById("rankingView").classList.toggle("hidden", isMap);
  if (isMap) { setTimeout(() => map.invalidateSize(), 50); }
}
document.querySelectorAll(".tab").forEach(b =>
  b.addEventListener("click", () => switchView(b.dataset.view)));

/* mobile sidebar drawer */
const sidebarEl = document.getElementById("sidebar");
const sidebarOpenBtn = document.getElementById("sidebarOpen");
const sidebarCloseBtn = document.getElementById("sidebarClose");
function closeSidebarDrawer() { sidebarEl.classList.add("closed"); setTimeout(refreshMapSize, 260); }
function openSidebarDrawer() { sidebarEl.classList.remove("closed"); }
sidebarOpenBtn && sidebarOpenBtn.addEventListener("click", openSidebarDrawer);
sidebarCloseBtn && sidebarCloseBtn.addEventListener("click", closeSidebarDrawer);
if (window.matchMedia("(max-width: 720px)").matches) { sidebarEl.classList.add("closed"); }

document.querySelectorAll(".sortbtn").forEach(b =>
  b.addEventListener("click", () => {
    rankSort = b.dataset.sort;
    document.querySelectorAll(".sortbtn").forEach(x => x.classList.toggle("active", x === b));
    renderRanking();
  }));

/* load */
fetch(DATA_URL)
  .then(r => r.json())
  .then(data => {
    if (data.tiers) Object.assign(TIERS, data.tiers);
    ITEMS = data.items || [];
    buildMarkers();
    buildPrefFilter();
    buildTierFilter();
    buildCatFilter();
    renderList();
    renderRanking();
  })
  .catch(err => {
    countEl.textContent = "データの読み込みに失敗しました（heritage.json）";
    console.error(err);
  });

let t;
searchEl.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { renderList(); buildMarkers(); }, 120); });
prefEl.addEventListener("change", () => { renderList(); buildMarkers(); });