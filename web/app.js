const $ = (id) => document.getElementById(id);
const names = { chuo: "北海道中央バス", jr: "JR北海道バス", jotetsu: "じょうてつ" };
const operators = ["chuo", "jr", "jotetsu"];
const state = { operator: "all", stop: null, pattern: null, date: null, searchSerial: 0, loadSerial: 0 };
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
function setPanel(panel) { for (const id of ["map-panel", "search-panel", "pattern-panel", "departure-panel"]) $(id).hidden = id !== panel; if (panel === "map-panel") BUSSAPMap.show(); }
function setStatus(id, message, error = false) { const el = $(id); el.hidden = !message; el.textContent = message || ""; el.classList.toggle("error", error); }
function clear(el) { el.replaceChildren(); }
function make(tag, className, value) { const el = document.createElement(tag); if (className) el.className = className; if (value != null) el.textContent = value; return el; }
function displayTime(value) { const [hour, minute] = value.split(":"); return `${String(Number(hour) % 24).padStart(2, "0")}:${minute}`; }
async function get(path, params) { const response = await fetch(`${path}?${new URLSearchParams(params)}`, { cache: "no-store" }); const body = await response.json(); if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`); return body; }

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
  state.stop = null; state.pattern = null; setPanel(term ? "search-panel" : "map-panel"); clear($("search-results"));
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
  clearTimeout(searchTimer); ++state.searchSerial; state.stop = stop; state.pattern = null; state.date = chosenDate;
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
  clear($("departure-results")); clear($("source-note")); setStatus("departure-status", "時刻を読み込んでいます…");
  const now = tokyoNow();
  const sourceStopId = stop.operator === "jr" ? String(stop.station_id || stop.id.split(":")[1]) : stop.id.split(":").slice(1).join(":");
  const params = { operator: stop.operator, stop: sourceStopId, date: state.date, after: state.date === now.date ? now.time : "00:00", limit: "50" };
  if (state.pattern) params.pattern = state.pattern.pattern;
  try {
    const data = await get("/api/departures", params);
    if (serial !== state.loadSerial) return;
    if (data.status === "outside_feed_coverage") { setStatus("departure-status", `この日付の時刻表はありません。掲載期間: ${data.coverage.from}〜${data.coverage.through}`); return; }
    if (data.status === "source_revision_changed_review_required") { setStatus("departure-status", "JRの時刻表が更新されました。確認が終わるまで時刻を表示できません。", true); return; }
    let emptyMessage = "この乗り場では、この時間以降の便はありません。明日の時刻を見るか、別の乗り場を選んでください。";
    if (!data.departures.length && state.date === now.date && stop.operator !== "jr") {
      try {
        const fullDay = await get("/api/departures", { ...params, after: "00:00" });
        if (serial !== state.loadSerial) return;
        if (fullDay.departures.length > 0 && fullDay.departures.length < 50) {
          emptyMessage = `この乗り場の今日の最終バスは${displayTime(fullDay.departures.at(-1).scheduled_time)}でした。明日の時刻も確認できます。`;
        }
      } catch { /* Keep the useful empty-state message if the second lookup fails. */ }
    }
    setStatus("departure-status", data.warning || (data.departures.length ? "" : emptyMessage), Boolean(data.warning));
    for (const departure of data.departures) {
      const row = make("div", "departure-row");
      const main = make("div", "departure-main"), line = make("div", "departure-line");
      const routeName = departure.route || "路線名なし";
      const code = routeName.match(/\[([^\]]+)\]/)?.[1];
      const shortRoute = code || routeName.split(/[・･]/)[0];
      const route = make("span", "route", shortRoute.length <= 8 ? shortRoute : routeName);
      route.title = routeName;
      const fullDestination = departure.destination || "行先不明";
      const destination = make("span", "destination", stop.operator === "jr" ? fullDestination.split("→").at(-1) : fullDestination);
      destination.title = fullDestination;
      line.append(route, destination);
      main.append(line, make("span", "scheduled", "予定時刻"));
      row.append(make("time", "departure-time", displayTime(departure.scheduled_time)), main);
      $("departure-results").append(row);
    }
    const note = $("source-note");
    note.append(make("span", "", `出典: ${names[stop.operator]}時刻表`));
    const url = stop.operator === "jr" ? "https://www.jrhokkaidobus.com/timetable/routebus_sapporo/" : data.source;
    if (url) { const link = make("a", "", "公式・データ元を確認 ↗"); link.href = url; link.target = "_blank"; link.rel = "noopener noreferrer"; note.append(document.createTextNode(" · "), link); }
    if (data.feed_fetched_at) note.append(make("span", "", ` · 取得 ${new Intl.DateTimeFormat("ja-JP", { timeZone: "Asia/Tokyo", month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" }).format(new Date(data.feed_fetched_at))}`));
  } catch { if (serial === state.loadSerial) setStatus("departure-status", "時刻を読み込めませんでした。更新を押して、もう一度お試しください。", true); }
}

function resetSearch() { ++state.loadSerial; ++state.searchSerial; state.stop = null; state.pattern = null; $("stop-search").value = ""; setPanel("map-panel"); }
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
BUSSAPMap.init(selectStop);
