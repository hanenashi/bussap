/* BUSSAP offline shell and previously viewed full timetables. No map tiles or PDF. */
const SHELL_CACHE = "bussap-shell-v1";
const TIMETABLE_CACHE = "bussap-timetables-v1";
const SHELL_ASSETS = [
  "/", "/styles.css", "/map.css", "/app.js", "/map.js",
  "/vendor/leaflet.js", "/vendor/leaflet.css", "/manifest.webmanifest",
  "/icons/icon-192.png", "/icons/icon-512.png",
];
const SHELL_PATHS = new Set(SHELL_ASSETS);
const MAX_TIMETABLES = 30;

self.addEventListener("install", event => {
  event.waitUntil((async () => {
    const cache = await caches.open(SHELL_CACHE);
    await cache.addAll(SHELL_ASSETS);
    await self.skipWaiting();
  })());
});

self.addEventListener("activate", event => {
  event.waitUntil((async () => {
    for (const name of await caches.keys()) {
      if (name.startsWith("bussap-") && name !== SHELL_CACHE && name !== TIMETABLE_CACHE) await caches.delete(name);
    }
    await self.clients.claim();
  })());
});

async function fetchWithin(request, milliseconds) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), milliseconds);
  try { return await fetch(request, { signal: controller.signal }); }
  finally { clearTimeout(timer); }
}

async function shellResponse(request) {
  const cache = await caches.open(SHELL_CACHE);
  const url = new URL(request.url);
  const key = new Request(`${url.origin}${url.pathname}`);
  try {
    const response = await fetchWithin(request, 5000);
    if (response.ok) {
      try { await cache.put(key, response.clone()); } catch { /* App still works online if storage is full. */ }
    }
    if (response.ok || response.status < 500) return response;
    return await cache.match(key) || response;
  } catch {
    return await cache.match(key) || Response.error();
  }
}

function timetableKey(request) {
  const url = new URL(request.url);
  url.searchParams.delete("after");
  url.searchParams.sort();
  return new Request(url.href);
}

async function saveTimetable(cache, key, data) {
  const record = { cached_at: new Date().toISOString(), data };
  await cache.delete(key);
  await cache.put(key, new Response(JSON.stringify(record), { headers: { "Content-Type": "application/json" } }));
  const keys = await cache.keys();
  for (const old of keys.slice(0, Math.max(0, keys.length - MAX_TIMETABLES))) await cache.delete(old);
}

async function clearJrTimetables(cache) {
  for (const key of await cache.keys()) {
    if (new URL(key.url).searchParams.get("operator") === "jr") await cache.delete(key);
  }
}

async function timetableResponse(request) {
  const cache = await caches.open(TIMETABLE_CACHE);
  const key = timetableKey(request);
  let response = null;
  try {
    response = await fetchWithin(request, 6000);
    if (response.ok) {
      const data = await response.clone().json();
      if (data.status === "scheduled_gtfs" || data.status === "day_category_candidate_unverified_for_date") {
        try { await saveTimetable(cache, key, data); } catch { /* Keep the live response. */ }
      } else if (data.status === "source_revision_changed_review_required") {
        try { await clearJrTimetables(cache); } catch { /* Never replace a live revision warning with old data. */ }
      } else {
        try { await cache.delete(key); } catch { /* Keep the live response. */ }
      }
      return response;
    }
    if (response.status < 500) return response;
  } catch { /* Fall through to a previously viewed timetable. */ }
  try {
    const saved = await cache.match(key);
    if (saved) {
      const record = await saved.json();
      return new Response(JSON.stringify({ ...record.data, offline_cached_at: record.cached_at }), {
        status: 200, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
      });
    }
  } catch { /* No usable saved data. */ }
  return response || new Response(JSON.stringify({ error: "この日付の保存済み時刻表がありません。接続時に一度開いてください。" }), {
    status: 503, headers: { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" },
  });
}

self.addEventListener("fetch", event => {
  const request = event.request;
  if (request.method !== "GET") return;
  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname === "/api/departures" && url.searchParams.get("limit") === "50") {
    event.respondWith(timetableResponse(request));
  } else if (SHELL_PATHS.has(url.pathname)) {
    event.respondWith(shellResponse(request));
  }
});
