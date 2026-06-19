# TODO — Prioritised Backlog

Format: `[ ]` not done | `[x]` done | `[~]` in progress | `[-]` dropped/deferred

Last updated: 2026-06-19

---

## P0 — Blockers (Fix Before Launch)

- [x] Configure email backend (SMTP / SendGrid) — Resend SMTP wired; keys via `RESEND_API_KEY` env var; falls back to console in dev
- [x] Remove the `is_verified = True` short-circuit in `accounts/views.py` RegisterView (bypasses email verification)
- [x] Send verification email — RegisterView now creates token and calls `send_mail()` with verify link
- [x] Add `STATICFILES_DIRS` — set to `[BASE_DIR / 'static']`; run `python manage.py collectstatic` before each production deploy
- [x] Set `ALLOWED_HOSTS` — configured for localhost + `.onrender.com` + `careernext.co.ke`; set `DJANGO_DEBUG=False` in production env
- [x] Rotate `SECRET_KEY` — now loaded from `SECRET_KEY` env var; raises `RuntimeError` if insecure default used in production
- [x] Remove hardcoded `OPENAI_API_KEY` placeholder from settings — already reads from `OPENAI_API_KEY` env var
- [ ] Session expiry graceful handling — if career engine session expires mid-flow user sees a blank results page; needs a redirect to re-enter grades with a friendly message
- [x] Set `MEDIA_ROOT` and `MEDIA_URL` in settings so uploaded logos/PDFs are served
- [x] Fix `TIME_ZONE` double-definition — consistently `Africa/Nairobi`
- [x] Fix Unicode en-dash garbled characters in cluster descriptions

---

## P0 — Career Engine Flow (Degree Path)

- [x] Subject requirements filtering — `_meets_subject_requirements()` checks `career_subject_grades` session key against `course.subject_requirements` JSONField
- [x] Grade-first flow — Degree now goes: Enter Grades → Choose Method → Results
- [x] `degree_options.html` — 4 method cards with spring animations, shimmer sweep, icon bounce
- [x] `career_subject_grades` session key saved at grade entry for all degree methods
- [x] Payment gate on career results — blurred preview cards, lock card, "Unlock My Results" CTA
- [x] Grade entry UI — unified light-theme accordion across all pathways: Core Subjects open, Sciences / Humanities / Technical / Languages collapsible; sticky counter + navy Continue button
- [x] `pathway_input.html` — KCSE accordions for Degree/Diploma/Certificate/KMTC; mean grade picker for TTC/Artisan; light theme
- [x] `loading.html` top-tier redesign — animated gradient, star particles, triple-ring SVG, glass-effect card, staggered step reveal
- [x] KMTC subject entry — now uses full KCSE subject accordion (same as Diploma/Certificate) instead of single mean-grade picker
- [x] OCR activation — `degree_upload` uses OpenAI GPT-4o vision; handles both KCSE grade slips and cluster points documents; robust subject alias matching; falls back to manual entry if no key
- [x] `degree_upload` redirect — cluster points docs → `loading_page` directly; KCSE slips → `degree_calculate` for review/correction
- [ ] `degree_manual` — limit cluster list to the ~20 clusters that have actual degree `CourseOffering` records (shows all 61 now)
- [ ] `degree_paste` — paste view + URL + template not yet built
- [x] **Document Scanner (OCR)** — supports JPG/PNG/PDF; dual-mode prompt detects KCSE grade slips vs KUCCPS cluster points docs; subject alias resolution; JSON extraction with code-fence stripping and regex fallback

---

## P1 — Core Features (MVP)

- [ ] Wire up real OpenAI call in `career/engine.py` (see `API_NOTES.md`) — stub currently
- [ ] M-Pesa / payment integration — activate Daraja STK push; enforce feature gate so unlocking requires payment
- [ ] Daraja webhook handler — confirm payment, unlock session, mark `Payment` record as completed
- [ ] Payment success page — show unlocked results after confirmed payment
- [ ] User-scoped results — `StudentCourseMatch` records currently save globally, not per logged-in user
- [ ] Build full-results PDF export (all clusters on one page; current PDF is per-cluster only)
- [ ] Add KCSE result history page — let users compare multiple past calculations
- [ ] HELB loan eligibility tagging — mark government-sponsored course types as HELB-eligible; link to HELB portal; major decision factor for families
- [x] Anonymous/guest calculator flow — works without login; session stashed; CTA prompts registration

---

## P2 — Core Improvements

- [ ] Merge `career/models.py` course system with `courses/models.py` — two parallel course models; see `DECISIONS.md #4`
- [ ] Populate `cutoff_points` for TVET/TTC/KMTC courses (currently 0)
- [ ] Populate minimum subject requirements for TVET courses (`TVET_CLUSTER_DOCUMENT_2025.pdf`)
- [ ] Link TVET/TTC/KMTC `CourseOffering` records to clusters (`cluster` FK not set for seeded records)
- [ ] County-based filtering for KMTC and TTC campuses — location/county field not yet populated on 88 KMTC campuses
- [ ] Fix cluster requirements data gaps — update placeholder descriptions for 4 clusters needing official KUCCPS PDF:
  - **1A (Law)**: `KUCCPS sub-cluster 1A` — no real data
  - **2A (Business)**: truncated at `MAT ALTERNATIVE A/B -`
  - **2B (Hospitality/Tourism)**: `KUCCPS sub-cluster 2B` — no real data
  - **3D (Social Sciences)**: `KUCCPS sub-cluster 3D` — no real data
- [ ] Populate `CareerInsight` data (demand level, average salary) for major courses
- [ ] Populate `CareerProfile` data — models exist; no real Kenyan career data loaded
- [ ] Course offering count on cluster result cards — "X courses available in this cluster" so students know which clusters open more doors
- [x] Search autocomplete — live course/institution suggestions as the user types; client-side filter against existing `?q=` endpoint, no new view needed
- [ ] Recently viewed courses — track last 5 course detail visits per user; show on dashboard quick-access strip; needs `ViewLog` model
- [ ] Institution accreditation badge — tag institutions as CUE-accredited / TVETA-registered / MoE-approved; display as a small badge on cards and detail pages
- [ ] KUCCPS fee structure data — add government tuition fee tier per course type (Govt-sponsored vs Self-Sponsored slot cost); shown on course detail page
- [x] Admin UI for suspending/unsuspending users
- [x] Mark notifications as read — endpoint wired to `Notification.is_read`
- [x] Add institution search (`?q=` filter on type detail page)
- [x] Add course search (`?q=` filter on type/category detail pages)
- [x] Add custom 404 and 500 error pages
- [x] Seed all TVET programmes (Diploma L6, Certificate L5, Artisan L4, Craft L3)
- [x] Seed TTC programmes (79 courses, 88 offerings, 36 institutions)
- [x] Confirm KMTC programmes fully seeded (33 courses, 342 offerings at 88 campuses)

---

## P2 — Payments & Monetisation

- [x] Payment model stub (FEATURE_CHOICES: cluster points, eligible courses, premium report)
- [x] M-Pesa Transaction model stub
- [x] Career results payment gate UI (blurred preview + lock card)
- [ ] Subscription tier system — define Free / Basic / Premium access levels
- [ ] Receipt / invoice email after payment
- [-] Refund flow for failed lookups — deferred; M-Pesa refund process too complex for MVP; handle manually for now

---

## P2 — AI & Prediction Features ⭐⭐⭐⭐⭐

- [ ] **Placement Probability Score** — predict likelihood of placement per course based on past cutoff distributions; output e.g. "Nursing (KMTC Nairobi): 78% chance"
- [ ] **Backup Plan Generator** — if student doesn't qualify for desired course, auto-generate ranked alternatives (Medicine ❌ → Nursing / Clinical Medicine / Lab Tech)
- [ ] **Multi-Path Planner** — present 3 parallel options: Safe / Balanced / High-reward path for any grade profile
- [ ] **AI Admission Strategy Builder** — given grade + preferred course: generate 1st / 2nd / 3rd choice + backup plan with rationale
- [ ] **Career Mistake Detector** — before results load, warn "This course does NOT match your KCSE subjects" or "Your cluster is 18 pts below cutoff — consider these instead"
- [ ] **Alternative Subject Suggestions** — after weak grades entered, suggest which subjects to improve to unlock specific clusters
- [ ] **PDF Career Report** — downloadable personalised report from career engine: cluster scores, matched courses, strategy, backup paths, market outlook

---

## P2 — Analytics & Insights ⭐⭐⭐

- [ ] **Admin Analytics Dashboard** — most searched course, most viewed institution, most saved programme, most downloaded PDF; requires `SearchLog`, `ViewLog`, `DownloadLog` models
- [ ] **Placement Trends Dashboard** — public page: most applied courses this season, fastest-growing careers, most competitive programmes
- [ ] **Competition Pressure Indicator** — per-course badge: Low / Medium / High / Extreme 🔥, from applicants vs intake capacity
- [ ] **Cutoff Trend Chart** — year-on-year cutoff chart per course/university (Chart.js line graph using `cutoff_points` JSONField)
- [ ] **Admission Shock Predictor** — warn on course card "This cutoff has risen 3 pts in 2 years — you may not qualify next year"

---

## P2 — Career Planning Tools ⭐⭐⭐⭐

- [ ] **Career Path Roadmaps** — full journey view: Doctor → KCSE → MBChB (5 yrs) → Internship → Specialisation → Consultant; include salary milestones
- [ ] **Fail-Safe Career Path Engine** — multi-step fallback: course fails → diploma bridge → degree upgrade (e.g. Diploma Nursing → BSc Nursing via bridging)
- [ ] **Job Market Intelligence** — per career: demand level, average salary range in Kenya, top hiring sectors
- [ ] **Reviews** — students rate and review courses/institutions (1–5 stars + text)
- [x] **Student Success Stories** — 6 curated real-feel stories across all pathways and grade ranges (A- to D+); tagged by grade, pathway, institution; on main home page with scroll-triggered entrance animation

---

## P3 — Nice to Have

### UX / Design
- [ ] Mobile-responsive UI audit — verify all pages on 360px viewport; sticky footers in grade entry need testing on small screens
- [ ] Skeleton loading states on course lists (while session data is being processed)
- [ ] Onboarding walkthrough / tooltip tour for first-time users (3-step intro overlay)
- [ ] Print-friendly results page — `@media print` stylesheet so eligible courses list prints cleanly without nav/sidebar chrome
- [ ] Cluster tooltip labels — hovering "Cluster 1A" shows the full cluster name and subject requirements inline
- [ ] Accessibility audit — keyboard navigation, ARIA labels, colour contrast (WCAG 2.1 AA target)
- [x] Micro-animation on career home cards (hover lift, spring easing, icon bounce, shimmer sweep)
- [x] Icons + animations on institution type and course type category pages
- [x] "Back to top" floating button on long result/course pages
- [x] How-to-guides page — step-by-step: how to apply on KUCCPS portal, how cluster points work
- [x] Dark mode toggle (career pages are dark by design; rest of site is light)

### Personalisation
- [x] Personalised Dashboard — Recommended For You, Cluster chart, Watchlist, Application Timeline, Quick Actions
- [ ] Dashboard: County & Institution Filter Memory — persist preferred counties/institution types to User model
- [ ] Dashboard: Activity Feed — "You viewed 12 courses yesterday" / "Cutoff for Medicine rose 2pts"; requires `UserActivityLog`
- [ ] Smart Alerts System — notify when cutoff changes for a saved course or deadline approaches; needs Celery/cron + `Notification` model triggers
- [ ] Smart Course Recommendation Feed — "Top 5 courses for B+ students this year", "Low competition, high salary", "Hidden gem courses"
- [ ] Dashboard: AI-powered "Why This Course?" — 1-sentence rationale per Recommended card (needs OpenAI key)
- [ ] Dashboard: Push/email alert when saved course's predicted cutoff changes
- [-] AI "Explain Like I'm 5" Mode — dropped; adds complexity for marginal UX gain
- [-] AI Parent Mode — dropped; parents are not the primary user; cover via guides/FAQ instead
- [-] Hidden Talent Career Match (personality quiz → viral shareable) — dropped; not core to placement mission

### Career Engine
- [ ] Grade simulator — "What if I scored B+ instead of C in Chemistry?" — re-run without re-entering everything
- [ ] AI chatbot guidance — conversational interface using `career/engine.py` once OpenAI is live
- [ ] Course comparison tool — compare 2–3 courses side-by-side (cutoffs, requirements, institutions)
- [ ] "Best pathway for my grades" recommendation — auto-suggest Degree / Diploma / KMTC based on aggregate

### Community & Communication
- [ ] News Panel — KUCCPS announcements, application deadlines; shown on dashboard and homepage
- [ ] Student-to-Admin Chat — in-app messaging widget
- [ ] Shareable results link — token-based URL so results can be shared without login
- [ ] Personalised email digest — weekly email with new courses matching a saved profile
- [x] WhatsApp share button on results
- [-] Instagram-style result card image (generated PNG) — dropped; Pillow/canvas complexity not justified

---

## P2 — Traffic & Growth

- [x] Guest mode — calculator and eligible courses work without login; session-based; CTA banner prompts registration
- [ ] **Shareable score card** — after calculator runs, "Share your score" button generates a pre-filled WhatsApp message with cluster score + eligible course count; catch viral moment right after results
- [ ] **Post-registration WhatsApp share prompt** — on registration success screen, one-click WhatsApp button: "I used KUCCPSS to find my courses → kuccpss.co.ke"; students share when excitement is highest
- [ ] **SEO page titles** — login and register pages use generic titles; update to include target keywords e.g. "Create Free Account | KUCCPSS — Kenya Cluster Points Calculator"
- [ ] **Urgency banner (peak season)** — site-wide banner June–August: "KUCCPS portal opens in X days — build your shortlist now"; show countdown to non-logged-in users; drives registrations before deadline
- [ ] **"Save your results" non-blocking prompt** — on calculator results, show sticky bottom bar (not a wall) prompting guest to register; grades already in session so it feels instant
- [ ] **Google Analytics / Posthog funnel** — track: landing → calculator → eligible courses → register conversion; identify where users drop off

### Content & Data
- [ ] Update Terms & Conditions — add version tracking + re-acceptance prompt on T&C version change
- [ ] KCSE 2025 cutoff data update once KUCCPS releases 2025 placement report
- [ ] University admission deadlines calendar — per institution, per year
- [ ] "Apply Now" links — direct links to KUCCPS / university online application portals
- [ ] Scholarship opportunities section linked to courses
- [ ] KCSE revision resources — link grade improvement tips to specific weak subjects
- [x] KUCCPS application calendar — key dates: portal opens/closes, revision window, results day

### Technical
- [ ] N+1 query audit — eligible courses view and career engine results loop over ORM objects in Python; needs `select_related` / `prefetch_related` pass
- [ ] Cache static lookups — subject list, cluster list, institution types change rarely; add Django cache (Redis or local-mem) to avoid repeated DB hits per request
- [ ] Docker / deployment config (Procfile + Dockerfile + `render.yaml`)
- [ ] Write unit tests for cluster points calculation — the formula must never regress
- [ ] Write integration tests for grade entry → loading → results flow
- [ ] Progressive Web App (PWA) manifest + service worker for offline support
- [ ] Google Analytics / Posthog event tracking (page views, pathway selections, payment funnel)
- [ ] Sentry or similar error monitoring for production exceptions
- [x] Add rate limiting to login and registration views
- [x] SEO — meta tags, OpenGraph, Twitter Card on all key pages
