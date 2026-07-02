# Static Files

All static assets live in [static/](../static/) and are served by WhiteNoise in production (see
[API_AND_SERVICES.md](API_AND_SERVICES.md)). Referenced from [templates/base.html](../templates/base.html)
unless noted.

```
static/
├── css/style.css        # Site-wide stylesheet (1186 lines, 31 sections)
├── js/main.js            # Site-wide JS (nav, AJAX toggles, PWA install, dark mode)
├── js/sw.js               # PWA service worker
├── manifest.json          # PWA manifest
├── images/                # favicon, PWA icons (180/192/512), OG image
└── img/                   # SVG logos (mark, white, color)
```

## static/css/style.css (1186 lines, 31 numbered sections)

| # | Section | Notes |
|---|---|---|
| 1 | Tokens | CSS custom properties (colors, spacing, radii) |
| 2 | Reset & Base | |
| 3 | Navbar | |
| 4 | Buttons | |
| 5 | Cards | |
| 6 | Badges | |
| 7 | Forms | |
| 8 | Section Headers | |
| 9 | Page Hero | |
| 10 | Hero Landing | |
| 11 | Alerts / Flash Messages | |
| 12 | Footer | |
| 13 | Mobile Bottom Nav | used by all pages via base.html |
| 14 | Skeleton Loaders | |
| 15 | Page Transition Loader | |
| 16 | Empty States | |
| 17 | Animations | |
| 18 | Btn Loading State | |
| 19 | Auth Pages | login/register/password-reset split-panel layout |
| 20 | Trust Badge | |
| 21 | Feature Tile | |
| 22 | PWA Install Banner | |
| 23 | Responsive | breakpoints |
| 24 | **Dark Mode** (lines 946–1082) | `body.dark <selector>` — the standardized site-wide dark-mode pattern |
| 25 | Dark Mode Toggle | |
| 26 | Print | |
| 27 | Hover Scale Utility + Font-Weight Utilities | |
| 28 | HTMX Loading Indicator | |
| 29 | Lazy Image blur-up reveal | |
| 30 | Card Performance Utilities | |
| 31 | Pagination | pairs with `templates/partials/pagination.html` |

**Flagged inconsistency**: dark mode is standardized on `body.dark <selector>` everywhere except
[templates/mentorship/directory.html](../templates/mentorship/directory.html), which instead uses
`[data-bs-theme="dark"] <selector>` — this means the mentor directory likely does not respond
correctly to the site's dark-mode toggle. See [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md).

## static/js/main.js (259 lines)

Loaded on every page via base.html.

- `getCsrf()` — top-level helper reading the `csrftoken` cookie, used by all same-page AJAX POSTs
  (save-course, save-career, shortlist toggles, etc.).
- `DOMContentLoaded` handler:
  - Auto-dismisses flash messages after a timeout.
  - Highlights the active nav link in both `.site-navbar` (desktop) and `.mobile-bottom-nav`.
  - Wires AJAX toggles for `[data-save-course]` / `[data-save-career]` attributes (posts to
    `accounts:toggle_save_course` / `accounts:toggle_save_career`).
  - Initializes Bootstrap tooltips.
  - `IntersectionObserver`-based scroll-reveal for `.card` elements.
  - Animated `[data-count]` stat counters (cubic-ease `requestAnimationFrame` loop) used on
    homepage/dashboard stat rows.
- Standalone IIFE for **Web Push subscription**: `doSubscribe()` + `urlB64ToUint8Array()` — reads the
  VAPID public key from a `#vapid-public-key` meta tag, requests permission after a 12s delay, POSTs
  the subscription to `accounts:push_subscribe`.
- Standalone IIFE for **PWA install prompt**: `dismiss()` (escalating cooldown 7 days → 4 days via
  `localStorage`), `trackInstall(platform)` (posts to `analytics:pwa_install`), listens for
  `beforeinstallprompt` / `appinstalled`; detects iOS Safari (which never fires
  `beforeinstallprompt`) and shows a manual-install-instructions modal instead.

## static/js/sw.js (84 lines) — PWA service worker

- `CACHE = 'careernext-v7'`; `OFFLINE_URL = '/offline/'` (→ `templates/offline.html`).
- `install`: caches the offline page with `cache:'reload'` (bypasses HTTP cache), calls
  `self.skipWaiting()`.
- `activate`: deletes any cache not matching the current `CACHE` name, calls `clients.claim()`.
- `push`: renders a notification from the push payload JSON (title/body/url), falls back to
  defaults on parse failure; vibration pattern `[200,100,200]`. Paired with server-side push sending
  via `pywebpush` (see [API_AND_SERVICES.md](API_AND_SERVICES.md)) and the `PushSubscription` model.
- `notificationclick`: closes the notification, focuses an existing matching-URL client window or
  opens a new one.
- `fetch` strategy:
  - `/static/` assets → cache-first with background revalidation.
  - Page navigations → network-only with one retry, falling back to the cached offline page.
  - Everything else → straight to network; returns an empty `503` on failure.

Registered from `templates/base.html` on every page load.

## static/manifest.json (40 lines)

- `name` / `short_name`: CareerNext branding.
- `start_url: /dashboard/`, `display: standalone`, `orientation: any`.
- `background_color` / `theme_color` set.
- Icons: 192px and 512px (from `static/images/`).
- `shortcuts`: quick-launch entries for **Calculator** and **Career Quiz** (long-press home-screen
  icon).
- `categories` and `lang` fields set.

## static/images/ and static/img/

- `images/` — favicon, PWA install icons (180/192/512px), Open Graph share image.
- `img/` — SVG logo variants (mark-only, white, full color) used across navbar/footer/emails.

## Which pages use what

| Asset | Used by |
|---|---|
| `style.css`, `main.js`, `manifest.json`, `sw.js` | Every page (via base.html) |
| Chart.js (CDN, unversioned) | `clusterpoints/calculator.html` (cutoff trend) |
| Chart.js 4.4.0 (CDN) | `courses/course_detail.html` (degree cutoff trend line chart) |
| `analytics/base_analytics.html` embedded design-system CSS | All 13 staff analytics dashboard templates |
| VAPID push (`#vapid-public-key` meta + main.js IIFE) | Any page where the user is logged in (subscription prompt fires 12s after load) |
