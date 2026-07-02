# Feature Catalog (Developer Onboarding)

This document is a feature-by-feature developer guide to KUCCPSS/CareerNext. For each feature it lists purpose, every file involved, the user-facing flow, current state, and explicitly flagged gaps/inconsistencies. It complements (does not replace) the [FEATURE_STATUS.md](FEATURE_STATUS.md) status table, [ARCHITECTURE.md](ARCHITECTURE.md), [DECISIONS.md](DECISIONS.md), and the cross-reference docs [DATABASE.md](DATABASE.md), [URL_MAP.md](URL_MAP.md), [TEMPLATE_MAP.md](TEMPLATE_MAP.md).

Read [CLAUDE.md](../CLAUDE.md) before changing any of the "Critical Rules" areas (cluster formula, aggregate calc, custom User model, career engine, two course systems).

---

## 1. Authentication

**Purpose:** Email/password login plus Google OAuth, backed by a custom UUID-keyed `User` model (no username field). Includes email verification, password reset, "remember me" persistence, and a re-authentication gate for sensitive actions.

**Files:**
- `accounts/models.py` — `User`, `UserManager`, `EmailVerificationToken`, `PasswordResetToken`, `RememberToken`, `DeviceSession`, `LoginHistory`
- `accounts/views.py` — `RegisterView`, `LoginView`, `email_verify_view`, `logout_view`, `change_password_view`, `re_auth_view`
- `accounts/forms.py` — `UserRegistrationForm`, `UserLoginForm`, `PasswordChangeForm` (defined but unused — see below), `_check_email_domain`/`validate_password_strength`
- `accounts/urls.py` — `login/`, `logout/`, `register/`, `verify-email/<token>/`, `change-password/`, `re-auth/`, plus `include('allauth.urls')`
- `accounts/adapters.py` — `AccountAdapter`, `SocialAccountAdapter` (swallow SMTP/OAuth-config errors so they never 500)
- `accounts/signals.py` — `log_user_login`, `log_user_login_failed`, `log_user_logout`, `mark_google_user_on_connect`, `on_user_signed_up`
- `accounts/decorators.py` — `require_recent_auth` (30-minute re-auth window)
- `accounts/tasks.py` — Django-Q async email tasks (`send_verification_email`, `send_welcome_email` — see gap below)
- `kuccpss/settings.py` — `AUTH_USER_MODEL`, `AUTHENTICATION_BACKENDS`, allauth config block, `GOOGLE_OAUTH_AVAILABLE`
- `kuccpss/urls.py` — mounts `accounts.urls` **and** `django.contrib.auth.urls` **and** `allauth.urls` all at `/accounts/` (see gap)
- Templates: `templates/accounts/login.html`, `register.html`, `email_confirm.html`, `email_verification_sent.html`, `change_password.html`, `re_auth.html`, `password_reset_*.html`; allauth overrides `templates/account/password_reset*.html`; `templates/socialaccount/login.html` (Google consent card), `templates/socialaccount/signup.html`

**Flow:**
1. **Register** — `RegisterView` (class-based, `accounts/views.py`) validates `UserRegistrationForm` (min 4-char password, disposable-email/MX-record domain check), creates the user **already active and immediately logged in**, creates an `EmailVerificationToken`, sends a branded verification email synchronously via `kuccpss/email_utils.py::send_branded_email`, attributes any pending referral (`Referral.attribute_from_session`), converts a matching `EmailLead` if one exists, and redirects straight to the dashboard. Rate-limited to 5 registrations/hour/IP.
2. **Login** — `LoginView` validates `UserLoginForm` (authenticates, blocks suspended/inactive accounts), sets a 90-day sliding session, stamps `_auth_verified_at` in session (used by the re-auth gate), rate-limited to 10 failed attempts/15min/IP.
3. **Google OAuth** — handled entirely by `django-allauth`; `accounts/adapters.py::SocialAccountAdapter` prevents a 500 if Google credentials are missing; `accounts/signals.py` marks `is_google_user=True` and auto-verifies email on both `social_account_added` and `user_signed_up` signals. The actual `SocialApp` DB row is provisioned by `build.sh` (not part of the Django app) from `GOOGLE_CLIENT_ID`/`GOOGLE_SECRET` env vars. `GOOGLE_OAUTH_AVAILABLE` (derived from `GOOGLE_CLIENT_ID` presence) gates whether templates render the Google button. `templates/socialaccount/login.html` is a redesigned, JS-auto-submitting consent card (per recent commits `b73e1b0`/`0fbb694`/`2337777`).
4. **Email verification** — `email_verify_view` validates token expiry (24h) and marks `EmailVerificationToken.is_used=True` + `User.is_verified=True`.
5. **Password reset** — handled by allauth's built-in flow (`account/password_reset*.html` templates); a **separate**, apparently unused/legacy custom flow also exists (`accounts/password_reset_*.html` templates + `PasswordResetToken` model) — see gap below.
6. **Re-auth for sensitive actions** — `accounts/decorators.py::require_recent_auth` requires `_auth_verified_at` (session timestamp) to be within `REAUTH_WINDOW_SECONDS = 1800` (30 min); otherwise redirects to `/accounts/re-auth/?next=...`. Applied to `change_password_view` and `accounts/views.py::request_affiliate_payout`, and to `mentorship/views.py::request_withdrawal`.

**State:** Complete and in daily use.

**Flagged issues:**
- **Duplicate `/accounts/` URL mounts.** `kuccpss/urls.py` includes `accounts.urls` (which itself already `include()`s `allauth.urls`), then separately includes `django.contrib.auth.urls`, then separately includes `allauth.urls` *again*. Django resolves by list order so `accounts.urls` wins on name collisions, but the second/third mounts are redundant and a cleanup candidate.
- **`PasswordChangeForm`** in `accounts/forms.py` is defined but `change_password_view` implements its own manual validation instead — likely dead code.
- **Two independent password-reset flows** appear to coexist: allauth's built-in one (`account/password_reset*.html`, uses `PasswordResetToken`? — needs confirmation) and a custom set of templates (`accounts/password_reset_complete.html`, `password_reset_confirm.html`, `password_reset_done.html`) whose wiring wasn't traced in this pass — worth auditing which one is actually reachable from the login page.
- **Password strength minimum is 4 characters** (`validate_password_strength` in `accounts/forms.py`), intentionally low per an in-code comment; Django's `AUTH_PASSWORD_VALIDATORS` (6-char minimum) is not invoked by the custom registration/change-password paths.
- **IP extraction inconsistency**: `accounts/views.py::get_client_ip` reads the *last* entry of `X-Forwarded-For`; `accounts/signals.py::get_client_ip` (separate, same-named function) reads the *first* entry.
- **`accounts/tasks.py`** (Django-Q async email tasks) appears to duplicate the synchronous email-sending already inlined in `RegisterView.post` — likely legacy/unused, or reserved for a future move to background sending.

---

## 2. KCSE Cluster Points Calculator (core feature)

**Purpose:** Converts a student's 7+ KCSE subject grades into KUCCPS cluster points for all applicable clusters, using the official KUCCPS midpoint-marks formula. This is the foundation every degree-pathway feature (eligibility, career engine, predictor) builds on.

**Files:**
- `clusterpoints/services.py` — **canonical formula implementation**: `GRADE_MIDPOINT_MARKS`, `_weighted_cp()`, `calculate_clusters_anonymous()` (guest, in-memory), `calculate_all_clusters()` (authenticated, DB-persisting)
- `clusterpoints/models.py` — `UserKCSEResult` (has its own `recalc_total_points()` aggregate method), `SubjectResult`, `ClusterCalculationResult`, `GradePoint`
- `clusterpoints/forms.py` — `KCSEForm` (dynamic per-subject grade dropdown), `get_grade_choices()`
- `clusterpoints/views.py` — `kcse_calculator_view`, `dashboard`, `export_cluster_pdf`, `export_full_results_pdf`, `recalculate_view`, `admin_analytics`, `share_calculator_create`
- `clusterpoints/urls.py` — `calculator/`, `export/`, `export/full/`, `recalculate/`, `admin-analytics/`, `eligible/`, `share/create/`
- `clusterpoints/admin.py` — read-only admin for computed results
- `clusters/models.py` — `Cluster`, `SubjectGroup`, `Subject` (the reference data the formula iterates over)
- `clusters/management/commands/seed_clusters.py` — seeds the 31 official subjects and the **20 master calculation clusters** (numbers 101–120), each with exactly 4 `SubjectGroup` slots
- Templates: `templates/clusterpoints/calculator.html` (grade entry + results, Chart.js, M-Pesa payment gate polling)

**Formula (do not change — see CLAUDE.md):**
```
cluster_points = 48 × sqrt( (core_midpoint_marks / 400) × (aggregate_total / 84) )
```
`core_midpoint_marks` = sum of `GRADE_MIDPOINT_MARKS` for the best 4 cluster subjects (capped at 48 overall). Aggregate (max 84) = Mathematics + best(English, Kiswahili) + next 5 best; the non-chosen language returns to the subject pool before picking the top 5.

**Flow:**
1. User fills `KCSEForm` (one grade dropdown per `clusters.Subject`, requires ≥7 filled subjects).
2. `kcse_calculator_view` (`clusterpoints/views.py`) branches on auth: **authenticated** users get `UserKCSEResult`/`SubjectResult` persisted, then `calculate_all_clusters()` runs inside `transaction.atomic()` and upserts `ClusterCalculationResult` per cluster via `update_or_create`; **guests** get an in-memory-only `calculate_clusters_anonymous()` result stashed in session and are redirected to register (guest session state is restored after signup).
3. Both functions iterate each cluster's `subject_groups` ordered by `priority`, picking the best not-yet-used subject per slot (never reusing a subject across slots), padding unfillable slots with 0, and forcing `weighted=0.0` if any *required* slot can't be filled.
4. Results render as an accordion UI with top-5 courses per cluster attached; a "Application Readiness" style payment gate (via `payments.services`) controls when eligible-course details unlock.
5. PDF export (`export_cluster_pdf`, `export_full_results_pdf`) via ReportLab.
6. A submission-lock mechanism (`career.models.SubmissionLockConfig`/`CareerSubmission`, keyed on `CareerSubmission.FEATURE_CALCULATOR`) prevents recalculation abuse after payment; `recalculate_view` deletes the lock row to reset it.

**State:** Complete, canonical, actively used.

**Flagged issues:**
- **`clusterpoints/models.py::ClusterCalculationResult.calculate_cluster_points()`** contains a **different, deprecated formula** (`weighted = 48 * sqrt((raw_core_total / 48) * (aggregate_total / 84))` — the old fraction-based approach CLAUDE.md explicitly forbids reverting to). It appears to be dead code — the live call path (`clusterpoints/views.py` → `clusterpoints/services.py`) never calls this model method — but its presence is a latent-bug risk if anything (a shell script, a future refactor, a signal) ever calls it directly.
- **All 61 programme sub-clusters (numbers < 100) currently have zero `SubjectGroup` rows.** `seed_clusters.py` only seeds the 20 *master calculation clusters* (101–120); the sub-clusters used for course-matching/requirements display are managed separately and have not been populated with slots. Where the live calculator UI shows "top courses per cluster," this may be relying on a top-4-subjects fallback rather than true per-cluster subject-group logic — confirm against current behavior before assuming sub-cluster slots exist.
- **At least four independent reimplementations of the aggregate algorithm** exist across the codebase: `clusterpoints/models.py::UserKCSEResult.recalc_total_points()`, `clusterpoints/services.py` (both functions, shared logic), `clusterpoints/views.py::_compute_aggregate()`, and `career/models.py::_compute_aggregate()`. They are believed consistent today but are a maintenance risk — a future bugfix applied to only one of them would silently diverge.
- **`clusterpoints/forms.py`** lists Chemistry as "compulsory" for display (`COMPULSORY_SUBJECT_NAMES`) but does not actually enforce it as required (`REQUIRED_SUBJECT_NAMES` omits it) — intentional per an in-code comment (many students take Biology/Physics instead), but worth knowing the two lists diverge on purpose.
- **AI knowledge base is out of sync**: `career/management/commands/seed_knowledge.py` seeds an `AIKnowledgeEntry` that restates the cluster-points formula using the **old fraction-based version** (`sum of 4 cluster subject points ÷ 48`), not the midpoint-marks version actually implemented. The CareerNext AI chat could therefore explain the formula incorrectly if it surfaces that KB entry verbatim.
- Duplicated PDF branding/styling code exists independently in both `clusterpoints/views.py` and `career/views.py` (NAVY/TEAL/EMERALD/AMBER/PURPLE/SLATE palette, header/footer draw functions) rather than a shared module.

---

## 3. Course/Institution Eligibility Matching

**Purpose:** Determines which courses a student qualifies for, using two entirely different rulesets depending on pathway — cluster points for degrees, mean grade only for everything else.

**Files:**
- `clusterpoints/eligibility.py` — `get_eligible_courses()` (degree), `get_eligible_courses_by_mean_grade()` (non-degree), `_get_course_cutoff_data()` (cached cutoff lookup), `COURSE_TYPE_MAP`, `PATHWAY_DEFAULT_MIN_GRADE`, `GRADE_POINTS`, `NEARLY_ELIGIBLE_GAP`/`NEARLY_ELIGIBLE_GRADE_GAP`
- `clusterpoints/views.py::eligible_courses_view` — the UI entry point, branches on `career_pathway` session var, payment-gated
- `courses/models.py` — `Course.cutoff_points` (legacy/summary field, largely unused directly — see gap), `Course.minimum_mean_grade`, `Course.subject_requirements`, `CourseOffering.cutoff_points` (the authoritative per-institution cutoff JSON), `CourseOffering.latest_cutoff()`
- `predictor/services.py`, `predictor/views.py` — extends eligibility with a *predicted future* cutoff (see §12 Predictor)

**Flow (degree pathway):**
`get_eligible_courses(user, kcse_result)` builds a `cluster_map` keyed by `cluster.kuccps_number` from the user's `ClusterCalculationResult` rows, compares against `_get_course_cutoff_data()` (a 15-minute cached scan of `CourseOffering` rows with non-null cutoffs where `course__course_type__name__iexact='Degree'`), and classifies each course `eligible` (gap ≥ 0), `nearly` (0 < |gap| ≤ 5.0 points), or `not_eligible`.

**Flow (non-degree pathways — Diploma/Certificate/KMTC/TTC/Artisan/Short Course):**
`get_eligible_courses_by_mean_grade(pathway, mean_grade)` filters `CourseOffering` by `course__course_type__name__in=COURSE_TYPE_MAP[pathway]`, converts the mean grade to `GRADE_POINTS`, and compares against each course's `minimum_mean_grade` (falling back to `PATHWAY_DEFAULT_MIN_GRADE` if unset). **This function never reads `cutoff_points` or `subject_requirements`** — confirmed no cluster points and no subject-requirement checks are applied to non-degree pathways, per CLAUDE.md rule.

**State:** Complete for degree pathway; non-degree pathway works but its underlying cutoff/requirement *data* is incomplete (see gap below — this is a data gap, not a logic gap).

**Flagged issues:**
- **TVET/TTC cutoff points and subject requirements have not yet been sourced** for most courses (per FEATURE_STATUS.md and TODO.md) — the mean-grade-only logic is correct and complete, but many `Course.minimum_mean_grade`/`subject_requirements` rows are still blank, so eligibility results for those pathways may be less precise than for KMTC/Degree until that data entry work is done.
- **`Course.cutoff_points`** (on the parent `Course`, not `CourseOffering`) appears to be a legacy/summary field that nothing in the reviewed eligibility/predictor/trends code actually reads — the authoritative source is always `CourseOffering.cutoff_points` (per-institution). Worth confirming before removing.

---

## 4. Career Guidance Engine / CareerNext AI

**Purpose:** Multi-pathway course matching (Degree/Diploma/TVET/KMTC/TTC) plus an AI layer: chat assistant, quiz-based career matching, OCR grade-slip upload, and AI-generated insights/recommendations.

**Files:**
- `career/models.py` — legacy `Course`/`University`/`CourseCategory`/`TVETCourse`/`KMTCourse`/`TTCCourse` (the **older, separate course system** — see CLAUDE.md rule 5), `CareerProfile`, `QuizQuestion`/`QuizOption`/`QuizSubmission`/`QuizAnswer`, `CareerConfig` (singleton AI settings), `AIKnowledgeEntry`, `JobMarketData`, `AICallLog`, `AIChatCredit`, `SharedResult`, `SubmissionLockConfig`, `CareerSubmission`, plus module functions `match_degree_courses`, `match_diploma_courses`, `match_tvet_courses`, `match_kmtc_courses`, `match_ttc_courses`, `generate_ai_recommendation`, and a **duplicate** `career_guidance_engine()` (see gap)
- `career/engine.py` — **the live dispatcher** (`career_guidance_engine()`, confirmed not a stub), imported by `career/views.py`
- `career/views.py` (~4500 lines) — pathway views, AI chat/insight endpoints, quiz, PDF export, OCR upload, sharing
- `career/forms.py` — legacy per-pathway forms (likely superseded by `clusterpoints.forms.KCSEForm` for the degree flow)
- `career/job_market.py` — `get_jmd_for_course()`, in-memory keyword lookup over `JobMarketData`
- `career/tasks.py` — async AI-recommendation generation, snapshot saving, expired-share cleanup
- `career/urls.py` — 30 routes (`kcse-input/`, `degree/{calculate,upload,paste,manual}/`, `quiz/`, `chat/`, `ajax/ai-chat/`, `ajax/ai-insight/`, `results/`, `results/pdf/{quick,report}/`, `share/create/`, `share/<uuid:token>/`, etc.)
- `career/management/commands/` — `seed_careers.py`, `expand_careers.py` (career profiles + keyword-links to `courses.Course`), `seed_knowledge.py` (AI knowledge base), `seed_job_market.py`, `sync_career_clusters.py` (one-way bridge from `courses.Course.cluster` to `career.Course.cluster`)
- Templates: `templates/career/degree_options.html`, `degree_manual.html`, `degree_upload.html`, `degree_paste.html`, `quiz.html`, `quiz_results.html`, `chat.html`, `career_results_v2.html`, `shared_result.html`, `loading.html`, plus per-pathway step templates (`diploma_step.html`, `tvet_step.html`, `artisan_step.html`)

**Flow:**
1. **Pathway dispatch** — `career/engine.py::career_guidance_engine(kcse_grades, pathway, tvet_category=None, user=None)` dispatches by pathway string to the matching function in `career/models.py`, then calls `generate_ai_recommendation(matches, user=user)` and returns `(matches, ai_recommendation)`.
2. **Degree pathway** — `career/views.py::degree_calculate` delegates cluster-point math to `clusterpoints`-equivalent logic (via `clusterpoints.services._weighted_cp`, imported not reimplemented — good); `degree_manual` reuses `clusterpoints.forms.KCSEForm`; `degree_upload` runs OCR (see below); `degree_paste` accepts freeform pasted text.
3. **Non-degree pathways** — `match_diploma_courses`/`match_tvet_courses`/`match_kmtc_courses`/`match_ttc_courses` in `career/models.py` are mean-grade-based only (consistent with the eligibility rule above), matching against the **legacy** `TVETCourse`/`KMTCourse`/`TTCCourse` models — not `courses.models.Course`.
4. **AI chat (CareerNext AI)** — `ajax_ai_chat` builds a system prompt with DB-sourced context (`_build_ai_db_context`, pulling `AIKnowledgeEntry`/`JobMarketData`/`CareerProfile`), searches the knowledge base first, falls back to an OpenAI chat completion (`cfg.ai_model_name`, default configurable via `CareerConfig` singleton) if no KB hit. Rate/credit-gated via `_check_and_increment_ai_calls` (anonymous: daily cap via `AICallLog`; logged-in: `AIChatCredit` free-then-paid draw-down), master-switched by `CareerConfig.ai_enabled`.
5. **Quiz** — `quiz_view`/`quiz_results_view` score `QuizAnswer`s against `CareerProfile` tags; `_generate_quiz_ai_summary` makes an additional OpenAI call to narrate the fit.
6. **OCR grade upload** — `degree_upload` uses PyMuPDF (`fitz`) to rasterize PDF pages, then calls OpenAI's **Vision** API with a **hardcoded `model='gpt-4o'`** (not the configurable `cfg.ai_model_name`) to extract grades from an uploaded image/PDF.
7. **Sharing** — `share_result_create`/`shared_result_view` create/serve a `SharedResult` snapshot for public shareable links (no login required to view).
8. All AI call sites wrap OpenAI calls in broad try/except with graceful, always-succeeding fallback (never surfaces a raw API error to the user).

**State:** Fully implemented and live — `career/engine.py` is a real dispatcher, not a stub, per CLAUDE.md rule 4.

**Flagged issues:**
- **`generate_ai_recommendation()` in `career/models.py`** (the non-chat, results-page recommendation text) **still returns placeholder text** — confirmed by API_NOTES.md as a known-stubbed item, planned to become a real short (300-token) cached call.
- **Duplicate dispatcher**: `career/models.py` defines its own `career_guidance_engine()` function with the same name/purpose as `career/engine.py`'s — `career/views.py` imports the `engine.py` version, so the `models.py` copy appears unused, but its existence is a maintenance/confusion risk.
- **AI SDK is exclusively OpenAI** (`from openai import OpenAI`) across all 5 AI call sites in `career/views.py`, despite CLAUDE.md stating the engine "uses `OPENAI_API_KEY` or `ANTHROPIC_API_KEY`" — no Anthropic client was found in the reviewed code; `kuccpss/settings.py` only defines `OPENAI_API_KEY`, no `ANTHROPIC_API_KEY` constant.
- **Two unmerged course systems**: `career/models.py`'s legacy `Course`/`TVETCourse`/`KMTCourse`/`TTCCourse` vs. `courses/models.py`'s unified `Course`. Bridged one-way by `career/management/commands/sync_career_clusters.py` (dry-run by default, `--apply` to write; matches by case-insensitive stripped name; copies `cluster` FK from `courses.Course` → `career.Course` only for `category__name='Degree'` rows). Do not conflate the two without explicit instruction, per CLAUDE.md rule 5.
- OCR's hardcoded `gpt-4o` (vs. the configurable model elsewhere) is inconsistent with the rest of the AI configuration surface.

---

## 5. Course & Institution Directories

**Purpose:** Public browsing of courses and institutions (universities, KMTC, TVET, TTC), reviews, shortlisting (max 5, KUCCPS choice-order ranking), and side-by-side comparison.

**Files:**
- `courses/models.py` — `CourseType`, `CourseCategory`, `Course`, `CourseOffering` (through-model, per-institution cutoffs), `Review`, `CourseSpotlight`
- `courses/views.py` — `course_types_list`, `course_type_detail`, `course_category_detail`, `course_detail`, `submit_course_review`
- `courses/trends.py` — `get_trends_context()` (most-viewed/most-competitive/most-offered/top-rated, 1-hour cached)
- `courses/urls.py` — type → category → course slug hierarchy, HTMX-partial-aware
- `institutions/models.py` — `InstitutionType`, `Institution`, `InstitutionPromotion` (paid featured/scholarship/spotlight tiers)
- `institutions/views.py` — `institution_types_list`, `institution_type_detail`, `institution_detail`, `submit_institution_review`
- `accounts/models.py` — `SavedCourse`, `CourseShortlist` (max 5/user, enforced in the view not the DB; `rank` field 1-4 for KUCCPS choice order)
- `accounts/views.py` — `saved_courses_view`, `toggle_save_course`, `shortlist_view`, `shortlist_toggle`, `shortlist_update_notes`, `shortlist_set_rank`, `export_shortlist_pdf`, `course_comparison_view`
- Templates: `templates/courses/course_detail.html` (Chart.js cutoff trend, JSON-LD schema, branches by course type), `course_types_list.html`, `_course_items_partial.html`; `templates/institutions/institution_detail.html`, `institution_types_list.html`; `templates/accounts/shortlist.html`, `saved_courses.html`, `comparison.html`; `templates/partials/reviews_section.html` (shared by both course and institution detail pages via `target_type`)

**Flow:**
1. Users browse `course_types_list` → `course_type_detail`/`course_category_detail` → `course_detail`, with HTMX-driven search/pagination partials.
2. `course_detail` builds a Chart.js dataset (top 6 institutions by latest cutoff + an average line) from `CourseOffering.cutoff_points`, shows job-market data (`career.job_market.get_jmd_for_course`), and reviews.
3. Reviews: `submit_course_review`/`submit_institution_review` (`@login_required`) validate rating 1-5, truncate body to 280 chars, `update_or_create` a `Review` scoped to (user, course) or (user, institution) via conditional `UniqueConstraint`s.
4. Shortlist: `shortlist_toggle` (AJAX, capped at 5), `shortlist_set_rank` (1-4, mutually exclusive per rank per user), `shortlist_view` annotates each item with eligibility status (`eligible`/`nearly`/`not_eligible`) and competition level.
5. Comparison: `course_comparison_view` renders a full side-by-side table for all shortlisted courses.
6. Institution promotions (`InstitutionPromotion`) surface in listing pages as sponsored-first ordering (DB-level `Case/When`, not Python sort) and in career results for the `course_spotlight`/`scholarship` tiers.

**State:** Complete and in active use.

**Flagged issues:**
- **`courses/forms.py`** (`CourseTypeForm`, `CourseCategoryForm`, `CourseForm`) and **`institutions/forms.py`** (`InstitutionTypeForm`, `InstitutionForm`) are defined but not referenced by any view — likely dead code from a planned front-end CRUD UI now superseded by Django admin + `django-import-export`.
- **`courses/urls.py`** has a harmless duplicate `from django.urls import path` import line.
- `institutions/tests.py` is effectively empty (3 lines); `courses/tests.py` covers only smoke/review flows, not `course_detail`'s chart logic, category-fallback redirects, or `trends.py`.

---

## 6. Payments (IntaSend M-Pesa, feature gating)

**Purpose:** Paywall for premium features (career report, AI chat top-ups, eligible-course details, advanced analysis) via M-Pesa STK push, plus staff-grantable exemptions. **Important:** this project integrates M-Pesa through **IntaSend** (a payment aggregator), not Safaricom's Daraja API directly.

**Files:**
- `payments/models.py` — `PaymentFeature` (admin-configurable price/toggle), `Payment`, `PaymentExemption`, `Transaction`; `PRODUCT_CHOICES`, `FEATURE_TO_PRODUCT`, `AFFILIATE_EXCLUDED_FEATURES`
- `payments/services.py` — `initiate_stk_push()`, `fetch_intasend_status()`, `send_mentor_payout()`/`send_affiliate_payout()` (B2C), `normalise_phone()`, `has_paid_for_feature()`, `has_paid_for_current_session()`, `lock_submission_on_payment()`, `price_for_feature()`/`is_feature_enabled()`
- `payments/views.py` — `payment_required`, `payment_history`, `initiate_payment`, `mpesa_webhook` (HMAC-signature-verified), `payment_status`, `verify_payment`, `verify_by_transaction_code`, `pending_payment_for_feature`, `_generate_receipt_pdf`, `_send_payment_receipt`
- `payments/tasks.py` — `check_pending_payments()` (stale >30min → failed), `send_payment_confirmation()`, `top_up_ai_credits_after_payment()`
- `payments/urls.py` — `required/`, `history/`, `initiate/`, `webhook/mpesa/`, `status/<id>/`, `verify/<id>/`, `pending/`, `verify-code/`
- `payments/management/commands/seed_payment_features.py`, migrations `0004_seed_payment_features.py`, `0008_seed_ai_chat_access_feature.py`
- Templates: `templates/payments/payment_required.html` (full-page unlock, phone→waiting→success/failed/timeout state machine, polls every 3s for 2 min), `paywall_overlay.html` (blurred-content overlay variant, separate JS namespace), `payment_history.html`

**Flow:**
1. A gated view checks `payments.services.has_paid_for_feature(user, feature)` (staff always exempt; then `PaymentExemption`; then a completed `Payment` row).
2. `initiate_payment` creates a `Payment` and calls `initiate_stk_push()` → IntaSend `POST /payment/mpesa-stk-push/`, returns an `invoice_id` stored as `checkout_id`.
3. The frontend polls `payment_status`/`verify_payment` while waiting for the IntaSend webhook (`mpesa_webhook`) to arrive and flip `Payment.status` to `completed`.
4. On completion: grants AI credits if applicable, calls `lock_submission_on_payment` (locks the `CareerSubmission` so a paid calculation can't be silently recalculated), emails a branded PDF receipt, and — unless the feature is in `AFFILIATE_EXCLUDED_FEATURES` (`mentorship_booking`, `ai_chat_access`) — computes and credits affiliate commission for the referrer.
5. Manual fallback: `verify_by_transaction_code` lets a user paste their M-Pesa SMS code, matched against `Transaction.mpesa_ref`.

**State:** Complete, live in production (per DEPLOY.md), IntaSend keys configured.

**Flagged issues:**
- **`verify_payment` and `verify_by_transaction_code` (both fallback paths) do not run the affiliate-commission logic** that `mpesa_webhook` runs — payments confirmed via these fallback paths never earn affiliate commissions, only webhook-confirmed ones do. This is a real behavioral inconsistency.
- **Two independent webhook code paths can confirm a mentorship-linked `Payment`**: `payments.views.mpesa_webhook` (HMAC-verified) contains an inline, duplicated copy of the mentorship-session-confirmation logic rather than calling the shared `mentorship.views._confirm_session_after_payment` helper — see §7 Mentorship for the full detail.
- Production hard-fails (`RuntimeError`) at startup if `INTASEND_WEBHOOK_SECRET` is unset or `SECRET_KEY` is left at its insecure default — intentional safety guard, not a bug.
- `payments/tests.py` is an empty stub — no test coverage.
- `payments/tasks.py::send_payment_confirmation` (plain-text email) appears to be an older/alternate mechanism superseded by the HTML+PDF receipt in `views.py::_send_payment_receipt`.
- Minor migration/command inconsistency: `0004_seed_payment_features.py` seeds `advanced_analysis` as `enabled=True`, while the standalone `seed_payment_features` management command's default is `disabled` — re-running the command with `--force` would change production behavior for that feature.

---

## 7. Mentorship Marketplace

**Purpose:** Peer-mentor directory (current/former students by course+institution), paid 15-minute booking sessions (KES 100 default, 70/30 payout split), session lifecycle management, and mentor payout withdrawals.

**Files:**
- `mentorship/models.py` — `MentorProfile`, `TimeSlot`, `MentorshipSession`, `WithdrawalRequest`, `MentorshipConfig` (singleton: `session_price`, `mentor_payout`, `mentor_signup_enabled`)
- `mentorship/views.py` — `directory`, `mentor_profile`, `become_mentor`, `mentor_dashboard`, `add_slots`/`add_weekly_slots`, `book_session`, `checkout`, `initiate_payment`, `verify_payment_manual`, `payment_webhook` (**unsigned**, mentorship-specific), `session_detail`, `rate_session`, `cancel_session`, `download_ics`, `request_withdrawal`, `_confirm_session_after_payment`, `_maybe_auto_pay_mentor`
- `mentorship/forms.py` — `MentorRegistrationForm`, `BookingForm`, `AddSlotsForm`/`AddWeekSlotsForm`, `WithdrawalForm`, `RatingForm`, `CancelSessionForm`
- `mentorship/calendar_utils.py` — `google_calendar_url()`, `generate_ics()` (hand-built iCal, no external calendar API)
- `mentorship/admin.py` — approval workflow (reject button, bulk approve/reject/deactivate actions), `confirm_manual_payment` action
- `mentorship/management/commands/mentorship_housekeeping.py` — cron job: session reminders (60–120 min window) + auto-complete sessions >30 min past their slot
- `mentorship/urls.py` — directory, become-mentor, dashboard/slots, booking/checkout/webhook, session lifecycle, withdrawal routes
- `resources/migrations/0010_seed_withdrawal_settings.py` (**currently untracked in git**) — seeds `mentor_min_withdrawal` (100) and `affiliate_min_withdrawal` (500) as admin-editable `SiteSetting` rows
- Templates: `templates/mentorship/directory.html`, `mentor_profile.html`, `become_mentor.html`, `mentor_dashboard.html`, `book_session.html`, `checkout.html`, `session_detail.html`, `my_sessions.html`

**Flow:**
1. **Become a mentor** — `become_mentor` (`@login_required`, gated by `MentorshipConfig.mentor_signup_enabled`) collects course/institution/bio/WhatsApp/verification docs (student ID + portal screenshot) via `MentorRegistrationForm`; institution queryset restricted to hardcoded `institution_type_id`s 2/3/4 (see gap); admin reviews and approves/rejects via `mentorship/admin.py`.
2. **Booking** — `book_session` prevents self-booking, race-checks slot availability, creates a `pending_payment` `MentorshipSession`, redirects to `checkout`.
3. **Payment** — `initiate_payment` creates/updates a `payments.Payment` (`feature="mentorship_booking"`) keyed by the session's UUID `token` as IntaSend's `api_ref`; on webhook confirmation, `_confirm_session_after_payment` sets `confirmed`, credits `mentor.wallet_balance`, sends confirmation emails+ICS+in-app notification+push, and calls `_maybe_auto_pay_mentor`.
4. **Manual verification fallback** — `verify_payment_manual` calls `fetch_intasend_status` directly if the webhook is late/missing; else emails admin for manual review.
5. **Session lifecycle** — `complete_session` (mentor marks done), `rate_session` (mentee, one-time), `cancel_session` (frees slot, debits wallet if already credited, sends refund-required email to admin — refund itself is manual, no automated M-Pesa reversal).
6. **Auto-completion & reminders** — `mentorship_housekeeping` management command (intended for a scheduled cron).
7. **Withdrawals** — `request_withdrawal` (`@require_recent_auth`) validates against `_mentor_min_withdrawal()` (reads the `mentor_min_withdrawal` `SiteSetting`), calls `payments.services.send_mentor_payout()` (IntaSend B2C "Send Money"), synchronously marks the `WithdrawalRequest` processed/failed. `_maybe_auto_pay_mentor` also auto-triggers a full-balance payout once wallet balance crosses `MENTOR_AUTO_PAY_THRESHOLD` (default 500).

**State:** Complete and live. Auto-payout depends on IntaSend's B2C "Send Money" feature being manually activated on the IntaSend account (per TODO.md — unclear if done for production).

**Flagged issues:**
- **Duplicate/parallel payment-confirmation logic**: `mentorship.views.payment_webhook` (no signature verification) and `payments.views.mpesa_webhook` (HMAC-verified) can *both* independently confirm the same `MentorshipSession`. The payments-app webhook reimplements the confirmation logic inline instead of calling `mentorship.views._confirm_session_after_payment`, and critically **does not call `_maybe_auto_pay_mentor`** — so whether a mentor gets auto-paid depends on which webhook IntaSend happens to hit.
- **`WithdrawalRequest.status = "failed"` is set in code but is not one of `STATUS_CHOICES`** (`pending`/`processed`/`rejected` only). It saves without error (Django doesn't enforce choices at the DB layer) but breaks `get_status_display()` and any choices-based admin filter.
- **`MentorshipSession.meet_link`** (added in migration `0007`) is a dead column — never written or read anywhere in `views.py` or `calendar_utils.py`. All meeting coordination happens via WhatsApp-coordination text baked into emails/ICS, plus a Google-Calendar "add event" link. Despite this, the model docstring references a "Jitsi room" that doesn't exist in code.
- **`MentorRegistrationForm.__init__`** hardcodes `institution_type_id__in=[2,3,4]` — fragile if `InstitutionType` seed IDs ever change.
- **`MENTOR_AUTO_PAY_THRESHOLD`** is read via `getattr(settings, ..., 500)` but is not actually defined anywhere in `kuccpss/settings.py` — always uses the 500 default.
- **`resources/migrations/0010_seed_withdrawal_settings.py` is currently untracked in git** (confirmed via `git status` at the start of this session) — functionally harmless if unmigrated (the code fallback defaults match the seeded values exactly), but should be committed before deploy so the settings become admin-editable in production.
- No automated cron currently processes `WithdrawalRequest` rows beyond the synchronous request-time call and the inline auto-pay trigger — `mentorship_housekeeping` only handles reminders/completion, not withdrawals.

---

## 8. Affiliate/Referral System

**Purpose:** Lets any user generate a referral code/link; when a referred user makes a payment, the referrer earns a commission (default 20%) into a wallet, withdrawable via M-Pesa.

**Files:**
- `accounts/models.py` — `Referral` (code, `attribute_from_session()`, `get_or_create_for_user()`), `AffiliateProfile` (commission_rate, wallet_balance, total_earned), `AffiliateCommission` (one per referred payment, O2O to `payments.Payment`), `AffiliateWithdrawalRequest`
- `accounts/views.py` — `referral_view`, `affiliate_dashboard`, `request_affiliate_payout`, `_build_affiliate_withdrawal_form`, `_mask` (hides referred users' PII in the dashboard)
- `accounts/forms.py` — `AffiliateWithdrawalForm` (`_affiliate_min_withdrawal()` reads `SiteSetting['affiliate_min_withdrawal']`)
- `kuccpss/middleware.py` — `ReferralMiddleware` (captures `?ref=CODE` into session, cache-validated)
- `payments/views.py::mpesa_webhook` — computes and credits `AffiliateCommission` on payment completion (excluding `mentorship_booking`/`ai_chat_access`)
- `accounts/admin.py` — `activate_as_affiliate` bulk action, `AffiliateCommissionAdmin.mark_paid_out`
- `analytics/views.py::affiliate_analytics` — staff dashboard
- Templates: `templates/accounts/referral.html`, `affiliate_dashboard.html` (recently modified — see git status)

**Flow:**
1. Any user can request an affiliate code (`Referral.get_or_create_for_user`); sharing a link with `?ref=CODE` stores the code in the visitor's session via `ReferralMiddleware`.
2. On signup, `accounts/signals.py::on_user_signed_up` calls `Referral.attribute_from_session` to mark the referral converted and link the new user.
3. On the referred user's first completed payment (any feature except `mentorship_booking`/`ai_chat_access`), `payments.views.mpesa_webhook` computes `commission_amount = rate% × payment.amount`, creates an `AffiliateCommission` (idempotent — checked via `.exists()`), and atomically increments the affiliate's `wallet_balance`/`total_earned`.
4. Affiliates request payout via `request_affiliate_payout` (`@require_recent_auth`), bounded by `_affiliate_min_withdrawal()` (currently 500 KES via the pending `SiteSetting` migration), paid out via `payments.services.send_affiliate_payout()` (IntaSend B2C).

**State:** Complete; recently touched (uncommitted changes to `accounts/forms.py`, `accounts/views.py`, `affiliate_dashboard.html` per git status — appears to be adding the configurable minimum-withdrawal feature described in §7).

**Flagged issues:**
- Shares the same fallback-path gap as payments generally: commissions are only awarded via the `mpesa_webhook` path, not via `verify_payment`/`verify_by_transaction_code` fallbacks.
- Depends on the same untracked `resources/migrations/0010_seed_withdrawal_settings.py` as mentorship withdrawals (see §7) for the admin-editable minimum.
- Depends on IntaSend B2C "Send Money" being activated for payouts to actually succeed (same caveat as mentor payouts).

---

## 9. Analytics & Staff Dashboards

**Purpose:** Comprehensive, fail-silent server-side event logging plus ~16 staff-only dashboards covering users, content, revenue, growth, and operations.

**Files:**
- `analytics/models.py` — `PageViewLog`, `UserActionLog`, `SessionLog`, `SearchLog`, `ViewLog`, `DownloadLog`, `EventLog`, `PWAInstallLog`, `CareerEngineLog`
- `analytics/utils.py` — synchronous logging helpers actually called from views (`log_search`, `log_view`, `log_download`, `log_career_engine`, `log_event`, `log_action`, `track_posthog`) — all fail-silent
- `analytics/tasks.py` — Django-Q async variants (`log_event`, `log_search`, `purge_old_logs`) — appears to duplicate `utils.py` (see gap)
- `analytics/signals.py` — auto-logs on user creation, payment save, login/logout, shortlist add/remove
- `analytics/geo.py` — MaxMind GeoLite2 wrapper (`get_location(ip)`, fails soft if DB/package missing)
- `kuccpss/middleware.py::PageTrackingMiddleware` — the core writer, creates a `PageViewLog` + upserts `SessionLog` on every non-static request
- `analytics/views.py` (~1600 lines) — `analytics_dashboard`, `export_csv`, `mentor_analytics`, `affiliate_analytics`, `pages_analytics`, `actions_analytics`, `user_timeline`, `insights_dashboard`, `payments_overview`, `live_feed_json`, `calculator_analytics`, `career_engine_analytics`, `conversion_analytics`, `retention_analytics`, `ai_chat_analytics`; all gated by `staff_only = user_passes_test(...)`
- `analytics/urls.py` — 16 routes under `/analytics/`
- `analytics/context_processors.py` — `posthog_keys`, `sentry_context`, `ga_context`, `data_version` (injected into every template)
- Templates: `templates/analytics/*.html` (extend `base_analytics.html`, sidebar shell with Overview/Behaviour/Growth/Revenue/Community sections), `templates/admin/analytics/overview.html`, `templates/admin/base_site.html` (custom admin nav bar + GA/Sentry/PostHog script injection)

**Flow:**
1. Every request is logged by `PageTrackingMiddleware` (device sniffing, response time, referrer, geo on first hit per session) — wrapped in a blanket try/except so tracking never breaks the response.
2. Explicit events (`calculator_run`, `ai_chat`, `quiz_complete`, shortlist add/remove, etc.) are logged via `analytics/utils.py` calls scattered through `clusterpoints`, `career`, `courses`, `accounts` views.
3. Staff dashboards aggregate these logs with heavy ORM annotation (KPIs, trend %, time-series, funnels, cohort retention, peak-hours heatmap).
4. `calculator_analytics` explicitly cross-checks its pathway-recommendation buckets against `clusterpoints/views.py::_pathway_recommendation`'s thresholds (documented in an inline comment as a required-to-stay-in-sync pair).
5. External service integration (PostHog, Sentry, GA4) is entirely optional/env-gated — dashboards show "configured/not configured" flags rather than hard-requiring any of them.

**State:** Complete, comprehensive, actively used by staff.

**Flagged issues:**
- **`analytics/tasks.py`** (Django-Q async logging) largely duplicates `analytics/utils.py` (synchronous) — the sync versions are what's actually called from views; the async task versions' purpose/usage is unclear (possibly unused, possibly reserved for future load reduction).
- **`analytics.tasks.purge_old_logs`** has no visible scheduler wiring in the reviewed code — no management command or cron entry calls it, so old logs may be accumulating unbounded.
- Heavy reliance on `EventLog` freeform `name`/`properties` for cross-cutting analytics (e.g., `calculator_run`, `ai_chat_message`, `ai_chat_paywall_hit`) means those event names are a de facto contract between multiple view files and `analytics/views.py` — no shared constants module enforces them; a typo in an event name would silently break a dashboard metric.

---

## 10. Notifications (in-app + push)

**Purpose:** In-app notification center plus Web Push (VAPID) for booking confirmations, admin broadcasts, and reminders.

**Files:**
- `accounts/models.py` — `Notification` (message, notif_type, is_read, link, published_by), `PushSubscription` (endpoint/p256dh/auth)
- `accounts/views.py` — `notifications_view` (marks all unread as read on open), `mark_notification_read` (both invalidate the `notif_unread:<uid>` cache key), `broadcast_notification_view` (staff-only bulk create + push), `push_subscribe`, `_send_push_to_all`/`_send_push_to_user` (use `pywebpush`, VAPID keys from settings, prune dead subscriptions on failure)
- `accounts/context_processors.py::unread_notifications` — cache-backed (60s TTL) unread count injected into every template, also injects `VAPID_PUBLIC_KEY`
- `static/js/main.js` — client-side push subscription IIFE (`doSubscribe()`, requests permission after a 12s delay, posts to `/accounts/push/subscribe/`)
- `static/js/sw.js` — service worker `push`/`notificationclick` handlers
- Templates: `templates/accounts/notifications.html`, `templates/accounts/broadcast_notification.html`
- Cross-app callers: `mentorship/views.py` (booking confirmations/reminders via `accounts.views._send_push_to_user`), `resources` (deadline banners are separate — see §13)

**Flow:**
1. In-app: any code path can `Notification.objects.create(user=..., message=..., notif_type=...)`; the navbar badge (via the context processor) and `notifications_view` surface them.
2. Push: client subscribes via `main.js`'s `doSubscribe()` → `push_subscribe` view stores a `PushSubscription`; server sends via `pywebpush.webpush()` with VAPID auth; `sw.js` renders the notification and handles clicks (focuses existing tab or opens a new one).
3. Staff broadcast: `broadcast_notification_view` bulk-creates `Notification` rows for all active users and pushes to all subscriptions (`_send_push_to_all`).
4. Mentorship booking confirmations/cancellations/reminders send both an in-app `Notification` and a push notification, best-effort (swallowed on exception).

**State:** Complete.

**Flagged issues:** None specific beyond the general fail-silent pattern (a broken push subscription is pruned automatically on send failure, which is correct behavior, not a bug).

---

## 11. PDF Export

**Purpose:** Branded PDF generation (ReportLab, no external service) for cluster results, shortlists, career results, and payment receipts.

**Files:**
- `clusterpoints/views.py` — `export_cluster_pdf` (quick, 2-column cluster grid), `export_full_results_pdf` (comprehensive: profile + all clusters + eligible/nearly courses + next-steps plan)
- `career/views.py` — `career_results_pdf_quick`, `career_results_pdf_detailed`
- `accounts/views.py` — `export_shortlist_pdf`
- `payments/views.py` — `_generate_receipt_pdf` (payment receipt, attached to `_send_payment_receipt` emails)
- Third-party: `reportlab` (see `requirements.txt`)

**Flow:** Each export function builds a `reportlab.pdfgen.canvas.Canvas` (or platypus flowables) by hand — custom header/footer draw callbacks, a shared NAVY/TEAL/EMERALD/AMBER/PURPLE/SLATE color palette, and per-document content blocks — then returns it as an `HttpResponse` with `Content-Type: application/pdf` (or attaches bytes to an email for the receipt case).

**State:** Complete for cluster results, shortlist, career results (quick+detailed), and payment receipts.

**Flagged issues:**
- **No shared PDF-styling module.** The branded palette and header/footer drawing logic is copy-pasted independently across `clusterpoints/views.py`, `career/views.py`, and `payments/views.py` — a rebrand or layout tweak requires editing 3+ places consistently.
- FEATURE_STATUS.md/TODO.md note the "full-results PDF (all clusters)" as a P1 item — confirm current completeness of `export_full_results_pdf` against that goal before assuming full parity.

---

## 12. Predictor (Cutoff Trend Prediction)

**Purpose:** Predicts next-cycle KUCCPS cutoff points per course/institution from historical `CourseOffering.cutoff_points`, and labels a student's admission likelihood against their calculated cluster score.

**Files:**
- `predictor/models.py` — `PredictionConfig` (singleton, admin-tunable: `rising_floor_multiplier`, `rising_floor_cap`, `stable_floor_offset`, `band_multiplier`)
- `predictor/services.py` — `predict_cutoff()` (70% WMA + 30% naive latest-year blend with a rising-trend floor adjustment; backtested MAE 1.581 vs alternatives per the module docstring), `eligibility()` (4-tier: High Likelihood/Likely/Borderline/Unlikely), `predict_offerings_for_calc_cluster()`, `predict_all_for_student()`; cluster-numbering bridge tables (`COURSE_TO_KUCCPS`, `CALC_TO_COURSE`, `COURSE_TO_CALC`, `KUCCPS_NAMES`) between the calculator's 101–120 numbering and course sub-group 5–65 numbering
- `predictor/views.py` — `predictor_index` (single page: search/filter by cluster/type/status, paginated 30/page), `_cluster_scores_from_request` (works for both authenticated and guest users, guest path reuses `clusterpoints.services.calculate_clusters_anonymous`)
- `predictor/urls.py` — single route, `predictor:index`
- `predictor/admin.py` — singleton-pattern admin (redirects list view straight to the one config row's change form)
- Templates: `templates/predictor/index.html`

**Flow:** For each course offering with ≥1 year of historical cutoff data, `predict_cutoff()` computes a weighted-moving-average blended prediction with a confidence band (`low`/`high`), classifies trend (rising/stable/falling), and — if the requesting student has a cluster score for that course's KUCCPS cluster — labels their eligibility likelihood against the predicted band. The single-page view supports search, cluster/type filters, and an eligibility-status filter, with per-status totals always shown regardless of active filter.

**State:** Complete; no `tests.py` in this app.

**Flagged issues:**
- No test coverage.
- The dual cluster-numbering scheme (calculator 101–120 vs course sub-groups 5–65) is a genuine domain complexity — any change to `clusters/management/commands/seed_clusters.py`'s cluster numbers must be mirrored in `predictor/services.py`'s static mapping tables, or predictions will silently target the wrong clusters.

---

## 13. Resources (Articles, FAQs, Success Stories, Deadline Banners)

**Purpose:** Editorial/content layer — downloadable guides, blog-style articles, FAQs, testimonials, site-wide settings, and a countdown-style deadline banner for the KUCCPS application window.

**Files:**
- `resources/models.py` — `SiteSetting` (generic key/value config, used pervasively across the codebase — see below), `FAQItem`, `SuccessStory`, `ResourceCategory`, `Resource`, `Article`, `Announcement`, `DeadlineBanner` (two configurable deadline dates + separate CTA links for authenticated vs. guest users), `SiteFeedback`
- `resources/views.py` — `resource_list`, `resource_detail`, `article_list`, `article_detail` (related-articles via shared tags), `kuccps_calendar`, `how_to_guides`, `submit_feedback`
- `resources/context_processors.py::deadline_banner` — cache-backed (120s), the only context processor in this app, injects `deadline_banner` into every page
- `resources/management/commands/seed_content.py` — seeds FAQ/success-story/base `SiteSetting` data
- `resources/urls.py` — `''`, `articles/`, `articles/<slug>/`, `kuccps-calendar/`, `how-to-guides/`, `feedback/submit/`, `<slug:slug>/` (catch-all, must stay last)
- Migrations of note: `0004_seed_admin_email_setting.py` (`admin_email` used by `mentorship._admin_email()`), `0007_seed_performance_settings.py` (`courses_per_page`, `mentors_per_page`, `trends_cache_ttl`), `0009_seed_deadline_banner.py` (KUCCPS 2026: portal opens 3 Jul 2026, closes 21 Aug 2026), `0010_seed_withdrawal_settings.py` (**untracked**, see §7/§8)
- Templates: `templates/resources/article_list.html`, `article_detail.html`, `resource_list.html`, `calendar.html`, `guides.html`
- Also: ~40 one-off PDF-extraction/ETL scripts living directly in `resources/` (not `management/commands/`) — developer tooling used once to seed `courses`/`institutions` data from official KUCCPS PDFs, not part of runtime

**Flow:** `SiteSetting.get(key, default)` is the universal admin-tunable-value pattern used throughout the app (pagination sizes, cache TTLs, contact info, minimum withdrawal amounts, admin email) — avoiding new migrations for every tunable. `deadline_banner` context processor surfaces the active `DeadlineBanner` site-wide (used on the homepage and in the base template's countdown bar). Articles/resources support HTMX-partial search+pagination like courses/institutions.

**State:** Complete.

**Flagged issues:**
- The large family of one-off ETL scripts directly under `resources/` (not in `management/commands/`) are historical/development artifacts, safe to ignore for runtime understanding but worth knowing they exist if auditing repo hygiene.
- `resources/migrations/0010_seed_withdrawal_settings.py` is untracked in git as of this writing — see §7 for the full implication.

---

## 14. PWA (Install, Offline, Service Worker, Push)

**Purpose:** Installable, offline-tolerant Progressive Web App shell around the Django server-rendered site.

**Files:**
- `static/manifest.json` — name/icons/`start_url: /dashboard/`/`display: standalone`/shortcuts (Calculator, Career Quiz)
- `static/js/sw.js` — service worker: `CACHE = 'careernext-v7'`, `OFFLINE_URL = '/offline/'`; cache-first-with-revalidation for `/static/`; network-only-with-one-retry-then-cached-offline-page for navigations; push/notificationclick handlers (shared with §10 Notifications)
- `static/js/main.js` — PWA install-prompt IIFE (`beforeinstallprompt`/`appinstalled` handlers, iOS manual-install modal since iOS doesn't fire the event, escalating dismiss cooldown 7d→4d via localStorage), install tracking
- `kuccpss/urls.py::serve_sw` — serves `sw.js` with `Service-Worker-Allowed: /` header so it can control the whole origin despite living under `/static/`
- `templates/offline.html` — standalone (no `base.html` inheritance) offline fallback page, auto-reloads on the browser's `online` event
- `templates/base.html` — PWA splash screen (first standalone-mode open only), install banner, iOS install instructions modal, service worker registration script
- `analytics/models.py::PWAInstallLog` + `analytics/views.py::pwa_install` (`@csrf_exempt`) — server-side install tracking endpoint

**Flow:** On first visit in a supporting browser, `main.js` listens for `beforeinstallprompt`, shows a custom install banner (respecting a dismiss cooldown), and on acceptance calls `trackInstall(platform)` → POSTs to `/analytics/pwa-install/`. The service worker (registered from `base.html`) precaches the offline page at install time and serves it if a navigation request fails while offline. Push notification handling (`push`/`notificationclick` in `sw.js`) is shared infrastructure with the Notifications feature (§10).

**State:** Complete.

**Flagged issues:** None identified beyond the general note that `sw.js`'s cache version (`careernext-v7`) must be bumped manually on any static-asset-affecting deploy to force cache invalidation — there's no automated cache-busting tied to the build process in the reviewed files.

---

## Cross-Cutting Notes (apply to multiple features above)

- **Two unmerged course systems** (`career/models.py` legacy vs. `courses/models.py` unified) recur across §4, §5, §6 — always check which system a given view/model is using before assuming Course means the same thing everywhere. See [CLAUDE.md](../CLAUDE.md) rule 5 and `career/management/commands/sync_career_clusters.py` for the one-way bridge.
- **`SiteSetting` (resources app)** is the de facto site configuration mechanism, referenced by name across accounts, mentorship, courses, career — a typo'd key silently falls back to the hardcoded Python default rather than erroring, which is safe but can mask a broken admin edit.
- **Fail-silent design is pervasive**: analytics logging, email sending (in several paths), push notifications, and PDF receipt generation are all wrapped in broad try/except that never surfaces errors to the end user. This is a deliberate UX choice but means silent failures require log/Sentry monitoring to catch, not user reports.
- **Multiple duplicated webhook/confirmation code paths** (payments↔mentorship, as detailed in §6/§7) are the single most concrete "needs a refactor" finding across this catalog — any bugfix to mentorship session confirmation must currently be applied in two places.

---

*Generated from a full-codebase research pass (accounts, analytics, career, clusterpoints, clusters, courses, institutions, predictor, mentorship, payments, resources, templates, static, and root docs). Cross-reference [docs/DATABASE.md](DATABASE.md) for the full schema, [docs/URL_MAP.md](URL_MAP.md) for every route, and [docs/TEMPLATE_MAP.md](TEMPLATE_MAP.md) for the full template inventory.*
