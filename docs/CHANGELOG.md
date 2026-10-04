# Changelog

Format: `[YYYY-MM-DD]` — description of what changed and why.

---

## [Unreleased]

### In Progress
- Career engine AI recommendation text — CareerNext AI chat live; `generate_ai_recommendation()` still returns stub text in non-chat flow
- Mentorship B2C payout disbursement — IntaSend "Send Money" must be activated on account before auto-payouts work

---

## [2026-10-04] — Mentorship: booking integrity, calendar invites, automatic refunds
- **Slots:** a cancelled slot can be rebooked (slot is now a FK with a one-active-session constraint, migration 0016). Booking claims the slot atomically. Slots starting within 30 min are hidden. Unpaid bookings are released after 30 min by `release_abandoned_bookings`, which checks IntaSend first.
- **Calendar:** .ics text is escaped and folded per RFC 5545. Each recipient gets a REQUEST invite with ORGANIZER/ATTENDEE. Cancellation sends METHOD:CANCEL. The Google link carries `ctz`. Google ignores .ics alarms; the UI now says so.
- **Lifecycle:** mentors can't complete before start. Auto-complete and the admin action send the rating request. The 1-hour reminder also goes out as web push. Expired checkouts redirect to booking.
- **Money:**
  - Reversing a payout that was already paid out records `payout_debt` (migration 0017), recovered from the next earnings.
  - Confirmation emails are claimed atomically, so they're sent once.
  - A payment arriving after release reclaims the slot if it is free, otherwise it is refunded.
- **Refunds:** automatic via the IntaSend chargebacks API on cancellation and late payment (migration 0018: `refund_ref`, `refund_requested_at`, `refund_error`). Failures email admin. The new admin action "Refund via IntaSend" retries. "Mark as refunded" is now record-only.
- **Dark mode:** `/career/results/` filter bar, result cards, chips, backup plan and AI panel.

## [2026-10-03] — CareerNext AI chat: database tools, site guide, identity
- **New `career/ai_assistant.py`:** the chat brain now lives here; `ajax_ai_chat` in `career/views.py` handles only access, credits and logging.
- **Reads the database through OpenAI tool calling.** The model can look things up while answering:
  - `search_courses`
  - `get_course_details`: cutoffs per institution, plus the student's eligibility computed by the server
  - `find_courses_i_qualify_for`
  - `search_institutions`
  - `get_institution_courses`
  - `search_careers`
  - `search_help_articles`

  It makes up to 4 lookup rounds, in both streaming and non-streaming modes.
- **Student data:** taken from the session first. If that is empty, it falls back to the latest snapshot, then the saved `UserKCSEResult`, then the latest `ClusterCalculationResult`. The AI never asks for subjects.
- **Knows itself and the site:**
  - What CareerNext is and who built it (Meshack Limo, Francis Oduor).
  - That it is independent from KUCCPS.
  - A verified map of site pages, which the test `AIAssistantTests.test_site_guide_paths_resolve` checks.
  - Example replies that give it a head start, and a personality section that allows creativity.
- **More tools:**
  - `compare_courses` compares 2–3 courses side by side: requirements, cutoff range, where the student qualifies, and salary.
  - `get_salary_outlook` reads `JobMarketData`.
  - `get_my_shortlist` reads the shortlist and saved courses, with eligibility for each.
  - `get_course_details` now includes `predicted_next_cutoff` from `predictor.services.predict_cutoff`.
- **Reply format:** point form with a summary first. Every reply ends with `<<FOLLOWUPS: a | b | c>>`. The chat page shows these as tap-able chips, `cnAiFormat` hides the marker everywhere, and the JSON response returns `followups` separately.
- **Clickable links:** new `static/js/ai_format.js` (`cnAiFormat`) renders the AI's Markdown in the chat page, the results-page assistant and the dashboard widget. It only allows links to site paths and to official HTTPS domains on an allow-list.

## [2026-10-02] — Course salary data: coverage and accuracy
- **Matching fixed** (`career/job_market.py`): course names now match keywords as whole words, and the longest keyword wins. This stops false hits such as "vet" in "TVET", "ict" in "conflict" and "mechanic" in "mechanical". The broad category fallback was removed. Diploma and certificate courses now show the technician-level salary (e.g. Diploma in Electrical Engineering → Electrical Technician) instead of the degree-level one.
- **Coverage:** 1,803 of 1,814 courses (99%) now show a salary, up from about 60%. The 11 still unmatched are generic "Bachelor of Arts/Science" and pure Philosophy, left blank on purpose.
- **Salaries updated from 2025 CBAs:**
  - Medical Doctor: KSh 200k–400k (KMPDU intern pay).
  - Clinical Officer: KSh 105,900–338,010 (KUCO–CoG CBA 2025–2029).
  - Secondary School Teacher: KSh 50k–130k (TSC CBA 2025–2029).
- **44 new careers** (`ESTIMATED_CAREERS` in `seed_job_market.py`): criminology, public administration, international relations, theology, languages, chemistry/physics/biology, planning, project management, and technician equivalents. Each record's source name says it is a KUCCPSS estimate.
- **Deploy:** run `python manage.py seed_job_market` on the server (or deploy with `RUN_SEEDS=1`), then restart the app so the `lru_cache` lookup reloads.

## [2026-10-02] — Background jobs actually run in production
- **In-process scheduler** (`kuccpss/scheduler.py`): Render runs no qcluster worker or cron, so the django-q Schedules never fired. A daemon thread started by the web server now runs pending-payment recovery (`check_pending_payments`) and mentorship reminders/auto-complete every 10 minutes. A Postgres advisory lock lets only one process run a cycle. Toggle with `BACKGROUND_JOBS_ENABLED` (defaults to on when `DEBUG` is off).
- **Mentorship reminders sent once:** new `MentorshipSession.reminder_sent` flag (migration 0015). Previously, repeated runs inside the 60–120 min window re-sent the email, and windows crossing midnight were missed. The logic moved to `mentorship/tasks.py`; `mentorship_housekeeping` now calls it.
- **Per-worker background threads:** gunicorn's `preload_app` ran `AppConfig.ready()` in the master, so the homepage cache warmer never ran in the workers that serve requests. The warmer and the scheduler now start in each worker from the `post_worker_init` hook in `gunicorn.conf.py`.
- **Keep-awake ping:** each scheduler cycle requests `KEEPALIVE_URL/health/` (defaults to Render's `RENDER_EXTERNAL_URL`), so the free-tier service doesn't sleep after 15 idle minutes and stop running jobs.
- **Fix:** sharing the calculator with a malformed body returns 400 instead of 500.
- **Tests:** career pathway/quiz/AI chat/share tests, calculator share tests, mentorship task and scheduler tests (196 total).

---

## [2026-10-01] — Database integrity, monitoring and recovery
- **Money race fixes:**
  - Mentor session confirmation, cancellation and refunds, and mentor/affiliate withdrawals and admin payout actions now use conditional status updates and `F()` balance changes inside `transaction.atomic`. Concurrent requests or webhook retries can no longer double-credit or double-debit a wallet.
  - Affiliate commission credit is now atomic: the commission row and the wallet credit commit together or not at all.
- **DB constraints:**
  - Money amounts must be ≥ 0, payment status must be a known value, and the affiliate commission rate must be between 0 and 100.
  - At most one pending withdrawal per mentor or affiliate (partial unique constraint).
  - Migrations `accounts/0018`, `mentorship/0014`, `payments/0013` and `analytics/0011` mark older duplicate pending withdrawals as `failed` before adding the constraint.
- **Auto-payout:** a pending withdrawal row is created *before* the B2C call. A failed payout now leaves a `failed` row instead of nothing.
- **Webhook:** retried IntaSend webhooks no longer create duplicate `Transaction` rows, and malformed amounts no longer cause a 500.
- **Audit trail:** new read-only `analytics.AuditLog` and `analytics.audit.record()` for payments, exemptions, wallet credits/debits, withdrawals and refunds.
- **Monitoring:**
  - New `manage.py db_health` checks connectivity, migrations, storage, connections, long queries, cache hit ratio, unindexed FKs, unused indexes, bloat and ledger/payment consistency.
  - `SlowQueryLogMiddleware` logs slow queries and requests that issue too many queries.
  - `/health/` reports `db_ms`.
  - Opt-in `DB_STATEMENT_TIMEOUT_MS` (direct connections only).
- **Restore testing:** the backup workflow now restores each nightly dump into a throwaway Postgres, then runs `migrate` and `db_health` against it.
- **Tests:** new `payments/test_integrity.py`, `mentorship/test_integrity.py` and `analytics/test_db_health.py`.
- **Docs:** new runbook [DATABASE_OPERATIONS.md](DATABASE_OPERATIONS.md).

---

## [2026-09-29] — Security hardening
- **Staff TOTP 2FA:**
  - `StaffSecurityMiddleware` requires every `is_staff` user to verify a code from an authenticator app. Unenrolled staff are sent to `/accounts/staff/2fa/setup/` (QR code); enrolled staff re-verify every 12 h.
  - The secret is Fernet-encrypted at rest. Replayed codes are rejected, and wrong codes are limited to 5 per 5 min.
  - New `StaffTOTPDevice` model (migration `accounts/0017`) and new dependency `segno` for the QR code.
  - Recovery: superuser admin delete, or `manage.py reset_staff_2fa <email>`. `STAFF_2FA_REQUIRED=False` is the emergency kill switch.
- **Staff sessions:** 12 h idle expiry (`STAFF_SESSION_MAX_AGE`) instead of 90 days.
- **Login throttling:** there is now also a per-account limit (8 failures / 15 min), alongside the per-IP limit, so distributed guessing is caught. Counters are atomic (`cache.add` + `incr`) and are cleared on success.
- **Script-context XSS:** 59 `{{ x|safe }}` inside `<script>` blocks (analytics dashboards, both `course_detail` templates) are replaced with the new builtin `|js_json` filter. It escapes `<`, `>` and `&` like `json_script`, so a stored `</script>` can't break out.
- **Headers:**
  - An enforced CSP subset (`object-src 'none'; base-uri 'self'; frame-ancestors 'self'`) alongside the existing report-only policy.
  - New `Permissions-Policy` disabling camera, mic, geolocation, payment, USB and the sensors.
- **Other fixes:**
  - The change-password view now requires 8 characters. It previously required only 4, which bypassed the registration rule.
  - `analytics:pwa_install` is limited to 5/hour/IP.
- `docs/SECURITY.md` updated. It also corrects stale sections: the mentorship webhook is signed, and IP resolution is unified in `kuccpss/ip_utils.py`.

## [2026-09-29] — Fix intermittent "Continue with Google" failures
- Sessions: `cached_db` only when `REDIS_URL` is set, plain `db` otherwise. Per-worker `LocMemCache` let one gunicorn worker serve a stale session that was missing the OAuth `state` another worker had just saved, so the callback failed depending on which worker handled it.
- New `CanonicalHostMiddleware` 301/308-redirects `www.careernext.co.ke` → `careernext.co.ke` (`CANONICAL_HOST` env var; `''` disables). This avoids split host-only session cookies and a Google `redirect_uri` that differed by host.
- `SocialAccountAdapter` now uses `on_authentication_error()` and raises `ImmediateHttpResponse`. The old deprecated `authentication_error()` redirect was ignored, so users saw allauth's "Third-Party Login Failure" page. Messages now distinguish cancelled / timed out / other errors, and the log line includes the host.
- Login/register show a warning inside WhatsApp/Instagram/Facebook/TikTok in-app browsers, where Google blocks OAuth (`403 disallowed_useragent`), with a copy-link button.

## [2026-09-29] — Circuit breakers for OpenAI and IntaSend
- New `kuccpss/circuit_breaker.py`: cache-backed breaker opens after 5 service failures (timeout, connection error, 5xx, 429) in 60s, refuses calls for 60s, then half-opens. Client errors (e.g. 400 bad phone) never trip it.
- Wrapped every OpenAI call (quiz summary, AI insight, AI chat incl. streaming, OCR upload, `generate_ai_recommendation`) and IntaSend STK push + status fetch. B2C payouts and webhooks are deliberately not wrapped.
- AI chat / insight check the breaker **before** charging a message credit; STK push views check it before creating a `Payment` row. Users get a 503 "try again in a minute" instead of a hung request.
- OpenAI clients now come from `get_openai_client()` with a 45s timeout and 1 retry (SDK default was 600s × 2 retries).

## [2026-09-29] — Payment pages overhaul + "paid but still locked" recovery
- **Root-cause fixes:** payment → CareerSubmission link is always written (not only when a lock config exists) and `has_paid_for_current_session` self-heals a missing link; `complete_payment()` makes fulfilment idempotent across webhook / poll / code / sweep races; stale-payment sweep asks IntaSend before marking anything failed.
- **M-Pesa code recovery** (`verify_by_transaction_code`): accepts a pasted SMS, checks logged transactions, then asks IntaSend about recent unconfirmed payments, then queues for admin review (code stored on the Payment + admin email). Rate-limited, rejects codes owned by other accounts. Admins approve by setting the payment to Completed.
- **Shared UI:** `templates/payments/_payment_help.html` "Paid but still locked?" panel (code entry + WhatsApp/email from SiteSettings `whatsapp_number` / `contact_email`) on every payment surface; `payment_polling.js` handles 409 resume, already-unlocked, tab-return re-check and a final verify before timeout.
- **Pages:** payment_required (how-it-works, resume banner, no-prompt tips, already-unlocked state, honest non-"lifetime" copy), paywall overlay (phone step now hides while waiting), calculator gate (fixed invisible white-on-white code input), AI chat top-up modal (accepts 07/01 numbers, no NaN counter), payment history (mobile cards, Check status, PDF receipts, status legend), mentorship checkout timeout guidance. All mobile-friendly with 44px tap targets and 16px inputs.

## [2026-09-29] — Admin actions reach users

### Fixed
- Payments: admin "Mark completed" (and editing status to Completed) now runs the same fulfilment as the webhook via `payments.views.fulfil_completed_payment()` — feature unlock, AI credits, receipt email, affiliate commission; mentorship payments confirm the session. Previously it only flipped the status and the feature stayed locked
- Mentor withdrawals: "Mark processed" / "Reject" now handle `failed` requests (failed B2C payouts are what admins must settle), debit the wallet only when processing, skip insufficient balances, and email the mentor on rejection
- Mentorship "Mark refunded" no longer debits the mentor for sessions that were never confirmed; it frees the slot, marks the payment refunded and emails the mentee
- Mentor approval email shows the real payout (was hardcoded KES 70); rejection email no longer says "you may re-apply"; ticking Approved/Rejected on the change form now emails the applicant
- Reject-mentor button and broadcast "Send Now" are no longer state-changing GET links: both show a confirmation page and act on POST; broadcasts are claimed atomically so a double-submit can't send twice, and are delivered in a background thread (no request timeout); the status flips to Failed with the delivered count if sending stops early
- Suspending a user now signs out their existing sessions (`SuspendedUserMiddleware`); admins can't suspend themselves; suspend/unsuspend counts are correct when the list is filtered
- Admin links in failed-withdrawal alert emails pointed to `/admin/…` (404) — now `reverse()` to `/cn-staff/…`
- Affiliate commission "Mark paid out" debited the wallet per commission while processing a withdrawal also marks pending commissions paid out, risking a double debit — it now records one processed `AffiliateWithdrawalRequest` per affiliate, debits once, skips insufficient balances and emails the affiliate
- Affiliate payout emails linked to `/accounts/affiliate-dashboard/` (404) — now `reverse('accounts:affiliate_dashboard')`

### Added
- Affiliate withdrawal admin actions: mark processed (manual payout) / mark failed, both notifying the affiliate
- "Activate as affiliate" emails each newly activated affiliate with a dashboard link
- Confirmation messages on every bulk action that lacked them (feedback resolve/dismiss, session actions)
- `accounts/test_admin_smoke.py` — renders every admin changelist/add page and exercises the user-facing actions

---

## [2026-09-29] — Course cutoff trend chart

### Changed
- Chart logic moved into `courses.views._cutoff_trend()`; offerings need 2+ non-empty years to plot, and years come from the data instead of a hardcoded 2021–2025 list (table view included)
- "Average" line now averages only institutions with a cutoff in every plotted year — previously the sparse 2025 data made the average jump
- Colours use the validated categorical palette with light and dark steps; the chart recolours when the dark-mode toggle flips. Lines are straight (no curve smoothing overshooting the real values)
- Course detail offerings query now also selects `institution_type` (removes an N+1 in the table view)

### Added
- "Add another institution" picker on the trend chart — any institution beyond the top six can be plotted as a highlighted line

---

## [2026-09-28] — Database linkage cleanup

### Fixed
- 19 Craft (L3) / Artisan (L4) `CourseCategory` rows were still attached to the opposite level after the earlier course-level swap fix, leaving 94 courses whose category belonged to another course type — categories moved to the matching type and slugs renamed (`a4-*` ↔ `c3-*`)
- Stale `accounts.applicationtracking` content type (and its 4 permissions) removed

### Removed
- 106 non-degree courses with no `CourseOffering` (no institution) — mostly Short Course / Trade Test / Proficiency / Professional, plus 13 L5, 11 L3 and 4 L4 entries
- Empty course types: TVET Short Course, TVET Trade Test, TVET Proficiency, TVET Professional
- `seed_tvet_craft_artisan` (used the old swapped L3/L4 mapping and would wipe offerings) and `seed_tvet_remaining` (created courses without offerings)
- Short Course career pathway (home card, KCSE-input and floating-modal options, pathway maps in `career/views.py` / `clusterpoints/eligibility.py`) and the four types from `seed_tvet.py`; `/career/input/shortcourse/` now redirects to the career home

---

## [2026-09-28] — Database performance & reliability pass

### Changed
- `calculate_all_clusters` persists the 18 results with bulk update/create + one M2M rewrite (~90 queries → 11); formula untouched
- `PageTrackingMiddleware` writes logs through one bounded per-process queue/worker instead of a thread + fresh DB connection per request; bots no longer get a DB session row per hit
- `SiteSetting.get` cached (5 min, invalidated on save/delete); `deadline_banner` no longer re-queries every request when no banner is active
- Quiz submission uses prefetched options + `bulk_create`; mentorship rating distribution is one grouped query; shortlist PDF and cluster detail no longer bypass prefetch / re-count
- `CONN_HEALTH_CHECKS` on persistent DB connections; Redis cache socket timeouts
- `backup_db` now writes compressed custom-format dumps, keeps SSL params from `DATABASE_URL` (Neon), and prunes to `--keep` (default 7)

### Added
- `.github/workflows/db-backup.yml`: daily encrypted off-site `pg_dump` (needs `BACKUP_DATABASE_URL` + `BACKUP_PASSPHRASE` secrets; 30-day artifact retention)
- Index `(user, is_read, created_at)` on Notification; functional `UPPER(mpesa_ref)` index on Transaction
- `build.sh` runs `clearsessions` and `purge_notifications` on deploy
- `redis` in requirements (RedisCache/django-q would crash without it when `REDIS_URL` is set)

### Removed
- 22 duplicate single-column indexes on fields already indexed by `unique=True` or a ForeignKey (migrations `*_db_index_cleanup`)

---

## [2026-09-27] — KUCCPS-style programme search & variations

### Added
- `courses/programmes.py`: reduces course names to a core programme ("BACHELOR OF SCIENCE (DATA SCIENCE)" / "BSc in Data Science" / "Bachelor of Data Science" → "data science")
- `/courses/?q=` programme search (`templates/courses/programme_search.html`): results grouped by programme with institution counts and all name variations, best match first, filterable by course type. The courses hub search box and the navbar "see all" link now land here
- Course detail "Variations of …" card: same programme under other names + related programmes (e.g. Data Science and Analytics), each listing its institutions and latest cutoff

### Fixed
- In-page course search matched ANY word ≥3 chars ("data science" returned every "Bachelor of Science …" course); now every significant word must match and results are ranked by relevance

---

## [2026-09-27] — KUCCPS 2025 cutoffs, 18 clusters, per-course requirements

### Added
- `import_kuccps_portal` management command + `scripts/scrape_kuccps_portal.py` → `data/kuccps_portal_degrees.json` (1,126 portal programme pages, 2,226 offerings)
- `import_kuccps_institutions` management command (`--dry-run`, `--no-create`) + `data/kuccps_portal_institutions.json` (514 rows from students.kuccps.net/institutions/): sets institution type (public/private university, KMTC, TTC, public/private TVET) and location as "Town, County County" from the portal. Renames university TVET wings stored under the parent university's name, and institutes upgraded to National Polytechnics; creates 85 portal institutions missing locally. Kaimosi Friends University → public; 4 colleges private → public TVET. Duplicate local rows are reported and merged by the new `merge_institutions` command (Kaiboi TTI → Kaiboi National Polytechnic, KU – Mama Ngina → Mama Ngina University College, Kirinyaga Central TVC, Laikipia/Tharaka University TVET, stray "Nairobi kmtc" → KMTC Nairobi; offerings/reviews/promotions/mentors/analytics logs moved, shared courses' cutoffs combined); institutions not on the portal (mostly private TVETs) are untouched
- 2025 cutoffs for 958 degree offerings; 2023/2024 values refreshed from the portal. Year keys are the portal's KCSE-year labels (no shift)
- `Course.entry_requirements` (migration `courses/0010`) — the 4 cluster-subject slots; `subject_requirements` filled from the portal for 700 courses (GSC ignored)
- `programme_code` on offerings; 7 new universities/university colleges, 145 new degree courses, 331 new offerings
- `clusters/constants.py` — the 18 KUCCPS cluster names
- [KUCCPS_2025_CLUSTER_MOVES.md](KUCCPS_2025_CLUSTER_MOVES.md) — the 98 courses that moved cluster

### Changed
- 20 calculator clusters → the 18 KUCCPS clusters (101–118), subject slots rebuilt from the portal; 119/120 and all 61 sub-clusters removed; saved results recalculated
- "Latest cutoff" shown to students = the `LATEST_CUTOFF_YEAR` (2025) value only, "—" when KUCCPS published none; eligibility still uses the newest year on record (`CourseOffering.newest_cutoff()`), and match results label a non-2025 cutoff with its year
- Predictor, cluster list/detail, PDF export, CareerNext AI prompt and all copy now say 18 clusters; predictor maps clusters by `number − 100`
- `seed_clusters` builds clusters from the portal data; admin/CSV cutoff editing gains 2025, caps at 48 and merges instead of wiping other years
- `DATA_VERSION` 2025, `DATA_CYCLE` 2026/2027, `DATA_UPDATED` September 2026
- FAQ "What are the 18 KUCCPS clusters?" (old example wrongly called Cluster 1 Medicine)
- Degree `CareerSessionSnapshot`s still keyed on the old 20 clusters deleted (they regenerate on the student's next Degree results view); `llms.txt` KMTC count 88 → 98 campuses; `seed_tvet` docstring warns to re-run `import_kuccps_institutions` + `merge_institutions` after re-seeding

---

## [2026-07-02] — Grade-entry forms now tell students exactly what's missing

### Changed
- `KCSEForm.clean()` (`clusterpoints/forms.py`) — invalid submissions now name the missing compulsory subjects ("You haven't entered a grade for: Mathematics…") and say how many more subjects are needed, instead of per-field errors the accordion templates never rendered (students only saw "Please correct the errors below")
- Calculator, degree grade entry, and pathway input pages (`calculator.html`, `degree_calculate.html`, `pathway_input.html`):
  - Continue/Calculate button now also requires English, Kiswahili and Mathematics client-side (was: any 7 subjects, then a vague server rejection)
  - Footer note names the specific missing subjects, not just a count
  - Tapping the disabled button now flashes the reason, opens the Core Subjects accordion, and scrolls to/highlights the first missing required subject (`pointer-events: none` on `:disabled` lets the tap reach the footer wrapper); on the mean-grade pathway variant it scrolls to the mean grade or category section
  - Multiple form errors render one per line instead of concatenated
- Views pass `required_subject_names` to the three templates (`clusterpoints/views.py::kcse_calculator_view`, `career/views.py::degree_calculate`, `career/views.py::pathway_input`)

---

## [2026-07-02] — CareerNext AI chat: streaming replies, prompt caching, student-friendly formatting

### Added
- Token streaming in `ajax_ai_chat` (`career/views.py`) — chat page sends `stream: true` and renders the reply as it types via `StreamingHttpResponse`; dashboard/results widgets keep the JSON path
- "Student-friendly style" section in the chat system prompt: direct answer first, simple English, terms explained in brackets, replies under ~120 words for simple questions, top 5 course matches by default (was 10)

### Added (chat answers from DB, no more interrogating the student)
- `_build_ai_db_context` now injects the student's saved KCSE subject grades (session `career_subject_grades`, falling back to `UserKCSEResult`/`SubjectResult`) and mean grade into the chat prompt
- `_search_courses_for_message` (`career/views.py`) — targeted DB lookup of courses named in the student's question (e.g. "Do I qualify for Nursing?") injecting real cluster, min mean grade, subject requirements, and per-institution cutoffs; max 2 per course type so Degree AND Diploma/KMTC routes both appear
- Prompt rules: "check student data sections FIRST — never ask for grades/subjects if present" and "'Do I qualify for X?' → verdict in the first line, one card, no questions"

### Changed
- System prompt reordered so all static rules come first and per-student KB/DB context comes last — enables OpenAI automatic prompt caching (faster first token, ~50% cheaper input on the long static prefix)
- Removed the "say you can only see their top 10 matches" rule — the AI now evaluates any course found by the targeted lookup
- Chat `max_tokens` raised 400 → 700 so course recommendation cards no longer truncate mid-sentence
- Chat markdown renderer (`templates/career/chat.html` `fmt()`) now supports `###` headings, numbered lists, and escapes HTML in model output

---

## [2026-06-30] — Admin-configurable AI model/temperature, SiteSetting performance knobs, analytics dashboard expansion

### Added
- `CareerConfig.ai_model_name` / `ai_temperature` fields (migration `0022_careerconfig_ai_model_name_and_more.py`) — all CareerNext AI calls (chat, insight, quiz summary) now read the OpenAI model name and sampling temperature from the admin panel instead of hardcoded `'gpt-4o-mini'` literals scattered across `career/models.py` and `career/views.py`
- `SiteSetting` performance group seeded via migration `resources/0007_seed_performance_settings.py`: `courses_per_page` (24), `mentors_per_page` (18), `trends_cache_ttl` (3600s) — admin can now tune pagination and cache lifetime without a deploy
- Homepage static context caching (`public_home_static_v1`, 300s) in `public_home_view` to cut repeated DB hits on the landing page
- Four new analytics sub-dashboards: Calculator Analytics, Conversion Analytics, Retention Analytics, AI Chat Analytics (`analytics/views.py`, wired in `analytics/urls.py`)
- Event logging added in `career/views.py` and `clusterpoints/views.py` for AI chat, calculator runs, and PDF export/share actions feeding the new dashboards

### Changed
- `courses/trends.py`, `courses/views.py`, `mentorship/views.py` now read pagination size / cache TTL from `SiteSetting` instead of hardcoded constants

---

## [2026-06-25] — Brand logo circles, payment polish, M-Pesa code verify on calculator paywall

### Changed
- Brand and institution logos rendered as circles (CSS border-radius update site-wide)

### Added
- `/payments/verify-code/` M-Pesa SMS code verification added to **calculator paywall** (was previously only on career engine paywall)
- "I already paid" fallback flow on calculator gate — user can enter M-Pesa confirmation code to unlock without waiting for STK push

### Fixed
- Email system polishing pass — confirmed Resend SMTP flows for all transactional emails (registration, session booking, cancellation)
- Cloudinary storage fix for Django 5.2 — guarded against malformed `CLOUDINARY_URL` on startup; `django-cloudinary-storage` activated correctly

---

## [2026-06-24] — Mentorship: price privacy, mentee phone, auto-verify; MentorshipConfig mentor_signup toggle

### Added
- `mentor_signup_enabled` flag moved from `CareerConfig` to `MentorshipConfig` (migration 0009); admin now controls mentor signups from the mentorship config panel
- Mentee phone number captured at booking — stored on `MentorshipSession.mentee_phone`; used for M-Pesa outreach
- Auto payment verify on session status page — polls IntaSend in background; confirms session without manual action
- Mentor price privacy — session price hidden from mentor directory listing until booking step

### Fixed
- Mentorship session page 500 error — fixed in commit 93d5630; view now handles missing slot/mentor gracefully
- Calculator 33s load time — query optimisation; eligible courses view now uses `select_related` / `prefetch_related`

---

## [2026-06-23] — Affiliate system, mentorship Meet links, course spotlight, UI overhaul

### Added — Affiliate system
- `AffiliateProfile` model — referral_code, commission_rate, balance, total_earned
- `AffiliateCommission` model — per-payment commission record (FK to affiliate + payment)
- `AffiliateWithdrawalRequest` model (accounts migration 0012) — withdrawal from affiliate balance
- `/accounts/affiliate/` dashboard — stats, commissions table, withdrawal request form
- `payments/services.py` — credits affiliate on successful payment via webhook

### Added — Mentorship Google Meet link
- `MentorshipSession.meet_link` field (migration 0007) — admin/mentor can set Google Meet URL; shown to both parties after session confirmation
- `mentorship/calendar_utils.py` — Google Meet link embedded in ICS calendar download

### Added — Course spotlight / trends page
- `CourseSpotlight` model in `courses/models.py` (migration 0007) — admin-configurable spotlight courses
- `InstitutionPromotion` model in `institutions/models.py` (migration 0004) — admin-configurable featured institutions with priority and label

### Changed — Major template redesign
- `base.html` — navigation overhaul; affiliate dashboard link; bottom nav updated
- `accounts/dashboard.html` — course spotlight section, Trending Now (ViewLog-powered), Clusters + Institutions sections
- `accounts/shortlist.html` — complete redesign with priority flags and deadline display
- `accounts/about.html`, `accounts/terms.html`, `accounts/privacy.html` — full redesign
- `career/career_results_v2.html` — WhatsApp share button improvements

### Fixed
- `clusterpoints/eligibility.py` — extracted shared eligibility logic; view refactor
- `institutions/admin.py` — format_html error fixed

---

## [2026-06-22] — Cluster points midpoint-marks formula; CareerNext AI paywall; multi-mentor price; analytics; Railway config; security hardening

### Changed — Cluster points formula
- `clusterpoints/services.py` — switched from `grade×7/400` to midpoint raw marks per grade band (A=90.2 … E=14.0) divided by 400, capped at 48; extracted shared `_weighted_cp()` helper used by both anonymous and saved-result calculators
- `career/models.py` — `calculate_cluster_points()` now converts grade letters → points via `KCSEGrade`, computes proper KCSE aggregate, picks best 4 cluster subjects, and calls `_weighted_cp()` — same formula as the cluster calculator
- `career/engine.py` — replaced dummy stub with real dispatch to `match_degree_courses()` and other pathway functions; no longer returns hardcoded matches

### Added — CareerNext AI paywall + credits system
- `AIChatCredit` model (career migration 0016) — lifetime free-tier + paid-tier message tracking per user
- `CareerConfig` fields: `ai_free_message_limit`, `ai_paid_message_limit`, `ai_free_reset_days`
- `PaymentFeature` seeded for `ai_chat_access` (KES 50 default, editable in admin)
- In-chat paywall modal — M-Pesa STK push flow (phone → polling → success/fail/timeout/code-entry); no page redirect
- Credit counter badge in chat header; 2-message low-balance warning
- `AIChatCreditAdmin` bulk actions: top-up credits, reset counter
- `AIKnowledgeEntry` model (career migration 0008) — admin-editable KB entries injected into AI system prompt
- Full CareerNext AI system prompt: 20 clusters, subject requirements, HELB/HEF rules, off-topic refusal, Golden Pre-check

### Added — Per-mentor price override
- `MentorProfile.custom_price` field — mentor can set their own session price; falls back to `MentorshipConfig.default_price`
- `MentorProfile.custom_payout_rate` field — admin can set custom payout % per mentor

### Added — Analytics models
- `SearchLog`, `ViewLog`, `DownloadLog`, `EventLog`, `CareerEngineLog` models in `analytics` app
- `analytics.context_processors` — injects PostHog key, Sentry context, GA measurement ID, data version
- Most-viewed courses aggregated from `ViewLog` → shown on dashboard Trending Now section

### Added — Railway migration config
- `railway.toml` in project root — Railway Hobby deployment config
- `gunicorn.conf.py` — gunicorn workers/threads config for Railway

### Added — Security hardening
- `payments/models.py` — `PaymentExemption` model (migration 0006) — admin grants free access per user per feature
- `SECURE_SSL_REDIRECT = True` in production settings
- `HeavyEndpointRateLimitMiddleware` — rate-limits `/career/` and `/clusterpoints/` heavy views
- `SlowRequestLogMiddleware` — logs slow requests to EventLog
- `GracefulErrorMiddleware` — catches unhandled exceptions, returns friendly response

### Added — Submission controls
- `SubmissionLockConfig` model (career migration 0014) — controls cooldown window between career engine re-submissions
- `CareerSubmission` model (career migration 0015) — records each submission per user with method + pathway
- `SharedResult` model (career migration 0007) — token-based shareable results URL; `/career/shared/<token>/`

### Fixed
- `courses/trends.py` — homepage 500 fixed: `MAX(jsonb)` not supported in PostgreSQL; compute most-competitive cutoff ranking in Python via `latest_cutoff()` instead of DB-side annotation
- `accounts/models.py` — `FieldError` fixed: replaced `date_joined` with `created_at` (custom User model uses `created_at`)
- `Cloudinary` crash on startup — guarded against malformed `CLOUDINARY_URL` (strips env var if it doesn't start with `cloudinary://`)

---

## [2026-06-19] — Security hardening + email verification wired

### Security
- Added `CommonPasswordValidator`, `NumericPasswordValidator`, `UserAttributeSimilarityValidator` to `AUTH_PASSWORD_VALIDATORS` (was only `MinimumLengthValidator`)
- Set `SOCIALACCOUNT_LOGIN_ON_GET = False` — eliminates CSRF risk on Google OAuth callback
- Added production-only security block: `SECURE_PROXY_SSL_HEADER` for Render, HSTS (1yr + subdomains + preload), `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, `SECURE_CONTENT_TYPE_NOSNIFF`, `SESSION_COOKIE_HTTPONLY`, `CSRF_COOKIE_HTTPONLY`
- `SECRET_KEY` now raises `RuntimeError` at startup if the insecure fallback value is used in production
- Admin URL moved from `/admin/` to `/cn-staff/` to reduce brute-force exposure

### Email
- Configured Resend SMTP in `settings.py`: activates automatically when `RESEND_API_KEY` env var is set; falls back to `console.EmailBackend` in dev
- `DEFAULT_FROM_EMAIL` set to `CareerNext <noreply@careernext.co.ke>` (overridable via env var)
- `RegisterView` now calls `send_mail()` with a real verification link — removed the `is_verified = True` short-circuit that bypassed email verification
- `is_verified = False` on registration; user must click email link before login is allowed
- Login error message updated to direct unverified users to check inbox/spam

---

## [2026-06-13] — TVET, TTC & KMTC full programme seeding; level mapping fixes; institution overhaul

### Added — TVET programme seeder (`courses/management/commands/seed_tvet_programmes.py`)
- Reads 4 KUCCPS PDF files and seeds `Course` + `CourseOffering` records for all TVET levels:
  - `DIPLOMA_PROGRAMMES.pdf` → **TVET Diploma (Level 6)**: 319 courses / 4,515 offerings
  - `CERTIFICATE_PROGRAMMES.pdf` → **TVET Certificate (Level 5)**: 159 courses / 4,947 offerings
  - `ARTISAN_18_03_2024_RV2.pdf` → **TVET Artisan Certificate (Level 4)**: 68 courses / 2,738 offerings
  - `CRAFT_18_03_2024_RV2.pdf` → **TVET Craft Certificate (Level 3)**: 77 courses / 1,801 offerings
- Supports `--dry-run` and `--pdf <key>` flags; fully idempotent (`get_or_create` throughout)
- `normalize()` helper strips apostrophes (by Unicode codepoint), normalises `&`→`AND`, collapses hyphens/spaces, strips trailing LEVEL/CDACC/CBET qualifiers
- `section_prefix_whitelist` per PDF prevents cross-level contamination (e.g., Certificate PDF's stray Craft sections are skipped)
- `SKIP_TEXT_RE` guards against column header rows leaking into institution lookups

### Fixed — Level mapping contamination (multiple migration scripts in `resources/`)
- Certificate PDF contained ~115 `CERTIFICATE IN X` sections that had been seeded under Level 3 — migrated to Level 5, merging with any existing Level 5 courses
- Pre-loaded data had Level 3/4 swapped (Craft courses under Level 4, Artisan under Level 3) — fixed by:
  - Moving 71 "Craft Certificate/Craft in X" courses from Level 4 → Level 3 (with offering merge)
  - Moving 26 "Artisan Certificate in X" courses from Level 3 → Level 4
  - Moving 1 "Certificate in X" course from Level 4 → Level 5

### Fixed — Institution name matching
- Added 21 missing TVET institutions that appeared in the PDFs but not in DB
- Fixed "Kitutu Chache" name mismatch (`&` vs `AND` normalisation)
- Fixed "Co-operative" vs "Cooperative" mismatch (merged pre-loaded Level 5 course into PDF-seeded one)
- Result: Level 5 = 0 unmatched, Level 4 = 0 unmatched, Level 3 = 0 unmatched, Level 6 = 0 unmatched after TTC fix (was 25)

### Fixed — Course detail URL namespace (`courses/views.py`)
- Courses moved between types (due to level-mapping fix) caused 404s because `redirect('course_detail', ...)` did not use the `courses:` namespace
- Fixed to `redirect('courses:course_detail', ...)` and `redirect('courses:course_detail_no_category', ...)`
- View now falls back to slug-only lookup and transparently redirects to the corrected URL

### Added — TTC programme seeder (`courses/management/commands/seed_ttc_kmtc.py`)
- Reads `DSTE_18_03_2024_RV2.pdf` (17 pages, Diploma Secondary Teacher Education) — same artisan-style table format (section header rows in table cells)
- Seeds **79 TTC courses / 88 offerings** under CourseType "TTC"; 0 unmatched institutions
- Reads `KMTC_Programmes.pdf` (25 pages) — continuous table format with `CAMPUS` column; no section headers
- KMTC was already fully seeded (33 courses / 342 offerings confirmed via `get_or_create`; 0 new)
- Campus OCR word-split artifacts handled by space+hyphen-free key matching: `re.sub(r"[\s\-]", "", name.upper())` — e.g., "CHEMOLIN GOT" → "CHEMOLINGOT", "KABARNE T" → "KABARNET"
- `KMTC_CAMPUS_ALIAS` dict for genuine OCR typos (e.g., "SATELITE" → "SATELLITE")

### Added — TTC institution data overhaul
- Renamed all 21 existing TTC institutions from "X Teachers College" to "X Teachers Training College" to match PDF naming convention
- Added 16 missing TTC institutions: Aberdare, Asumbi, Bishop Mahon, Borabu, Chesta, Egoji, Kaimosi, Kenyenya, Kericho, Kibabii Diploma, Mandera, Moi Baringo, Narok, St. John's Kilimambogo, St. Marks Kigari, St. Augustine Eregi (renamed from "Eregi Teachers College")
- **36 total TTC institutions** in DB

### Fixed — TVET Diploma offerings for TTC institutions
- After TTC institution rename, re-ran `seed_tvet_programmes --pdf diploma` to pick up 25 previously-unmatched TTC institutions in the diploma PDF
- Created **134 new TVET Diploma (Level 6) offerings** at TTC campuses that also offer TVET-level diplomas

### Final DB state (all programme types)
| Course Type | Courses | Offerings |
|---|---|---|
| TTC | 83 | 141 |
| KMTC | 33 | 342 |
| TVET Diploma (Level 6) | 319 | 4,515 |
| TVET Certificate (Level 5) | 159 | 4,947 |
| TVET Artisan Certificate (Level 4) | 68 | 2,738 |
| TVET Craft Certificate (Level 3) | 77 | 1,801 |
| Degree | 958 | 2,007 |

---

## [2026-06-11] — KMTC data, course search, institutions overhaul, aggregate bug fix

### Fixed
- `clusterpoints/models.py` + `clusterpoints/services.py` — aggregate total calculation bug: after picking the best language (English/Kiswahili), the non-best language was being discarded instead of returned to the subject pool. This caused aggregates to be 3–5 points too low for students who scored well in both languages. Fix: return the lower language score back to the remaining subjects before selecting the top 5.

### Added — KMTC data layer
- `courses/models.py` — added `minimum_mean_grade` (CharField, e.g. "C+") and `subject_requirements` (JSONField, list of slot-dicts) to `Course` model; migration `0004_add_kmtc_fields` applied
- `courses/models.py` → `CourseOffering` — added `programme_code` CharField (e.g. `5000K32`) for KMTC programme reference codes
- `courses/management/commands/seed_kmtc.py` — seeds 87 KMTC campuses as `Institution` records, 33 unique programmes as `Course` records, and 342 `CourseOffering` records; supports `--clear` flag

### Changed — KMTC course detail page
- `templates/courses/course_detail.html` — KMTC courses no longer show the cutoff year table (2024/2023/2022/2021 columns). Instead shows: "Minimum Mean Grade" red badge card, "Subject Requirements" table (slot / subjects / min grade), and "Campuses Offering This Programme" table (campus name + programme code). Non-KMTC courses unchanged.
- Sidebar: shows `minimum_mean_grade` for KMTC; "Offered At" hidden for KMTC; label changes to "Campuses"

### Added — Course search
- `courses/views.py` — `course_type_detail` and `course_category_detail` now accept `?q=` GET param and filter by `name__icontains`. When searching on a type that has categories, the category grid is bypassed and matching courses are shown directly.
- `templates/courses/course_type_detail.html` — search bar with result count and ✕ clear link; KMTC cards show `minimum_mean_grade` badge
- `templates/courses/course_category_detail.html` — same search bar pattern; empty state distinguishes "no results" from "no courses yet"

### Added — Career guidance home redesign
- `templates/career/home.html` — redesigned to 6-box grid layout for pathway selection

### Added — Institutions section overhaul
- `institutions/models.py` — added `abbreviation` field (CharField max 20) to `Institution` model; added `bg_color` property to `InstitutionType` that maps `color_code` to its light background equivalent
- `institutions/migrations/0002_add_abbreviation.py` — applied
- `institutions/admin.py` — `abbreviation` added to `list_display` and detail fieldset
- `institutions/views.py` — full rewrite:
  - `institution_types_list`: annotates `inst_count`, sorts by fixed ORDER (Public → Private → KMTC → TVET → TTC)
  - `institution_type_detail`: annotates `course_count` via `Count('offerings')`, supports `?q=` search
  - `institution_detail`: builds grouped offerings dict `{course_type: {category: [offerings]}}` for nested template rendering
- `templates/institutions/institution_types_list.html` — 5 coloured category cards using model `icon`, `color_code`, `bg_color` fields directly (no `{% elif %}`)
- `templates/institutions/institution_type_detail.html` — search bar; cards showing logo/fallback, name, abbreviation badge, location with pin icon, green course count badge
- `templates/institutions/institution_detail.html` — breadcrumbs + abbreviation in hero; courses grouped by type → category; cutoff badge (green ≥70 / amber ≥55 / red <55) or min grade badge; sidebar with abbreviation, location, website, email, phone, course count; PDF brochure download
- `institutions/management/commands/seed_institution_types.py` — upserts 5 institution types with icons/colours/descriptions; back-fills abbreviation + location for 30 known public universities and 20 private universities using name fragment matching

### Fixed
- `templates/institutions/institution_types_list.html` — `TemplateSyntaxError`: Django templates do not support `{% elif %}`. Removed all conditional `{% with %}` chains; template now reads `type.icon`, `type.color_code`, and `type.bg_color` directly from the model.

---

## [2026-06-11] — URL routing fix, Unicode data cleanup, TIME_ZONE fix

### Fixed
- `courses/views.py` — `course_category_detail` view was causing HTTP 404 for all "Details" buttons on cluster detail pages. Root cause: `courses/urls.py` URL pattern `<type_slug>/<category_slug>/` (course_category_detail, position 3) matched before `<type_slug>/<course_slug>/` (course_detail_no_category, position 5) because Django takes the first match for identical 2-segment slug patterns. Fix: wrapped `CourseCategory.objects.get()` in `try/except CourseCategory.DoesNotExist` and delegated to `course_detail()` when no category matches the slug. All "Details" buttons across all 20 cluster groups now return 200.

### Fixed (continued)
- `settings.py` `TIME_ZONE` — removed duplicate `UTC` definition on line 133; now consistently `Africa/Nairobi` in one place
- Cluster descriptions — replaced Unicode en-dash (U+2013) garbled characters with proper ` -` in 16 clusters: 12A, 13A, 15B, 15C, 15D, 15E, 15F, 15G, 20A, 3E, 4A, 5B, 5C, 6B, 9B, 11A. Requirements text now renders cleanly on cluster detail pages.

### Still Needed (data gaps in source CSV — require official KUCCPS PDF)
- Cluster minimum subject requirements still missing for 3 clusters (placeholder descriptions):
  - **Law, Commerce & Business (1A)** — no requirements in source PDF
  - **Business, Management & Information (2B)** — no requirements in source PDF
  - **Communication, Media & Social Sciences (3D)** — no requirements in source PDF
- Cluster 2A (Business, Management & Information) has a **truncated** description: `MAT ALTERNATIVE A/B -` (cut off mid-sentence during PDF extraction)
- Several clusters have Unicode replacement characters (`?`) in descriptions from PDF extraction (15B, 15C, 15D, 15E, 15G, 5B, 5C, 3E, 11A, 9B, 4A, 4B, 6B) — requirements still display but with garbled dashes
- All 61 KUCCPS clusters have 0 SubjectGroups; the cluster points calculator falls back to the student's top 4 subjects as core for every cluster

---

## [2026-06-10] — Documentation audit and corrections

### Fixed
- ARCHITECTURE.md: removed non-existent `CoreSubject` model; replaced with `CourseOffering` through model and `core_subjects` M2M field
- ARCHITECTURE.md: added missing models — `CareerProfile`, `QuizQuestion/Option/Submission/Answer`, `SavedCourse`, `SavedCareer`, `ApplicationTracking`, `Notification`, `Resource`, `Article`, `Payment`, `Transaction`
- ARCHITECTURE.md: updated URL structure to include resources, payments, and correct accounts paths
- FEATURES.md: corrected `Media files setup` status to ✅ (MEDIA_ROOT/MEDIA_URL are configured)
- FEATURES.md: corrected `Email backend config` status to 🚧 (console backend configured; not production SMTP)
- FEATURES.md: added Career Profiles, Quiz, Saved Items, Notifications, Resources, Payments sections
- TODO.md: marked MEDIA_ROOT/MEDIA_URL task as `[x]` (done)
- TODO.md: added TIME_ZONE double-definition fix to P0 blockers
- TODO.md: added Resources views and M-Pesa integration to P2; added notification read endpoint and data population to P3
- CHANGELOG.md: corrected courses app entry (CoreSubject → CourseOffering); added all missing models and apps

---

## [2026-06-10] — Initial codebase documentation

### Added
- `CLAUDE.md` — Claude Code instructions and critical rules
- `PROJECT_CONTEXT.md` — Kenyan education system context and business rules
- `ARCHITECTURE.md` — app structure, data flow, model reference
- `FEATURES.md` — full feature status inventory
- `DECISIONS.md` — key design decisions with rationale
- `TODO.md` — prioritised backlog
- `API_NOTES.md` — OpenAI integration plan
- `CHANGELOG.md` — this file

---

## [Prior to 2026-06-10] — Development phase

### accounts app
- Custom User model: UUID PK, email-only auth, is_verified/is_suspended flags
- Email verification token (24h), password reset token (2h)
- Remember me token (72h), device session tracking, login history
- Google OAuth via django-allauth
- Terms & conditions page with agreed_terms field

### clusters app
- Subject model (KCSE subjects)
- Cluster model with auto-slug and auto-number
- SubjectGroup model linking subjects to clusters with required/optional flag

### clusterpoints app
- GradePoint model (A=12 to E=1)
- UserKCSEResult + SubjectResult for storing KCSE input
- ClusterCalculationResult with weighted formula
- KCSE calculator view with bulk SubjectResult creation
- Results dashboard view
- PDF export via ReportLab
- Admin analytics view
- `clusterpoints/services.py` — standalone calculate_all_clusters() service

### institutions app
- InstitutionType model (Public Uni, Private Uni, KMTC, TVET, TTC)
- Institution model with logo, PDF, location, contact fields
- List and detail views for types and institutions

### courses app
- CourseType, CourseCategory, Course models
- CourseOffering through model (Course↔Institution with per-institution cutoff_points JSONField)
- Course linked to Institution (M2M via CourseOffering), Cluster (FK), core_subjects (M2M to clusters.Subject)
- Cutoff points as JSONField per year at both Course and CourseOffering level
- Course type, category, and course detail views

### career app
- Standalone course models: Course, TVETCourse, KMTCourse, TTCCourse
- University, KMTCampus, TTCCollege, TVETCategory models
- CourseCutoff and CourseCutoffHistory for tracking cutoff trends
- StudentCourseMatch and AIRecommendation models
- CareerInsight model (demand, salary, fields)
- CareerProfile model (title, slug, duties, skills, career_tags, demand_level, M2M to courses.Course)
- QuizQuestion, QuizOption, QuizSubmission, QuizAnswer for career assessment quiz
- Career guidance engine (stub — not yet connected to OpenAI)
- Views: pathway selection, KCSE input, results, course detail, AI history, career profiles list/detail, quiz, quiz results
- AJAX endpoints: TVET subject validation, live admission update
- CSV export of matches
- Filtering and search across matches

### resources app
- ResourceCategory, Resource (PDF/video/link, download_count), Article (content, tags, is_published) models

### payments app
- Payment model (feature gating stubs), Transaction model (M-Pesa stub)

### accounts app (additions)
- SavedCourse, SavedCareer models for bookmarking
- ApplicationTracking model with status workflow
- Notification model with type choices and is_read flag
- Notification context processor (unread_notification_count in all templates)
