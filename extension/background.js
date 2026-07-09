/**
 * Service worker: the only place that talks HTTP to the local desktop app.
 * Content scripts message this worker instead of calling fetch() directly so
 * requests from every open YouTube tab share one small in-memory cache and
 * one place to read the configured port.
 */

const DEFAULT_PORT = 8765;
const CACHE_TTL_MS = 10 * 60 * 1000; // 10 minutes
const PREDICT_BATCH_LIMIT = 50;

/** @type {Map<string, {data: object, ts: number}>} */
const predictionCache = new Map();

async function getPort() {
  const { serverPort } = await chrome.storage.local.get("serverPort");
  return serverPort || DEFAULT_PORT;
}

async function baseUrl() {
  const port = await getPort();
  return `http://127.0.0.1:${port}`;
}

async function callServer(path, options, timeoutMs = 4000) {
  const url = `${await baseUrl()}${path}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const resp = await fetch(url, { ...options, signal: controller.signal });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    return await resp.json();
  } finally {
    clearTimeout(timer);
  }
}

function cacheGet(videoId) {
  const hit = predictionCache.get(videoId);
  if (!hit) return null;
  if (Date.now() - hit.ts > CACHE_TTL_MS) {
    predictionCache.delete(videoId);
    return null;
  }
  return hit.data;
}

async function predict(videoIds) {
  const uniqueIds = [...new Set(videoIds)].filter(Boolean);
  const results = {};
  const toFetch = [];

  for (const id of uniqueIds) {
    const cached = cacheGet(id);
    if (cached) results[id] = cached;
    else toFetch.push(id);
  }

  for (let i = 0; i < toFetch.length; i += PREDICT_BATCH_LIMIT) {
    const chunk = toFetch.slice(i, i + PREDICT_BATCH_LIMIT);
    try {
      const json = await callServer("/predict", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ video_ids: chunk }),
      });
      for (const pred of json.predictions || []) {
        predictionCache.set(pred.video_id, { data: pred, ts: Date.now() });
        results[pred.video_id] = pred;
      }
    } catch (err) {
      for (const id of chunk) {
        results[id] = { video_id: id, error: String(err) };
      }
    }
  }

  return results;
}

async function reportWatch(payload) {
  return callServer("/watch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

async function health() {
  try {
    return await callServer("/health", { method: "GET" }, 2000);
  } catch (err) {
    return { status: "unreachable", error: String(err) };
  }
}

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (!message || !message.type) return false;

  if (message.type === "PREDICT") {
    predict(message.videoIds || []).then(sendResponse);
    return true; // async response
  }
  if (message.type === "WATCH") {
    reportWatch(message.payload).then(sendResponse).catch((err) => sendResponse({ error: String(err) }));
    return true;
  }
  if (message.type === "HEALTH") {
    health().then(sendResponse);
    return true;
  }
  return false;
});
