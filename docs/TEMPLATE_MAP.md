# Template Map

`templates/` contains 144 HTML files. All templates that extend Django's block system inherit from
[templates/base.html](../templates/base.html) unless noted otherwise. See
[FOLDER_STRUCTURE.md](FOLDER_STRUCTURE.md) for the top-level layout and
[DJANGO_ARCHITECTURE.md](DJANGO_ARCHITECTURE.md) for context processors available to every template.

## base.html — master layout

Blocks defined: `title`, `meta`, `keywords`, `canonical`, `og_type`, `og_meta`, `twitter_meta`,
`schema_org`, `extra_schema`, `extra_head`, `content`, `extra_js`.

Loads Bootstrap 5.3.2, Bootstrap Icons, Font Awesome 6.4.2, Google Fonts Inter, HTMX 1.9.12,
jQuery 3.7.1 slim, [static/css/style.css](../static/css/style.css),
[static/js/main.js](../static/js/main.js). Renders: PWA splash screen (first open only), flash
messages, navbar with global search, deadline countdown banner (`resources` context processor),
`site_announcements` loop, mobile bottom nav, PWA install banner + iOS install modal, feedback
button/modal, offline banner, 60s session-heartbeat ping to `analytics:heartbeat`. Dark-mode toggle
persists to `localStorage['kuccpss-dark']` and applies a `body.dark` class (the standardized
dark-mode selector site-wide — see the STATIC_FILES.md note on `mentorship/directory.html`'s
inconsistent use of `[data-bs-theme="dark"]`). Registers `/sw.js` service worker. Conditionally
injects GA4/Sentry/PostHog scripts from `analytics` context processors. 5-column footer.

`career/base_career.html` extends `base.html` but applies a dark-themed override for all career-app
pages (per design decision — "career pages are dark by design").

`analytics/base_analytics.html` extends `base.html` and defines a full CSS design-system
(`--navy`, `--blue`, `--green`, etc.) plus a sticky sidebar shell used by every staff analytics
dashboard (see [STATIC_FILES.md](STATIC_FILES.md) for the component-class inventory).

## Per-app template tables

### accounts/ (views in [accounts/views.py](../accounts/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `dashboard.html` | Personalized dashboard: recommended courses, cluster-points chart, watchlist/shortlist, application timeline, trending courses, spotlight | `dashboard_view` |
| `login.html` | Split-panel login (email/password, remember-me, Google OAuth) | `LoginView` |
| `register.html` | Split-panel registration (email, password, county, kcse_year, terms) | `RegisterView` |
| `home.html` | Public marketing homepage (cached 5 min) | `public_home_view` |
| `about.html`, `terms.html`, `privacy.html`, `faq.html`, `how_it_works.html` | Static informational pages | resp. static views |
| `profile.html` / `profile_update.html` | View / edit profile | `profile_update_view` (GET/POST) |
| `saved_courses.html` | `SavedCourse` bookmarks list | `saved_courses_view` |
| `shortlist.html` | `CourseShortlist` management (priority/deadline/rank) | `shortlist_view` |
| `comparison.html` | Side-by-side course comparison | `course_comparison_view` |
| `notifications.html` | Notification inbox (marks read on visit) | `notifications_view` |
| `broadcast_notification.html` | Staff form to broadcast a notification | `broadcast_notification_view` |
| `applications.html` / `application_form.html` | List / create-edit `Application` records | application CRUD views |
| `referral.html` | Referral link + stats | `referral_view` |
| `affiliate_dashboard.html` | Affiliate stats, commissions, withdrawal form | `affiliate_dashboard` |
| `staff_team.html` | Public staff team page | `staff_team_view` |
| `re_auth.html` | Step-up re-authentication prompt | `re_auth_view` |
| `email_confirm.html` / `email_verification_sent.html` | Email verification click-through / "check inbox" | `email_verify_view` |
| `change_password.html` | Change password (recent-auth required) | `change_password_view` |
| `password_reset_*.html` (4 templates) | Custom (non-allauth) password reset flow | password reset views |
| `google_login.html` / `google_oauth_link.html` | Google login trigger / account-linking | allauth-adjacent views |

### account/ + socialaccount/ (django-allauth overrides)

| Template | Purpose |
|---|---|
| `account/password_reset.html` | Split-panel reset-request form (allauth override; hardcoded `email` input, not a form widget) |
| `account/password_reset_done.html` | "Email sent" confirmation |
| `account/password_reset_from_key.html` | Set-new-password after clicking reset link |
| `account/password_reset_from_key_done.html` | Password-changed confirmation |
| `socialaccount/login.html` | Renders as the "Continue with Google" (`gconfirm`) consent card; **auto-submits** on page load for instant login (per commits `b73e1b0`/`2337777`) |
| `socialaccount/signup.html` | Social-signup form shown if extra info is needed post-OAuth |

### admin/ (Django admin overrides)

| Template | Purpose |
|---|---|
| `admin/base_site.html` | Injects a custom analytics quick-link bar into the admin nav; conditionally loads GA4/Sentry (with `browserTracingIntegration`/`replayIntegration`, authenticated-user context)/PostHog scripts |
| `admin/index.html` | Custom admin index override |
| `admin/accounts/notification/change_list.html` | Custom change-list for `Notification` (likely adds a broadcast action) |
| `admin/analytics/overview.html` | Admin-embedded analytics overview, linked from the nav bar |

### clusterpoints/ (views in [clusterpoints/views.py](../clusterpoints/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `calculator.html` | KCSE grade entry + results; Chart.js cutoff trend; M-Pesa payment-gate polling flow | `kcse_calculator_view` |
| `eligible_courses.html` | Courses the student qualifies for at their cluster points (payment-gated) | `eligible_courses_view` |
| `admin_analytics.html` | Staff-only totals (users/results/clusters) | `admin_analytics` |

### clusters/ (views in [clusters/views.py](../clusters/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `cluster_list.html` | List of all 61 KUCCPS clusters | `cluster_list` |
| `cluster_detail.html` | Single cluster: subject groups, requirement text | `cluster_detail` |
| `cluster_courses.html` | Courses linked to a cluster | `cluster_courses` |
| `cluster_form.html` | Staff create/edit form | `cluster_create`/`cluster_edit` |
| `subject_group_form.html` | Staff create/edit form for `SubjectGroup` | orphaned — no URL wired (see [URL_MAP.md](URL_MAP.md)) |

### courses/ (views in [courses/views.py](../courses/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `course_types_list.html` | Pathway landing grid (Degree/Diploma/KMTC/TVET/TTC) with quick search | `course_types_list` |
| `course_type_detail.html` | Courses within a type | `course_type_detail` |
| `course_category_detail.html` | Courses within a category | `course_category_detail` |
| `course_detail.html` | Full course detail: branches by course type (degree Chart.js trend vs KMTC/TVET tables), shortlist/save AJAX, reviews, job-market card, mentorship CTA | `course_detail` |
| `spotlight_trends.html` | `CourseSpotlight` & trending courses page (cached) | trends view |
| `_course_items_partial.html` / `_course_list_partial.html` | AJAX/HTMX grid & list partials | included by list views |

### institutions/ (views in [institutions/views.py](../institutions/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `institution_types_list.html` | Type landing grid, color-coded by category | `institution_types_list` |
| `institution_type_detail.html` | Institutions within a type | `institution_type_detail` |
| `institution_detail.html` | Institution detail: `grouped_offerings` (type→category), cutoff badges, reviews | `institution_detail` |
| `_institution_items_partial.html` / `_institution_list_partial.html` | AJAX/HTMX partials | included by list views |

### career/ (views in [career/views.py](../career/views.py)) — 40+ templates

| Template | Purpose | Rendered by |
|---|---|---|
| `home.html` | 6-box pathway-selection grid (Degree/Diploma/KMTC/TVET/TTC) | `home` |
| `kcse_input.html` | Unified KCSE grade-input accordion | `kcse_input` |
| `pathway_input.html` | Per-pathway accordion inputs (mean-grade picker for TTC/Artisan) | `pathway_input` |
| `career_type.html`, `degree_step.html`, `diploma_step.html`, `tvet_step.html`, `artisan_step.html`, `input_form.html` | Individual pathway-selection/grade-entry step templates | various step views |
| `degree_entry.html`, `degree_options.html` | Degree pathway landing + 4 method-selection cards (manual/upload/paste) | `degree_entry`, `degree_options` |
| `degree_manual.html` | Manual cluster selection (~20 clusters with real offerings) | `degree_manual` |
| `degree_upload.html` | OCR document upload UI (GPT-4o Vision) | `degree_upload` |
| `degree_paste.html` | Paste-grades entry — regex-parsed KUCCPS-format or plain-value cluster points | `degree_paste` |
| `degree_calculate.html` | Review/correction step after OCR extraction | `degree_calculate` |
| `loading.html` | Animated loading screen while engine processes | `loading_page` |
| `career_results_v2.html` (aka `results.html`) | Match results: filters/sort, WhatsApp share, payment-gate blurred preview | `career_results` |
| `report.html` | Results/report summary view | pdf/report-related views |
| `eligibility_card.html` | Reusable card: one matched course's `admission_chance` | included by results templates |
| `course_detail.html` | Career-engine's own course detail (parallel to `courses/course_detail.html` — legacy system, see [DATABASE.md](DATABASE.md)) | `course_detail` (career) |
| `chat.html` | CareerNext AI chat UI: credit counter, in-chat M-Pesa paywall modal | `career_chat` |
| `ai_guidance_modal.html`, `ai_response.html` | AI insight modal / single-response partial | AJAX AI endpoints |
| `ai_recommendations.html` | Stored AI recommendation history | `ai_recommendations` |
| `quiz.html` / `quiz_results.html` | Career-assessment quiz UI / top-6 matches | `quiz_view` / `quiz_results_view` |
| `career_profiles.html` / `career_profile_detail.html` / `_career_profile_items_partial.html` | Career profile list / detail / AJAX grid partial | `career_profiles_list` etc. |
| `shared_result.html` / `shared_result_expired.html` | Public token-based results view / expired-token state | `shared_result_view` |
| `floating_modal.html` | Generic floating modal partial | included where needed |

### mentorship/ (views in [mentorship/views.py](../mentorship/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `directory.html` | Public mentor directory (uses non-standard `[data-bs-theme="dark"]` — see [STATIC_FILES.md](STATIC_FILES.md)) | `directory` |
| `become_mentor.html` / `become_mentor_success.html` | Mentor application form / confirmation | `become_mentor` |
| `mentor_dashboard.html` | Approved-mentor dashboard: stats, upcoming/past sessions, availability management, withdrawal form | `mentor_dashboard` |
| `edit_profile.html` | Mentor profile edit form | `edit_mentor_profile` |
| `mentor_profile.html` | Public mentor profile (bio, courses, slots) | `mentor_profile` |
| `book_session.html` | Booking form (slot radio choices, mentee question/phone) | `book_session` |
| `checkout.html` | Session booking checkout/payment step | `checkout` |
| `session_detail.html` | Session status/detail (payment polling, meet link) | `session_detail` |
| `my_sessions.html` | Mentee's booked-sessions list | `my_sessions` |
| `rate_session.html` / `cancel_session.html` | Post-session rating / cancellation form | resp. views |
| `_mentor_items_partial.html` | AJAX grid partial for mentor listings | directory search |

### payments/ (views in [payments/views.py](../payments/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `payment_required.html` | Full-page dark M-Pesa unlock page; phone→waiting→success/failed/timeout state machine; polls `payments:payment_status` every 3s (40 attempts / 2 min) | `payment_required` |
| `paywall_overlay.html` | Full-screen blurred paywall overlay partial (separate JS namespace `pw*` from `payment_required.html`'s `pr*` — **duplicated polling logic**, see [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)) | included in gated views (calculator, eligible_courses, career results) |
| `payment_history.html` | User's past payments list | `payment_history` |
| `signup_gate_overlay.html` | Guest-registration prompt overlay (distinct from the payment paywall) | included where guests hit a gate |

### predictor/

| Template | Purpose | Rendered by |
|---|---|---|
| `index.html` | Single-page cutoff-trend predictor (select cluster, view WMA+naive trend) | `predictor_index` |

### resources/ (views in [resources/views.py](../resources/views.py))

| Template | Purpose | Rendered by |
|---|---|---|
| `resource_list.html` | Sidebar search/categories + `_resource_items_partial.html` grid | `resource_list` |
| `_resource_items_partial.html` / `_article_items_partial.html` | AJAX grid partials | included by list views |
| `article_list.html` | Article list with tag cloud, featured hero, schema.org JSON-LD | `article_list` |
| `article_detail.html` | Single article page | `article_detail` |
| `calendar.html` | KUCCPS Application Calendar (2024/2025 cycles, timeline) | `kuccps_calendar` |
| `guides.html` | How-To Guides static page (6 guides) | `how_to_guides` |
| `resource_detail.html` | Single resource (PDF/video/link) detail | `resource_detail` |

### analytics/ (all extend `analytics/base_analytics.html`; staff-only)

| Template | Purpose | Rendered by |
|---|---|---|
| `dashboard.html` | Overview KPIs, activity chart, conversion funnel, auth split, career-pathway donut; tabbed (Overview/Users/Content & Search/Career Engine/Payments/Live Activity/Monitoring/Feedback) | `analytics_dashboard` |
| `actions.html` | User action analytics + daily trend | `actions_analytics` |
| `pages.html` | Top/slow pages, 4xx/5xx errors, device split, geo breakdown | `pages_analytics` |
| `payments.html` | Pending/stale/failed/completed/refunded payment queues | `payments_overview` |
| `calculator.html` | Calculator run volume, guest vs auth split, grade distribution | `calculator_analytics` |
| `career_engine.html` | Career engine usage analytics | `career_engine_analytics` |
| `conversion.html` | Conversion funnel (view→shortlist), top/zero-converting courses | `conversion_analytics` |
| `retention.html` | Weekly cohort retention heatmap (12-week window) | `retention_analytics` |
| `insights.html` | Peak-hours heatmap, referral sources, new-vs-returning, funnels | `insights_dashboard` |
| `ai_chat.html` | AI chat volume/trend, free/paid split, KB hit rate, revenue | `ai_chat_analytics` |
| `mentor_analytics.html` | Mentor comparison table, monthly session/payout chart | `mentor_analytics` |
| `affiliate_analytics.html` | Affiliate comparison table, commission chart | `affiliate_analytics` |
| `user_timeline.html` | Per-user chronological activity feed | `user_timeline` |

### emails/ (standalone, table-based HTML — no Django `{% extends %}`)

| Template | Purpose |
|---|---|
| `transactional.html` | Generic branded transactional email (heading, body_lines, optional info table, CTA button, footnote) — used by `send_branded_email()` |
| `payment_receipt.html` | Payment receipt/invoice email |

### partials/

| Template | Purpose |
|---|---|
| `pagination.html` | Reusable pagination control (preserves `?q=`, smart-ellipsis window) |
| `reviews_section.html` | Reusable star-rating + AJAX review section, parameterized by `target_type` ("course"/"institution") |

### Root-level

| Template | Purpose |
|---|---|
| `404.html` | Extends base.html; gradient "404", nav shortcuts, course search |
| `429.html` | Rate-limit exceeded page (matches `HeavyEndpointRateLimitMiddleware`) |
| `500.html` | Standalone server error page (previewable at `/errors/500/` in DEBUG) |
| `offline.html` | Standalone (no base.html) — PWA offline fallback cached by `sw.js`'s `OFFLINE_URL` |
| `llms.txt` / `robots.txt` | Rendered as templates at their respective routes |

## Cross-references

- Formula/business-rule text appearing in templates (e.g. calculator results, PDF exports) must
  match [clusterpoints/services.py](../clusterpoints/services.py) — see [DATABASE.md](DATABASE.md)'s
  flagged discrepancy with the dead `ClusterCalculationResult.calculate_cluster_points()` method.
- Payment-gated templates (`payment_required.html`, `paywall_overlay.html`, `eligible_courses.html`,
  `career_results_v2.html`) all interact with `payments.PaymentFeature`/`FEATURE_TO_PRODUCT` — see
  [DATABASE.md](DATABASE.md) and [API_AND_SERVICES.md](API_AND_SERVICES.md).
