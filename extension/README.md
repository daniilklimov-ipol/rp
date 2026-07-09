# YouTube Watch-Completion Predictor — Browser Extension

A Manifest V3 extension for Chrome/Edge that overlays a predicted
watch-completion percentage on every YouTube video thumbnail (home page,
search results, sidebar recommendations), using predictions from the
[companion desktop app](../desktop). It also reports your actual watch
progress back to that app, which is what trains the model in the first
place.

## What it looks like

- A small **badge** in the top-right corner of each thumbnail showing the
  predicted `%`.
- A **border** around the thumbnail whose color smoothly interpolates from
  **red** (0% — low predicted completion) to **green** (100% — high
  predicted completion), via `hsl(percent/100 * 120°, ...)`.
- Both update automatically as you scroll and YouTube lazy-loads more
  thumbnails (an `IntersectionObserver` + `MutationObserver` combo re-scans
  the page and only fetches predictions for thumbnails actually on screen).

## Install (unpacked, for development)

1. Make sure the [desktop app](../desktop) is running (`python main.py`) —
   it must be up for predictions to appear.
2. Open `chrome://extensions` (or `edge://extensions`).
3. Enable **Developer mode**.
4. Click **Load unpacked** and select this `extension/` folder.
5. Open youtube.com — badges/borders should appear on thumbnails within a
   second or two of scrolling them into view.
6. Click the extension icon to open the popup: set the desktop app's port
   (default `8765`), toggle overlays on/off, and check the connection status.

## How it talks to the desktop app

- `content.js` runs on every `youtube.com` page. It never calls `fetch()`
  directly — it messages `background.js` (the MV3 service worker), which is
  the only place that talks HTTP to `http://127.0.0.1:<port>`. This lets
  multiple open YouTube tabs share one small prediction cache (10 min TTL)
  instead of hammering the server.
- **Thumbnails** (`POST /predict`): batches of up to 50 video IDs, only for
  thumbnails that have scrolled into view, debounced by 400ms.
- **Watch page** (`POST /watch`): while a `/watch` page is open, the content
  script listens to the `<video>` element's `timeupdate` event and tracks
  the furthest playback position reached. It reports this every 15s and
  again when you navigate away or the tab is hidden.

## Permissions

- `storage` — remembers the configured port and the overlays on/off toggle.
- `host_permissions` for `localhost`/`127.0.0.1` (any port) — talk to the
  desktop app. No permission is requested for youtube.com's own network
  traffic; the content script only reads the DOM there.

## Files

```
manifest.json     # MV3 manifest
background.js     # service worker: fetch() to the desktop app + caching
content.js        # thumbnail scanning/painting + watch-page progress tracking
overlay.css        # badge + border styles
popup.html/js       # port config, overlay on/off toggle, connection test
```

## Known limitations

- Shorts (`ytd-reel-item-renderer`) aren't overlaid yet — their thumbnail
  markup differs from regular video renderers. Extending `RENDERER_SELECTOR`
  and `extractVideoId()` in `content.js` to handle `/shorts/<id>` links is
  the way to add it.
- If the desktop app isn't running, badges show `?` (no API key configured)
  or `err` (server unreachable) instead of a percentage.
