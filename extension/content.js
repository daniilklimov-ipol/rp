/**
 * Runs on youtube.com. Two independent jobs:
 *
 *  1. Thumbnail overlay: find every video thumbnail on the page (home,
 *     search, sidebar recommendations), ask the background worker for a
 *     watch-completion prediction, and paint a %-badge + a green->red
 *     border on top of it. Re-scans as YouTube lazy-loads more thumbnails
 *     while the user scrolls, and only fetches predictions for thumbnails
 *     that have actually scrolled into view (keeps API/server load down).
 *
 *  2. Watch tracker: on a /watch page, observes the <video> element and
 *     reports the furthest playback position reached back to the desktop
 *     app, which is the *real* ground-truth training signal for the model.
 */

(() => {
  const RENDERER_SELECTOR = [
    "ytd-rich-item-renderer",
    "ytd-video-renderer",
    "ytd-compact-video-renderer",
    "ytd-grid-video-renderer",
    "ytd-playlist-video-renderer",
  ].join(", ");

  const FETCH_DEBOUNCE_MS = 400;
  const WATCH_REPORT_INTERVAL_MS = 15000;

  let overlaysEnabled = true;

  chrome.storage.local.get("overlaysEnabled", (res) => {
    overlaysEnabled = res.overlaysEnabled !== false;
  });
  chrome.storage.onChanged.addListener((changes) => {
    if (changes.overlaysEnabled) {
      overlaysEnabled = changes.overlaysEnabled.newValue !== false;
      if (!overlaysEnabled) clearAllOverlays();
      else rescan();
    }
  });

  // ---- color helpers -----------------------------------------------------
  function colorForPercent(percent) {
    const clamped = Math.max(0, Math.min(100, percent));
    const hue = (clamped / 100) * 120; // 0 = red, 120 = green
    return `hsl(${hue.toFixed(0)}, 82%, 45%)`;
  }

  // ---- thumbnail registry -------------------------------------------------
  /** @type {Map<string, Set<HTMLElement>>} videoId -> anchor elements showing it */
  const registry = new Map();
  const pendingIds = new Set();
  let debounceTimer = null;

  function extractVideoId(renderer) {
    const link = renderer.querySelector('a#thumbnail[href*="/watch?v="], a#video-title[href*="/watch?v="]');
    if (!link) return null;
    try {
      const url = new URL(link.getAttribute("href"), location.href);
      return url.searchParams.get("v");
    } catch {
      return null;
    }
  }

  function paint(anchor, prediction) {
    anchor.classList.add("ytwp-anchor");

    let border = anchor.querySelector(":scope > .ytwp-border");
    let badge = anchor.querySelector(":scope > .ytwp-badge");
    if (!border) {
      border = document.createElement("div");
      border.className = "ytwp-border";
      anchor.appendChild(border);
    }
    if (!badge) {
      badge = document.createElement("div");
      badge.className = "ytwp-badge";
      anchor.appendChild(badge);
    }

    if (prediction.error) {
      badge.textContent = prediction.error === "no_api_key" ? "?" : "err";
      badge.classList.add("ytwp-badge--error");
      badge.classList.remove("ytwp-badge--pending");
      anchor.style.removeProperty("--ytwp-color");
      border.style.setProperty("--ytwp-color", "#555");
      badge.style.setProperty("--ytwp-color", "#3a3a3a");
      return;
    }

    const color = colorForPercent(prediction.percent);
    badge.textContent = `${Math.round(prediction.percent)}%`;
    badge.classList.remove("ytwp-badge--pending", "ytwp-badge--error");
    border.style.setProperty("--ytwp-color", color);
    badge.style.setProperty("--ytwp-color", color);
  }

  function paintPending(anchor) {
    anchor.classList.add("ytwp-anchor");
    let badge = anchor.querySelector(":scope > .ytwp-badge");
    if (!badge) {
      badge = document.createElement("div");
      badge.className = "ytwp-badge";
      anchor.appendChild(badge);
    }
    if (!badge.textContent) {
      badge.textContent = "…";
      badge.classList.add("ytwp-badge--pending");
    }
  }

  function clearAllOverlays() {
    document.querySelectorAll(".ytwp-border, .ytwp-badge").forEach((el) => el.remove());
    document.querySelectorAll(".ytwp-anchor").forEach((el) => el.classList.remove("ytwp-anchor"));
  }

  function scheduleFetch() {
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(flushFetch, FETCH_DEBOUNCE_MS);
  }

  function flushFetch() {
    debounceTimer = null;
    if (pendingIds.size === 0) return;
    const ids = [...pendingIds];
    pendingIds.clear();

    for (const id of ids) {
      for (const anchor of registry.get(id) || []) paintPending(anchor);
    }

    chrome.runtime.sendMessage({ type: "PREDICT", videoIds: ids }, (results) => {
      if (chrome.runtime.lastError || !results) return;
      for (const [id, prediction] of Object.entries(results)) {
        for (const anchor of registry.get(id) || []) {
          if (anchor.isConnected) paint(anchor, prediction);
        }
      }
    });
  }

  // ---- visibility-driven scanning -----------------------------------------
  const intersectionObserver = new IntersectionObserver(
    (entries) => {
      if (!overlaysEnabled) return;
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const videoId = entry.target.dataset.ytwpVideoId;
        if (videoId) {
          pendingIds.add(videoId);
          scheduleFetch();
        }
      }
    },
    { root: null, rootMargin: "400px", threshold: 0.01 }
  );

  function registerRenderer(renderer) {
    if (renderer.dataset.ytwpProcessed) return;
    renderer.dataset.ytwpProcessed = "1";

    const videoId = extractVideoId(renderer);
    if (!videoId) return;

    const anchor = renderer.querySelector("ytd-thumbnail") || renderer;
    anchor.dataset.ytwpVideoId = videoId;

    if (!registry.has(videoId)) registry.set(videoId, new Set());
    registry.get(videoId).add(anchor);

    intersectionObserver.observe(anchor);
  }

  function rescan(root = document) {
    root.querySelectorAll(RENDERER_SELECTOR).forEach(registerRenderer);
  }

  const mutationObserver = new MutationObserver((mutations) => {
    if (!overlaysEnabled) return;
    for (const mutation of mutations) {
      for (const node of mutation.addedNodes) {
        if (!(node instanceof HTMLElement)) continue;
        if (node.matches?.(RENDERER_SELECTOR)) registerRenderer(node);
        else node.querySelectorAll?.(RENDERER_SELECTOR).forEach(registerRenderer);
      }
    }
  });
  mutationObserver.observe(document.documentElement, { childList: true, subtree: true });

  // ---- watch-page progress tracking ---------------------------------------
  let watchState = null; // { videoId, video, maxSeconds, reportTimer }

  function currentVideoIdFromUrl() {
    if (location.pathname !== "/watch") return null;
    return new URLSearchParams(location.search).get("v");
  }

  function guessTitle() {
    const el = document.querySelector("h1.ytd-watch-metadata yt-formatted-string, h1.title yt-formatted-string");
    return el ? el.textContent.trim() : document.title.replace(/ - YouTube$/, "");
  }

  function guessChannel() {
    const link = document.querySelector("ytd-channel-name a");
    const title = link ? link.textContent.trim() : "";
    let channelId = "";
    if (link) {
      const href = link.getAttribute("href") || "";
      const match = href.match(/\/channel\/([^/?]+)/);
      channelId = match ? match[1] : href.replace(/^\//, "");
    }
    return { channelId, title };
  }

  function sendWatchReport() {
    if (!watchState || !watchState.video) return;
    const duration = watchState.video.duration;
    if (!duration || !isFinite(duration)) return;

    const payload = {
      video_id: watchState.videoId,
      watched_seconds: watchState.maxSeconds,
      duration_seconds: duration,
      title: guessTitle(),
      ...guessChannelFields(),
    };
    // sendBeacon can't reach an extension service worker; a best-effort
    // fire-and-forget runtime message is the closest equivalent here.
    chrome.runtime.sendMessage({ type: "WATCH", payload });
  }

  function guessChannelFields() {
    const { channelId, title } = guessChannel();
    return { channel_id: channelId, channel_title: title };
  }

  function teardownWatchTracking() {
    if (!watchState) return;
    sendWatchReport();
    if (watchState.reportTimer) clearInterval(watchState.reportTimer);
    if (watchState.video) watchState.video.removeEventListener("timeupdate", watchState.onTimeUpdate);
    watchState = null;
  }

  function setupWatchTracking() {
    const videoId = currentVideoIdFromUrl();
    if (!videoId) return;
    if (watchState && watchState.videoId === videoId) return;
    teardownWatchTracking();

    const tryAttach = () => {
      const video = document.querySelector("video.html5-main-video, video");
      if (!video) return false;

      const onTimeUpdate = () => {
        if (watchState) watchState.maxSeconds = Math.max(watchState.maxSeconds, video.currentTime);
      };
      video.addEventListener("timeupdate", onTimeUpdate);

      watchState = {
        videoId,
        video,
        maxSeconds: video.currentTime || 0,
        onTimeUpdate,
        reportTimer: setInterval(() => sendWatchReport(), WATCH_REPORT_INTERVAL_MS),
      };
      return true;
    };

    if (!tryAttach()) {
      const observer = new MutationObserver(() => {
        if (tryAttach()) observer.disconnect();
      });
      observer.observe(document.documentElement, { childList: true, subtree: true });
      setTimeout(() => observer.disconnect(), 15000);
    }
  }

  document.addEventListener("yt-navigate-finish", () => {
    setupWatchTracking();
    rescan();
  });
  window.addEventListener("pagehide", () => teardownWatchTracking());
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") sendWatchReport();
  });

  // ---- boot -----------------------------------------------------------
  rescan();
  setupWatchTracking();
})();
