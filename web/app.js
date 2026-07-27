// コメリ 全店舗マップ — Leaflet + OpenStreetMap
const DATA_URL = "data/all_stores.json";

// brand -> {color, label}
const BRANDS = {
  "コメリ":                  { color: "#00873c", label: "コメリ" },
  "コメリPRO":               { color: "#1f6feb", label: "コメリPRO" },
  "コメリパワー":            { color: "#e8590c", label: "コメリパワー" },
  "コメリハード＆グリーン":   { color: "#7048e8", label: "コメリH&G" },
  "コメリリフォーム":        { color: "#e64980", label: "コメリリフォーム" },
  "その他":                  { color: "#868e96", label: "その他" },
};

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
      html: `<div class="komeri-cluster"><span>${c.getChildCount()}</span></div>`,
      className: "komeri-cluster-wrap", iconSize: [40, 40],
    });
  },
});
map.addLayer(clusters);

// モバイルではCSSの dvh 反映やアドレスバーの表示/非表示でコンテナサイズが
// 初期化直後と食い違い、タイルが空白のまま描画されないことがあるため、
// リサイズ・向き変更・初回ロード完了時に地図の内部サイズ計算をやり直す。
function refreshMapSize() { map.invalidateSize(); }
window.addEventListener("resize", refreshMapSize);
window.addEventListener("orientationchange", () => setTimeout(refreshMapSize, 200));
window.addEventListener("load", () => setTimeout(refreshMapSize, 100));
setTimeout(refreshMapSize, 300);

const listEl = document.getElementById("list");
const countEl = document.getElementById("count");
const searchEl = document.getElementById("search");
const prefEl = document.getElementById("prefFilter");
const onlyMappedEl = document.getElementById("onlyMapped");
const brandField = document.getElementById("brandFilter");

let STORES = [];
const markersById = new Map();
let activeId = null;
let activeBrands = new Set(Object.keys(BRANDS));

// cluster + pin styles
const styleTag = document.createElement("style");
styleTag.textContent = `
.komeri-cluster { width:40px;height:40px;border-radius:50%;background:#00873c;color:#fff;
  display:flex;align-items:center;justify-content:center;font-weight:700;font-size:14px;
  box-shadow:0 1px 4px rgba(0,0,0,.4);border:2px solid #fff; }`;
document.head.appendChild(styleTag);

function esc(t) {
  return String(t ?? "").replace(/[&<>"']/g, c => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

function brandInfo(b) { return BRANDS[b] || BRANDS["その他"]; }

function pinIcon(color) {
  return L.divIcon({
    className: "komeri-pin",
    html: `<svg width="26" height="34" viewBox="0 0 28 36" xmlns="http://www.w3.org/2000/svg">
      <path d="M14 0C6.3 0 0 6.3 0 14c0 10 14 22 14 22s14-12 14-22C28 6.3 21.7 0 14 0z" fill="${color}" stroke="#fff" stroke-width="1.5"/>
      <circle cx="14" cy="14" r="5.5" fill="#fff"/></svg>`,
    iconSize: [26, 34], iconAnchor: [13, 34], popupAnchor: [0, -32],
  });
}

function telDisp(t) {
  if (!t) return "";
  const d = t.replace(/\D/g, "");
  if (d.length >= 10) return d.replace(/(\d{2,4})(\d{2,4})(\d{3,4})/, "$1-$2-$3");
  return t;
}

function popupHtml(s) {
  const bi = brandInfo(s.brand);
  const hasLL = s.lat != null && s.lon != null;
  const dir = hasLL ? `https://www.google.com/maps/dir/?api=1&destination=${s.lat},${s.lon}` : "#";
  const sv = hasLL ? `https://www.google.com/maps/@?api=1&map_action=pano&viewpoint=${s.lat},${s.lon}` : "#";
  return `
    <p class="pname"><span class="ptag" style="background:${bi.color}">${esc(bi.label)}</span> ${esc(s.name)}</p>
    <p class="paddr">${esc(s.address)}</p>
    ${s.tel ? `<p class="ptel">☎ <a href="tel:${esc(s.tel)}">${telDisp(s.tel)}</a></p>` : ""}
    <div class="plinks">
      <a class="lk" href="${esc(s.url)}" target="_blank" rel="noopener">店舗詳細</a>
      ${hasLL ? `<a class="lk g" href="${dir}" target="_blank" rel="noopener">経路</a>` : ""}
      ${hasLL ? `<a class="lk g" href="${sv}" target="_blank" rel="noopener">ストリートビュー</a>` : ""}
    </div>`;
}

function buildMarkers() {
  clusters.clearLayers();
  markersById.clear();
  STORES.forEach(s => {
    if (s.lat == null || s.lon == null) return;
    const m = L.marker([s.lat, s.lon], { icon: pinIcon(brandInfo(s.brand).color), title: s.name });
    m.bindPopup(popupHtml(s), { maxWidth: 280 });
    m.on("click", () => setActive(s.id, false));
    m.storeId = s.id;
    clusters.addLayer(m);
    markersById.set(s.id, m);
  });
}

function buildPrefFilter() {
  const prefs = [...new Set(STORES.map(s => s.prefecture).filter(Boolean))].sort();
  prefs.forEach(p => {
    const o = document.createElement("option");
    o.value = p; o.textContent = p;
    prefEl.appendChild(o);
  });
}

function buildBrandFilter() {
  const counts = {};
  STORES.forEach(s => { counts[s.brand] = (counts[s.brand] || 0) + 1; });
  Object.keys(BRANDS).forEach(b => {
    if (b === "その他" && !counts[b]) return;
    const id = "bf_" + b.replace(/[^a-zA-Z]/g, "");
    const lbl = document.createElement("label");
    lbl.className = "brand-chip";
    const bi = BRANDS[b];
    lbl.innerHTML = `<input type="checkbox" data-brand="${esc(b)}" checked />
      <span class="dot" style="background:${bi.color}"></span>${esc(bi.label)}
      <em>${counts[b] || 0}</em>`;
    brandField.appendChild(lbl);
  });
  brandField.querySelectorAll("input[type=checkbox]").forEach(cb =>
    cb.addEventListener("change", () => {
      activeBrands = new Set(
        [...brandField.querySelectorAll("input:checked")].map(c => c.dataset.brand));
      renderList();
      applyMarkerVisibility();
    }));
}

function applyMarkerVisibility() {
  const q = searchEl.value.trim().toLowerCase();
  const pref = prefEl.value;
  const onlyMapped = onlyMappedEl.checked;
  clusters.clearLayers();
  markersById.clear();
  STORES.forEach(s => {
    if (s.lat == null) return;
    if (!activeBrands.has(s.brand)) return;
    if (pref && s.prefecture !== pref) return;
    if (q && !(s.name + " " + s.address + " " + s.prefecture).toLowerCase().includes(q)) return;
    const m = L.marker([s.lat, s.lon], { icon: pinIcon(brandInfo(s.brand).color), title: s.name });
    m.bindPopup(popupHtml(s), { maxWidth: 280 });
    m.on("click", () => setActive(s.id, false));
    m.storeId = s.id;
    clusters.addLayer(m);
    markersById.set(s.id, m);
  });
}

function renderList() {
  const q = searchEl.value.trim().toLowerCase();
  const pref = prefEl.value;
  const onlyMapped = onlyMappedEl.checked;
  const filtered = STORES.filter(s => {
    if (onlyMapped && s.lat == null) return false;
    if (!activeBrands.has(s.brand)) return false;
    if (pref && s.prefecture !== pref) return false;
    if (q && !(s.name + " " + s.address + " " + s.prefecture).toLowerCase().includes(q)) return false;
    return true;
  });
  listEl.innerHTML = "";
  const frag = document.createDocumentFragment();
  filtered.forEach(s => {
    const li = document.createElement("li");
    const bi = brandInfo(s.brand);
    li.className = (s.lat != null ? "has-coord" : "") + (s.id === activeId ? " active" : "");
    li.dataset.id = s.id;
    li.innerHTML = `
      <span class="name"><span class="dot" style="background:${bi.color}"></span>${esc(s.name)}</span>
      <span class="addr">${esc(s.address) || esc(s.prefecture)}</span>
      ${s.lat == null ? '<span class="badge">座標未取得</span>' : ''}`;
    li.addEventListener("click", () => setActive(s.id, true));
    frag.appendChild(li);
  });
  if (!filtered.length) {
    const li = document.createElement("li");
    li.style.cursor = "default";
    li.innerHTML = `<span class="addr">該当する店舗がありません</span>`;
    frag.appendChild(li);
  }
  listEl.appendChild(frag);
  const withCoord = STORES.filter(s => s.lat != null).length;
  countEl.textContent = `${STORES.length}店舗中 ${withCoord}店舗を地図表示 ／ リスト ${filtered.length}件`;
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

fetch(DATA_URL)
  .then(r => r.json())
  .then(data => {
    STORES = data;
    buildMarkers();
    buildPrefFilter();
    buildBrandFilter();
    renderList();
    return fetch("data/population.json").then(r => r.json());
  })
  .then(popData => {
    POP = popData.population || popData;
    POP_YEAR = popData.year || "";
    renderRanking();
  })
  .catch(err => {
    countEl.textContent = "データの読み込みに失敗しました（all_stores.json）";
    console.error(err);
  });

let t;
searchEl.addEventListener("input", () => { clearTimeout(t); t = setTimeout(() => { renderList(); applyMarkerVisibility(); }, 120); });
prefEl.addEventListener("change", () => { renderList(); applyMarkerVisibility(); });
onlyMappedEl.addEventListener("change", () => { renderList(); applyMarkerVisibility(); });

/* ===== Ranking view (deviation value per capita) ===== */
let POP = null, POP_YEAR = "";
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
  STORES.forEach(s => { sc[s.prefecture] = (sc[s.prefecture] || 0) + 1; });
  const rows = (POP ? PREF_ORDER : Object.keys(sc)).map(p => {
    const n = sc[p] || 0;
    const ppl = POP ? (POP[p] || 0) : 0;
    const per100k = ppl ? n / ppl * 100000 : 0;
    return { pref: p, stores: n, pop: ppl, per100k };
  });
  const xs = rows.map(r => r.per100k);
  const mean = xs.reduce((a, b) => a + b, 0) / xs.length;
  const variance = xs.reduce((a, b) => a + (b - mean) ** 2, 0) / xs.length;
  const std = Math.sqrt(variance);
  rows.forEach(r => { r.dev = std ? 50 + 10 * (r.per100k - mean) / std : 50; });
  return { rows, mean, std };
}

function devColor(dev) {
  // map dev (~38..75) to a green intensity
  if (dev >= 65) return "#00873c";
  if (dev >= 58) return "#2e9b44";
  if (dev >= 52) return "#6bb16a";
  if (dev >= 48) return "#b0c4a8";
  return "#cfd6cb";
}

function fmt(n) { return n.toLocaleString("ja-JP"); }

let rankSort = "dev";

function renderRanking() {
  if (!POP) return;
  const { rows, mean, std } = computeRanking();
  rows.sort((a, b) => rankSort === "stores" ? b.stores - a.stores : b.dev - a.dev);
  rows.forEach((r, i) => { r.rank = i + 1; });
  const tb = document.querySelector("#rankingTable tbody");
  tb.innerHTML = "";
  const frag = document.createDocumentFragment();
  const maxDev = Math.max(...rows.map(r => r.dev));
  const minDev = Math.min(...rows.map(r => r.dev));
  rows.forEach(r => {
    const tr = document.createElement("tr");
    tr.dataset.pref = r.pref;
    const medal = r.rank === 1 ? "🥇" : r.rank === 2 ? "🥈" : r.rank === 3 ? "🥉" : r.rank;
    const barW = ((r.dev - minDev) / (maxDev - minDev) * 100).toFixed(1);
    const col = devColor(r.dev);
    tr.innerHTML = `
      <td class="r">${medal}</td>
      <td class="dev">
        <div class="devbar"><span style="width:${barW}%;background:${col}"></span></div>
        <b style="color:${col === '#cfd6cb' ? '#6b756c' : col}">${r.dev.toFixed(1)}</b>
      </td>
      <td class="pref">${esc(r.pref)}</td>
      <td class="n">${r.stores}</td>
      <td class="pop">${fmt(r.pop)}</td>
      <td class="per">${r.per100k.toFixed(2)}</td>`;
    tr.addEventListener("click", () => {
      prefEl.value = r.pref;
      // clear brand/text filters for a clean prefecture view
      searchEl.value = "";
      renderList(); applyMarkerVisibility();
      switchView("map");
      // focus map on the prefecture's markers
      const ms = STORES.filter(s => s.prefecture === r.pref && s.lat != null);
      if (ms.length) {
        const lats = ms.map(s => s.lat), lons = ms.map(s => s.lon);
        map.fitBounds([[Math.min(...lats), Math.min(...lons)], [Math.max(...lats), Math.max(...lons)]], { padding: [40, 40] });
      }
    });
    frag.appendChild(tr);
  });
  tb.appendChild(frag);
  const top = rows[0];
  const lead = rankSort === "stores"
    ? `最多 <b style="color:${devColor(top.dev)}">${top.pref}</b>（${top.stores}店／${fmt(top.pop)}人／偏差値${top.dev.toFixed(1)}）`
    : `最高 <b style="color:${devColor(top.dev)}">${top.pref} 偏差値${top.dev.toFixed(1)}</b>（${top.stores}店／${fmt(top.pop)}人／${top.per100k.toFixed(2)}店/10万人）`;
  document.getElementById("rankingSummary").innerHTML =
    `全国平均 <b>${mean.toFixed(2)}</b> 店/10万人（標準偏差 ${std.toFixed(2)}） ／ ${lead}` +
    (POP_YEAR ? ` ／ 人口: ${POP_YEAR}年推計` : "");
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

/* mobile sidebar drawer (list <-> full-screen map) */
const sidebarEl = document.getElementById("sidebar");
const sidebarOpenBtn = document.getElementById("sidebarOpen");
const sidebarCloseBtn = document.getElementById("sidebarClose");

function closeSidebarDrawer() {
  sidebarEl.classList.add("closed");
  setTimeout(refreshMapSize, 260); // wait for the CSS transform transition to finish
}
function openSidebarDrawer() {
  sidebarEl.classList.remove("closed");
}
sidebarOpenBtn && sidebarOpenBtn.addEventListener("click", openSidebarDrawer);
sidebarCloseBtn && sidebarCloseBtn.addEventListener("click", closeSidebarDrawer);
// start closed (map-first) on narrow screens
if (window.matchMedia("(max-width: 720px)").matches) {
  sidebarEl.classList.add("closed");
}

document.querySelectorAll(".sortbtn").forEach(b =>
  b.addEventListener("click", () => {
    rankSort = b.dataset.sort;
    document.querySelectorAll(".sortbtn").forEach(x => x.classList.toggle("active", x === b));
    renderRanking();
  }));