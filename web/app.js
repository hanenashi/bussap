const $ = (id) => document.getElementById(id);
const names = { chuo: "北海道中央バス", jr: "JR北海道バス", jotetsu: "じょうてつ" };
const operators = ["chuo", "jr", "jotetsu"];
const state = { operator: "all", stop: null, pattern: null, routeFilter: null, date: null, searchSerial: 0, loadSerial: 0 };
const tokyoParts = new Intl.DateTimeFormat("en-US", { timeZone: "Asia/Tokyo", year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

function tokyoNow() {
  const parts = Object.fromEntries(tokyoParts.formatToParts(new Date()).filter(p => p.type !== "literal").map(p => [p.type, p.value]));
  return { date: `${parts.year}-${parts.month}-${parts.day}`, time: `${parts.hour}:${parts.minute}` };
}
function nextDay(iso) { const d = new Date(`${iso}T12:00:00+09:00`); d.setUTCDate(d.getUTCDate() + 1); const p = Object.fromEntries(tokyoParts.formatToParts(d).filter(v => v.type !== "literal").map(v => [v.type, v.value])); return `${p.year}-${p.month}-${p.day}`; }
function dateLabel(iso) { const [, m, d] = iso.split("-"); return `${Number(m)}/${Number(d)}`; }
function distanceFromSapporo(stop) {
  if (stop.lat == null || stop.lon == null) return null;
  const radians = degrees => degrees * Math.PI / 180;
  const deltaLat = radians(stop.lat - 43.0687), deltaLon = radians(stop.lon - 141.3508);
  const a = Math.sin(deltaLat / 2) ** 2 + Math.cos(radians(43.0687)) * Math.cos(radians(stop.lat)) * Math.sin(deltaLon / 2) ** 2;
  return 12742 * Math.asin(Math.sqrt(a));
}
function locationLabel(stop) {
  const km = distanceFromSapporo(stop);
  return km == null ? "" : `札幌駅から直線約${km < 10 ? km.toFixed(1) : Math.round(km)}km`;
}
function setPanel(panel) { for (const id of ["map-panel", "search-panel", "pattern-panel", "departure-panel"]) $(id).hidden = id !== panel; $("favorites-section").hidden = panel !== "map-panel" || !favorites.length; if (panel === "map-panel") BUSSAPMap.show(); }
function setStatus(id, message, error = false) { const el = $(id); el.hidden = !message; el.textContent = message || ""; el.classList.toggle("error", error); }
function clear(el) { el.replaceChildren(); }
function make(tag, className, value) { const el = document.createElement(tag); if (className) el.className = className; if (value != null) el.textContent = value; return el; }
function displayTime(value) { const [hour, minute] = value.split(":"); return `${String(Number(hour) % 24).padStart(2, "0")}:${minute}`; }
function serviceMinutes(value) { const [hour, minute] = value.split(":"); return Number(hour) * 60 + Number(minute); }
function jrNotice(data) {
  if (data.warning !== "cant promise correct times now") return data.warning || "";
  const revision = String(data.source_revision || "");
  return /^\d{8}$/.test(revision)
    ? `JR時刻表: ${revision.slice(0, 4)}/${revision.slice(4, 6)}/${revision.slice(6, 8)}改正データ。選択日の運行は未確認です。`
    : "JR時刻表: 改正日が不明です。選択日の運行は未確認です。";
}
function routeLabel(name) { return name.match(/\[([^\]]+)\]/)?.[1] || name.match(/^[^0-9０-９]{0,3}[0-9０-９]+[A-Za-zＡ-Ｚａ-ｚ]?/u)?.[0] || name.split(/[・･]/)[0]; }
async function get(path, params) { const response = await fetch(`${path}?${new URLSearchParams(params)}`, { cache: "no-store" }); const body = await response.json(); if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`); return body; }

const FAVORITES_KEY = "bussap.favorites.v1";
const MAX_FAVORITES = 12;
function cleanFavorite(item) {
  const source = item?.stop;
  if (!source || !operators.includes(source.operator) || typeof source.id !== "string" ||
      !source.id.startsWith(`${source.operator}:`) || source.id.length > 100 ||
      typeof source.name !== "string" || !source.name || source.name.length > 100) return null;
  const stop = { id: source.id, name: source.name, operator: source.operator,
    lat: Number.isFinite(source.lat) ? source.lat : null, lon: Number.isFinite(source.lon) ? source.lon : null,
    boarding_position: source.boarding_position == null ? null : String(source.boarding_position).slice(0, 20) };
  if (source.operator === "jr" && source.station_id != null) stop.station_id = String(source.station_id).slice(0, 20);
  let pattern = null;
  if (source.operator === "jr") {
    const value = item.pattern;
    if (!value || typeof value.pattern !== "string" || !value.pattern || value.pattern.length > 80 ||
        typeof value.route !== "string" || value.route.length > 100 ||
        value.direction != null && (typeof value.direction !== "string" || value.direction.length > 100)) return null;
    pattern = { pattern: value.pattern, route: value.route, direction: value.direction || "",
      boarding_position: value.boarding_position == null ? null : String(value.boarding_position).slice(0, 20) };
  }
  const routeFilter = source.operator !== "jr" && typeof item.routeFilter === "string" && item.routeFilter.length <= 40 ? item.routeFilter : null;
  return { stop, pattern, routeFilter };
}
function favoriteKey(item) { return JSON.stringify([item.stop.id, item.pattern?.pattern || "", item.routeFilter || ""]); }
function readFavorites() {
  try {
    const value = JSON.parse(localStorage.getItem(FAVORITES_KEY) || "[]");
    if (!Array.isArray(value)) return [];
    const unique = new Map();
    for (const raw of value) { const item = cleanFavorite(raw); if (item) unique.set(favoriteKey(item), item); }
    return [...unique.values()].slice(0, MAX_FAVORITES);
  } catch { return []; }
}
let favorites = readFavorites();
function currentFavorite() { return state.stop ? cleanFavorite({ stop: state.stop, pattern: state.pattern, routeFilter: state.routeFilter }) : null; }
function updateFavoriteButton() {
  const item = currentFavorite(), saved = item && favorites.some(entry => favoriteKey(entry) === favoriteKey(item));
  const button = $("favorite-button");
  button.disabled = !item;
  button.setAttribute("aria-pressed", String(Boolean(saved)));
  button.textContent = saved ? "★ 保存済み · タップで解除" : `☆ ${state.routeFilter ? `${state.routeFilter}を保存` : state.pattern ? "この路線を保存" : "この乗り場を保存"}`;
}
function renderFavorites() {
  clear($("favorites-list"));
  for (const item of favorites) {
    const stop = item.stop, position = item.pattern?.boarding_position || stop.boarding_position;
    const title = `${stop.name}${position ? ` · ${position}番のりば` : ""}`;
    const detail = `${names[stop.operator]} · ${item.pattern ? `${routeLabel(item.pattern.route)} → ${item.pattern.direction || "行先不明"}` : item.routeFilter ? `${item.routeFilter}のバス` : "すべての路線"}`;
    const button = make("button", "favorite-card"); button.type = "button";
    const content = make("span"); content.append(make("strong", "", title), make("small", "", detail));
    button.append(content, make("span", "chevron", "›"));
    button.addEventListener("click", () => openFavorite(item));
    $("favorites-list").append(button);
  }
  $("favorites-section").hidden = $("map-panel").hidden || !favorites.length;
  updateFavoriteButton();
}
function toggleFavorite() {
  const item = currentFavorite();
  if (!item) return;
  const key = favoriteKey(item), saved = favorites.some(entry => favoriteKey(entry) === key);
  const next = saved ? favorites.filter(entry => favoriteKey(entry) !== key) : [item, ...favorites].slice(0, MAX_FAVORITES);
  try { localStorage.setItem(FAVORITES_KEY, JSON.stringify(next)); }
  catch { $("favorite-button").textContent = "このブラウザでは保存できません"; return; }
  favorites = next;
  renderFavorites();
}
function openFavorite(item) {
  clearTimeout(searchTimer); ++state.searchSerial;
  $("stop-search").value = "";
  state.stop = { ...item.stop }; state.pattern = item.pattern ? { ...item.pattern } : null;
  state.routeFilter = item.routeFilter; state.date = tokyoNow().date;
  BUSSAPMap.focus(state.stop);
  loadDepartures();
}

function resultButton(title, detail, action) {
  const button = make("button", "result-button"); button.type = "button";
  const content = make("span"); content.append(make("strong", "", title), make("small", "", detail));
  button.append(content, make("span", "chevron", "›")); button.addEventListener("click", action);
  return button;
}

let searchTimer;
function queueSearch() { ++state.searchSerial; clearTimeout(searchTimer); searchTimer = setTimeout(search, 320); }
async function search() {
  const term = $("stop-search").value.trim();
  const serial = ++state.searchSerial;
  state.stop = null; state.pattern = null; state.routeFilter = null; setPanel(term ? "search-panel" : "map-panel"); clear($("search-results"));
  if (term.length < 2) { setStatus("search-status", term ? "2文字以上入力してください。" : ""); return; }
  setStatus("search-status", "バス停を探しています…");
  const choices = state.operator === "all" ? operators : [state.operator];
  const results = new Map();
  for (const operator of choices) {
    get("/api/stops", { operator, name: term, limit: "30" })
      .then(data => { results.set(operator, data); renderSearchResults(serial, choices, results); })
      .catch(() => { results.set(operator, null); renderSearchResults(serial, choices, results); });
  }
}
function renderSearchResults(serial, choices, results) {
  if (serial !== state.searchSerial) return;
  const list = choices.flatMap(operator => (results.get(operator)?.stops || []).map(stop => ({ ...stop, operator })));
  const term = $("stop-search").value.trim();
  list.sort((a, b) => Number(b.name === term) - Number(a.name === term) || (distanceFromSapporo(a) ?? Infinity) - (distanceFromSapporo(b) ?? Infinity) || a.name.localeCompare(b.name, "ja") || operators.indexOf(a.operator) - operators.indexOf(b.operator));
  clear($("search-results"));
  const done = results.size === choices.length;
  const failed = [...results.values()].filter(value => value === null).length;
  if (!list.length) { setStatus("search-status", done ? (failed === choices.length ? "検索できませんでした。接続を確認して、もう一度お試しください。" : "見つかりませんでした。別の名前を試してください。") : "バス停を探しています…", done && failed === choices.length); return; }
  setStatus("search-status", !done ? `${list.length}件を表示中。ほかのバス会社も検索しています…` : failed ? "一部のバス会社を検索できませんでした。" : `${list.length}件の乗り場が見つかりました。`);
  const fragment = document.createDocumentFragment();
  for (const stop of list) {
    const position = stop.boarding_position ? `${stop.boarding_position}番のりば` : "乗り場番号なし";
    const location = locationLabel(stop) ? ` · ${locationLabel(stop)}` : "";
    fragment.append(resultButton(stop.name, `${names[stop.operator]} · ${stop.operator === "jr" ? "路線を選択" : position}${location}`, () => selectStop(stop)));
  }
  $("search-results").append(fragment);
}

async function selectStop(stop, chosenDate = tokyoNow().date) {
  clearTimeout(searchTimer); ++state.searchSerial; state.stop = stop; state.pattern = null; state.routeFilter = null; state.date = chosenDate;
  BUSSAPMap.focus(stop);
  if (stop.operator === "jr") { await loadPatterns(); return; }
  setPanel("departure-panel"); await loadDepartures();
}
async function loadPatterns() {
  setPanel("pattern-panel"); $("pattern-title").textContent = state.stop.name;
  clear($("pattern-results")); setStatus("pattern-status", "路線を読み込んでいます…");
  const stop = state.stop;
  try {
    const data = await get("/api/jr-patterns", { stop: stop.id.split(":")[1], limit: "50" });
    if (state.stop !== stop) return;
    const patterns = stop.boarding_position ? data.patterns.filter(pattern => String(pattern.boarding_position) === String(stop.boarding_position)) : data.patterns;
    setStatus("pattern-status", patterns.length ? (data.total_patterns > data.patterns.length ? `最初の${data.patterns.length}路線を表示しています。` : "") : stop.boarding_position ? "この乗り場の路線が見つかりませんでした。地図で別の乗り場を選んでください。" : "このバス停の路線が見つかりませんでした。");
    for (const pattern of patterns) {
      const position = pattern.boarding_position ? `${pattern.boarding_position}番のりば` : "乗り場番号なし";
      $("pattern-results").append(resultButton(pattern.route || "路線名なし", `${pattern.direction || "行先不明"} · ${position}`, () => { state.pattern = pattern; setPanel("departure-panel"); loadDepartures(); }));
    }
  } catch { setStatus("pattern-status", "路線を読み込めませんでした。もう一度お試しください。", true); }
}

function updateDateButtons() {
  const today = tokyoNow().date, tomorrow = nextDay(today);
  $("today-button").textContent = `今日 ${dateLabel(today)}`;
  $("tomorrow-button").textContent = `明日 ${dateLabel(tomorrow)}`;
  $("today-button").classList.toggle("active", state.date === today);
  $("tomorrow-button").classList.toggle("active", state.date === tomorrow);
  $("date-label").textContent = `${state.date} · 札幌時間`;
  $("date-input").value = state.date;
}
async function loadDepartures() {
  if (!state.stop || state.stop.operator === "jr" && !state.pattern) return;
  const serial = ++state.loadSerial, stop = state.stop;
  setPanel("departure-panel"); updateDateButtons();
  const position = stop.operator === "jr" ? state.pattern.boarding_position : stop.boarding_position;
  $("selected-stop").textContent = `${stop.name}${position ? ` · ${position}番のりば` : ""}`;
  $("selected-detail").textContent = `${names[stop.operator]}${state.pattern ? ` · ${state.pattern.route} · ${state.pattern.direction || "行先不明"}` : ""}${locationLabel(stop) ? ` · ${locationLabel(stop)}` : ""}`;
  updateFavoriteButton();
  $("route-filter-bar").hidden = !state.routeFilter;
  $("route-filter-label").textContent = state.routeFilter ? `${state.routeFilter}のみ表示中` : "";
  clear($("departure-results")); clear($("source-note")); setStatus("departure-status", "時刻を読み込んでいます…");
  const now = tokyoNow();
  const sourceStopId = stop.operator === "jr" ? String(stop.station_id || stop.id.split(":")[1]) : stop.id.split(":").slice(1).join(":");
  const params = { operator: stop.operator, stop: sourceStopId, date: state.date, after: state.date === now.date ? now.time : "00:00", limit: "50" };
  if (state.pattern) params.pattern = state.pattern.pattern;
  if (state.routeFilter) params.route = state.routeFilter;
  try {
    const data = await get("/api/departures", params);
    if (serial !== state.loadSerial) return;
    if (data.status === "outside_feed_coverage") { setStatus("departure-status", `この日付の時刻表はありません。掲載期間: ${data.coverage.from}〜${data.coverage.through}`); return; }
    if (data.status === "source_revision_changed_review_required") { setStatus("departure-status", "JRの時刻表が更新されました。確認が終わるまで時刻を表示できません。", true); return; }
    const departures = data.offline_cached_at
      ? data.departures.filter(departure => serviceMinutes(departure.scheduled_time) >= serviceMinutes(params.after))
      : data.departures;
    const offlineNotice = data.offline_cached_at
      ? `オフライン: ${new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(data.offline_cached_at))}に取得した時刻表です。前回表示した範囲のみ表示します。`
      : "";
    let emptyMessage = data.offline_cached_at
      ? "保存済みの範囲に、この時間以降の便はありません。接続時に更新してください。"
      : state.routeFilter
      ? `${state.routeFilter}は、この時間以降の便がありません。明日の時刻も確認できます。`
      : "この乗り場では、この時間以降の便はありません。明日の時刻を見るか、別の乗り場を選んでください。";
    if (!departures.length && !data.offline_cached_at && state.date === now.date && stop.operator !== "jr") {
      try {
        const fullDay = await get("/api/departures", { ...params, after: "00:00" });
        if (serial !== state.loadSerial) return;
        if (fullDay.departures.length > 0 && fullDay.departures.length < 50) {
          emptyMessage = `この乗り場の今日の最終バスは${displayTime(fullDay.departures.at(-1).scheduled_time)}でした。明日の時刻も確認できます。`;
        }
      } catch { /* Keep the useful empty-state message if the second lookup fails. */ }
    }
    const sourceNotice = stop.operator === "jr" ? jrNotice(data) : data.warning;
    setStatus("departure-status", [sourceNotice, offlineNotice, departures.length ? "" : emptyMessage].filter(Boolean).join(" · "), Boolean(data.warning && stop.operator !== "jr"));
    for (const departure of departures) {
      const row = make(stop.operator === "jr" ? "div" : "button", "departure-row");
      if (stop.operator !== "jr") row.type = "button";
      const main = make("div", "departure-main"), line = make("div", "departure-line");
      const routeName = departure.route || "路線名なし";
      const shortRoute = routeLabel(routeName);
      const route = make("span", "route", shortRoute);
      route.title = routeName;
      const fullDestination = departure.destination || "行先不明";
      const destination = make("span", "destination", stop.operator === "jr" ? fullDestination.split("→").at(-1) : fullDestination);
      destination.title = fullDestination;
      line.append(route, destination);
      main.append(line, make("span", "scheduled", "予定時刻"));
      row.append(make("time", "departure-time", displayTime(departure.scheduled_time)), main);
      if (stop.operator !== "jr") {
        row.setAttribute("aria-label", `${displayTime(departure.scheduled_time)} ${shortRoute} ${fullDestination}。${state.routeFilter === shortRoute ? "すべての路線を表示" : `${shortRoute}のみ表示`}`);
        row.addEventListener("click", () => { state.routeFilter = state.routeFilter === shortRoute ? null : shortRoute; loadDepartures(); });
      }
      $("departure-results").append(row);
    }
    const note = $("source-note");
    note.append(make("span", "", `出典: ${names[stop.operator]}時刻表`));
    const url = stop.operator === "jr" ? "https://www.jrhokkaidobus.com/timetable/routebus_sapporo/" : data.source;
    if (url) { const link = make("a", "", "公式・データ元を確認 ↗"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; note.append(document.createTextNode(" · "), link); }
    const fetchedAt = data.feed_fetched_at || data.source_fetched_at;
    if (fetchedAt) note.append(make("span", "", ` · 取得 ${new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(fetchedAt))}`));
  } catch (error) {
    if (serial === state.loadSerial) {
      const stale = /unknown (chuo|jotetsu) stop ID|JR pattern is not listed at this stop/.test(error.message);
      const uncached = error.message.includes("この日付の保存済み時刻表がありません");
      setStatus("departure-status", stale ? "この乗り場・路線は現在のデータにありません。地図から選び直してください。" : uncached ? error.message : "時刻を読み込めませんでした。更新を押して、もう一度お試しください。", true);
    }
  }
}

function resetSearch() { ++state.loadSerial; ++state.searchSerial; state.stop = null; state.pattern = null; state.routeFilter = null; $("stop-search").value = ""; setPanel("map-panel"); }
$("stop-search").addEventListener("input", queueSearch);
document.querySelectorAll("[data-operator]").forEach(button => button.addEventListener("click", () => {
  state.operator = button.dataset.operator;
  document.querySelectorAll("[data-operator]").forEach(tab => { const selected = tab === button; tab.classList.toggle("active", selected); tab.setAttribute("aria-pressed", selected); });
  BUSSAPMap.setOperator(state.operator);
  if ($("stop-search").value.trim()) queueSearch();
}));
$("change-stop").addEventListener("click", resetSearch);
$("pattern-back").addEventListener("click", resetSearch);
$("today-button").addEventListener("click", () => { state.date = tokyoNow().date; loadDepartures(); });
$("tomorrow-button").addEventListener("click", () => { state.date = nextDay(tokyoNow().date); loadDepartures(); });
$("date-input").addEventListener("change", event => { if (event.target.value) { state.date = event.target.value; loadDepartures(); } });
$("calendar-button").addEventListener("click", () => { const input = $("date-input"); input.showPicker?.(); });
$("refresh-button").addEventListener("click", loadDepartures);
$("clear-route-filter").addEventListener("click", () => { state.routeFilter = null; loadDepartures(); });
$("favorite-button").addEventListener("click", toggleFavorite);
window.addEventListener("storage", event => { if (event.key === FAVORITES_KEY) { favorites = readFavorites(); renderFavorites(); } });
BUSSAPMap.init(selectStop);
renderFavorites();
const networkMapLink = $("network-map-link");
if (networkMapLink && (window.matchMedia("(display-mode: standalone)").matches || navigator.standalone === true)) {
  networkMapLink.removeAttribute("target");
  networkMapLink.removeAttribute("rel");
  networkMapLink.textContent = "参考路線図 (2016年・PDF) ›";
}
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
