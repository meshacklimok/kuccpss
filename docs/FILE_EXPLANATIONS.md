# FILE_EXPLANATIONS.md

Per-file reference for every significant Python module in the KUCCPSS Django project. Organized by app. For URL routing tables see [URL_MAP.md](URL_MAP.md); for schema/ERD detail see [DATABASE.md](DATABASE.md).

> **Canonical rules (do not contradict elsewhere in this doc):**
> - The cluster-points formula is `cluster_points = 48 × sqrt((core_midpoint_marks/400) × (aggregate_total/84))`, using `GRADE_MIDPOINT_MARKS`, capped at 48. The **only** canonical, live implementation is `clusterpoints/services.py::_weighted_cp`. `clusterpoints/models.py::ClusterCalculationResult.calculate_cluster_points` implements a **different, older, dead** fraction-based formula (`core_pts/48` instead of midpoint-marks/400) and is not called anywhere in the live request path.
> - The KCSE aggregate (max 84) = Mathematics + best(English, Kiswahili) + next 5 best subjects (non-chosen language returns to the pool). This algorithm is **independently duplicated in at least 4 places**: `career/models.py::_compute_aggregate`, `clusterpoints/models.py::UserKCSEResult.recalc_total_points`, `clusterpoints/services.py` (inline in `calculate_clusters_anonymous`/`calculate_all_clusters`), `clusterpoints/views.py::_compute_aggregate`.
> - `accounts.User` is a **custom** UUID-pk, email-login user model (`AbstractBaseUser` + `PermissionsMixin`) — never Django's default `auth.User`.
> - `career/engine.py` is **not a stub** — `career_guidance_engine()` dispatches to real pathway-matching functions and generates an AI recommendation.
> - Two separate, unmerged course systems exist: `career/models.py` (legacy: `Course`, `TVETCourse`, `KMTCourse`, `TTCCourse`) vs `courses/models.py` (newer, unified `Course`/`CourseOffering` linked to `institutions`/`clusters`). They are bridged one-way, name-match only, by `career/management/commands/sync_career_clusters.py` (dry-run by default, `--apply` to write).

---

## Table of Contents
1. [accounts](#accounts)
2. [analytics](#analytics)
3. [career](#career)
4. [clusterpoints](#clusterpoints)
5. [clusters](#clusters)
6. [courses](#courses)
7. [institutions](#institutions)
8. [kuccpss (project package)](#kuccpss-project-package)
9. [mentorship](#mentorship)
10. [payments](#payments)
11. [predictor](#predictor)
12. [resources](#resources)
13. [Known cross-cutting issues](#known-cross-cutting-issues)

---

## accounts

Custom UUID-based email-login User model plus the account domain: tokens/sessions, dashboard aggregation, shortlist/saved-courses/comparison, notifications + web push, referral & affiliate systems, application tracker, growth/marketing (email leads, broadcasts).

### `accounts/models.py`
**Purpose:** the custom `User` model plus every account-related domain model.

Helper functions:
| Name | Description |
|---|---|
| `default_email_token_expiry()` | now + 24h, default for `EmailVerificationToken.expires_at` |
| `default_password_reset_expiry()` | now + 2h |
| `default_remember_token_expiry()` | now + 72h |
| `_make_referral_code()` | random 8-char uppercase alnum code |

`UserManager(BaseUserManager)`:
- `create_user(email, password=None, **extra)` — normalizes/requires email, unusable password if none given.
- `create_superuser(email, password, **extra)` — forces `is_staff`/`is_superuser`/`is_verified=True`, raises `ValueError` if those are explicitly set False.

`User(AbstractBaseUser, PermissionsMixin)` — **the custom user model** (never Django's default `auth.User`). Key fields: `id` (UUID pk), `email` (unique, `USERNAME_FIELD`, no username field, `REQUIRED_FIELDS=[]`), `full_name`, `is_active`, `is_staff`, `is_verified`, `is_suspended`, `is_google_user`, `agreed_terms`/`terms_version`, `last_login_ip`/`last_login_user_agent`, `phone_number`, `county`, `kcse_year`, `profile_picture`, `email_notifications`, `created_at`/`updated_at`, `deleted_at` (soft delete). Methods: `__str__` (email), `soft_delete()`.

Other models (all FK to `User` unless noted):
| Model | Purpose |
|---|---|
| `EmailVerificationToken` / `PasswordResetToken` | expiring tokens, `is_valid()` |
| `DeviceSession` | per-session device tracking |
| `RememberToken` | "remember me" token, `is_valid()` |
| `LoginHistory` | login/logout audit trail |
| `Application` | user's application tracker (status choices draft→rejected) |
| `SavedCourse` / `SavedCareer` | watchlist entries, FK to `courses.Course` / `career.CareerProfile` (string refs) |
| `CourseShortlist` | comparison tool, capped at 5/user (enforced in view, not DB), `rank` 1–4 = KUCCPS choice order |
| `Notification` | in-app notifications, `notif_type` choices |
| `CareerSessionSnapshot` | persisted career-engine run for dashboard "Recommended For You" |
| `Referral` | referral codes; `attribute_from_session()` and `get_or_create_for_user()` staticmethods |
| `AffiliateProfile` | O2O to user, `commission_rate`, `wallet_balance`, `total_earned` |
| `AffiliateCommission` | one row per referred payment, O2O to `payments.Payment` |
| `AffiliateWithdrawalRequest` | affiliate payout request |
| `EmailLead` | pre-registration email capture |
| `PushSubscription` | Web Push endpoint storage |
| `EmailBroadcast` | bulk email campaign record |

**Dependencies:** imports `courses.Course`, `career.CareerProfile`, `payments.Payment` by string reference to avoid circular imports. Nearly every other app's models FK to `settings.AUTH_USER_MODEL` (this model).

### `accounts/views.py` (~1858 lines)
All account view logic. Helpers: `get_client_ip(request)` (uses **last** `X-Forwarded-For` entry — see inconsistency note), `_is_rate_limited(key, limit, window)`.

Class-based: `RegisterView` (rate-limited 5/hr/IP, creates+verifies+logs-in user immediately, sends welcome email, attributes referral, converts matching `EmailLead`), `LoginView` (rate-limited 10/15min/IP on failure, 90-day session).

Selected function views:
| View | Description |
|---|---|
| `email_verify_view` | validates token, marks user verified |
| `dashboard_view` | large aggregator: guest fast path (static preview) vs authenticated path (KCSE results, eligible courses via `clusterpoints.eligibility`, shortlist, mentorship, career recs, affiliate, KUCCPS 2026 timeline, trends via `courses.trends`, readiness checklist, predictor comparisons, activity feed) |
| `profile_update_view`, `change_password_view` (`@require_recent_auth`), `re_auth_view` | profile/security |
| `terms_view`, `privacy_view`, `about_view`, `faq_view`, `how_it_works_view` | static pages |
| `referral_view`, `affiliate_dashboard`, `request_affiliate_payout` (`@require_recent_auth`) | referral/affiliate flows; payout via `payments.services.send_affiliate_payout` |
| `email_lead_capture` | AJAX lead capture |
| `public_home_view`, `_get_home_static_context()` | anonymous home page, cached 5 min |
| `applications_view` + add/update/delete | Application CRUD |
| `saved_courses_view`, `toggle_save_course`, `toggle_save_career` | watchlist |
| `shortlist_view`, `shortlist_toggle`, `shortlist_update_notes`, `shortlist_set_rank`, `export_shortlist_pdf`, `course_comparison_view` | shortlist/comparison (reportlab PDF) |
| `notifications_view`, `mark_notification_read`, `broadcast_notification_view` | notifications |
| `push_subscribe`, `_send_push_to_all`, `_send_push_to_user` | Web Push via `pywebpush` |
| `staff_team_view` | superuser-only staff directory |

**Dependencies:** `clusterpoints` (models, eligibility), `career` (CareerProfile, QuizSubmission, CareerConfig, AIChatCredit), `courses`, `institutions`, `mentorship`, `predictor.services`, `payments.services`, `resources.models`, `kuccpss.email_utils.send_branded_email`; third-party `reportlab`, `pywebpush`.

### `accounts/forms.py`
`validate_password_strength(password)` (min 4 chars — deliberately low), `_check_email_domain(email)` (blocks disposable domains, optional MX check via `dnspython`). Forms: `UserRegistrationForm`, `UserLoginForm`, `UserProfileForm`, `PasswordChangeForm` (appears unused — `change_password_view` does its own inline validation), `RememberTokenForm`, `UserAdminCreationForm`/`UserAdminChangeForm`, `AffiliateWithdrawalForm` (`clean_mpesa_number` normalizes to `+254XXXXXXXXX`).

### `accounts/urls.py` (`app_name="accounts"`)
See [URL_MAP.md](URL_MAP.md) for the full table. Notable: `accounts.urls` itself includes `allauth.urls`.

### `accounts/admin.py`
`UserAdmin(BaseUserAdmin)` with custom fieldsets; bulk actions `suspend_users`/`unsuspend_users`/`activate_as_affiliate`/`export_users_csv`. Standard registrations for tokens/sessions/history/saved/shortlist/notification/push/snapshot models. `AffiliateCommissionAdmin` (`mark_paid_out` action using `F()`), `EmailBroadcastAdmin` (custom "Send Now" admin action view, batches 50/send).

### `accounts/adapters.py`
`AccountAdapter(DefaultAccountAdapter)` — swallows/logs SMTP exceptions. `SocialAccountAdapter(DefaultSocialAccountAdapter)` — logs+redirects on OAuth errors instead of 500ing. Wired via `ACCOUNT_ADAPTER`/`SOCIALACCOUNT_ADAPTER` settings.

### `accounts/context_processors.py`
`unread_notifications(request)` (cached 60s, also injects `VAPID_PUBLIC_KEY`, `GOOGLE_OAUTH_AVAILABLE`); `active_announcements(request)` (cached 120s, `resources.Announcement`).

### `accounts/decorators.py`
`REAUTH_WINDOW_SECONDS = 1800`. `require_recent_auth(view_func)` — requires `_auth_verified_at` session timestamp within 30 min.

### `accounts/signals.py`
`get_client_ip(request)` — **uses first XFF entry**, inconsistent with `views.py`'s last-entry version (see cross-cutting issues). `log_user_login`/`log_user_login_failed`/`log_user_logout` (LoginHistory/DeviceSession bookkeeping), `mark_google_user_on_connect`, `on_user_signed_up` (always calls `Referral.attribute_from_session`).

### `accounts/tasks.py`
Django-Q async tasks: `send_verification_email`, `send_welcome_email`, `send_notification_email`, `expire_stale_tokens`. Largely duplicate logic already inlined synchronously in `views.py` — likely legacy/unused or reserved for future background-queue migration.

### `accounts/apps.py`
`AccountsConfig` — `ready()` imports `accounts.signals`.

### `accounts/management/commands/backup_db.py`
`python manage.py backup_db` — Postgres `pg_dump` wrapper; `--dest`/`--stdout` options; timestamped output filename.

---

## analytics

Server-side event/analytics logging plus staff-only dashboards.

### `analytics/models.py`
All models FK optionally to `settings.AUTH_USER_MODEL` (`SET_NULL`, `related_name='+'`), plus `session_key`/`created_at`.
| Model | Purpose |
|---|---|
| `PageViewLog` | auto-recorded per request by `PageTrackingMiddleware` |
| `UserActionLog` | explicit actions (login, shortlist_add, ai_chat, quiz_*, etc.) |
| `SessionLog` | one row/browser session; `duration_seconds` property |
| `SearchLog` | navbar search queries |
| `ViewLog` | generic content view (course/institution/career_profile/resource/article/mentor_profile) |
| `DownloadLog` | PDF/resource downloads |
| `EventLog` | generic catch-all event store |
| `PWAInstallLog` | PWA install events |
| `CareerEngineLog` | career-engine pathway runs |

### `analytics/views.py` (~1609 lines)
`staff_only` decorator gate on nearly all views. Helpers: `_parse_days`, `_date_labels`, `_fill_series`, `_trend`. Public/AJAX: `heartbeat` (`SessionLog.last_seen_at` ping), `pwa_install`. Staff dashboards: `analytics_dashboard` (master overview), `export_csv`, `mentor_analytics`, `affiliate_analytics`, `pages_analytics`, `actions_analytics`, `user_timeline`, `insights_dashboard` (peak-hours heatmap, referral sources, retention, funnels), `payments_overview`, `live_feed_json`, `calculator_analytics` (**pathway bucket thresholds must match** `clusterpoints/views.py::_pathway_recommendation`, called out in a code comment), `career_engine_analytics`, `conversion_analytics`, `retention_analytics` (weekly cohort grid), `ai_chat_analytics`.

**Dependencies:** `accounts.models`, `payments.models.Payment`, `resources.models.SiteFeedback`, `mentorship.models`, `clusterpoints.models.ClusterCalculationResult`, `courses.models.Course`, `career.models.AIChatCredit`.

### `analytics/admin.py`
`export_to_csv` generic action. `SearchLogAdmin` adds a custom "overview" admin page (`/cn-staff/analytics/searchlog/overview/`). Standard registrations for the rest.

### `analytics/apps.py`
`AnalyticsConfig` — `ready()` imports `analytics.signals`.

### `analytics/context_processors.py`
`posthog_keys`, `sentry_context`, `ga_context`, `data_version` (`DATA_VERSION`/`DATA_CYCLE`/`DATA_UPDATED`).

### `analytics/geo.py`
GeoIP2 wrapper around MaxMind GeoLite2-City `.mmdb`. `_get_reader()` singleton (returns `None` gracefully if missing). `get_location(ip) -> (country, region)`.

### `analytics/signals.py`
`on_user_created`, `on_payment_saved`, `on_user_login`/`on_user_logout`, `on_shortlist_add`/`on_shortlist_remove`, `_posthog()` wrapper. All wrapped in try/except — analytics failures never break the triggering action.

### `analytics/tasks.py`
Django-Q: `log_event`, `log_search`, `purge_old_logs(days=90)` (no visible scheduler wiring found).

### `analytics/utils.py`
The **primary synchronous logging API** actually called by views app-wide: `log_search`, `log_view`, `log_download`, `log_career_engine`, `log_event`, `log_action`, `track_posthog`. Every function wrapped in try/except.

---

## career

The career-guidance engine app: legacy course/pathway models, quiz, AI chat (CareerNext AI), PDF export, sharing.

### `career/models.py` (1193 lines)
Legacy course & career-guidance models plus core engine business logic.

Models: `KCSEGrade`, `CourseCategory`, `University` (legacy, distinct from `institutions.Institution`), **`Course`** (legacy — FK to `University`/`CourseCategory`/nullable FK to `clusters.Cluster`; **separate system from `courses.models.Course`**), `CourseCutoff`, `CourseCutoffHistory`, `TVETCategory`, `TVETCourse`, `KMTCampus`, `KMTCourse`, `TTCCollege`, `TTCCourse`, `StudentCourseMatch`, `AIRecommendation`, `CareerInsight`, `CareerProfile` (slug auto-gen), `QuizQuestion`/`QuizOption`/`QuizSubmission`/`QuizAnswer`, `CareerConfig` (singleton, pk=1; `ai_enabled`/`ai_model_name`/`ai_temperature`/credit limits), `AIKnowledgeEntry` (KB Q&A), `JobMarketData`, `AICallLog` (anon rate-limit), `AIChatCredit` (per-user free/paid credit balance), `SharedResult` (UUID token, shareable snapshot), `SubmissionLockConfig` (singleton), `CareerSubmission` (payment-lock mechanism shared with `clusterpoints`).

Key module-level functions:
| Function | Description |
|---|---|
| `_grades_to_points(grades)` | subject:grade → subject:points |
| `_compute_aggregate(named)` | **1 of 4 duplicate implementations** of the aggregate algorithm |
| `calculate_mean_grade(aggregate_total)` | aggregate → mean-grade letter |
| `predict_admission_chance(user_points, cutoff)` | heuristic admission-likelihood label |
| `match_degree_courses(kcse_grades, user=None)` | calls `clusterpoints.services.calculate_clusters_anonymous`, matches legacy `Course` by cluster/cutoff |
| `match_diploma_courses` / `match_tvet_courses` / `match_kmtc_courses` / `match_ttc_courses` | mean-grade-based matching (no cluster points — consistent with the Non-Degree Filtering rule) |
| `generate_ai_recommendation(matches, user=None)` | **OpenAI wiring** — `client.chat.completions.create(model=cfg.ai_model_name, ...)`, broad try/except with graceful templated fallback, always saves an `AIRecommendation` |
| `career_guidance_engine(...)` | **duplicate** of `career/engine.py`'s dispatcher, defined again here — `views.py` imports the `engine.py` version, not this one |

`Course.calculate_cluster_points` delegates to `clusterpoints.services._weighted_cp` (correctly reuses the canonical formula rather than reimplementing it).

### `career/engine.py` (44 lines)
**Not a stub.** `career_guidance_engine(kcse_grades, pathway, tvet_category=None, user=None) -> (matches, ai_recommendation)` — dispatches on `pathway` string to the `match_*` functions in `career.models`, raises `ValueError` for unrecognized pathway/missing inputs, calls `generate_ai_recommendation`. This is the version actually imported by `career/views.py`.

### `career/views.py` (~4538 lines)
Legacy pathway flow, newer "v2" degree flow, AI chat/insight endpoints, quiz, PDF export, sharing.

| View/function | Description |
|---|---|
| `parse_kcse_grades` | normalizes posted/session grade data |
| `home`, `kcse_input`, `course_detail`, `filter_matches`, `search_courses`, `export_matches_csv` | legacy pathway/list views |
| `ai_recommendations` | displays AI recommendation for a session |
| `quiz_view` / `quiz_results_view` / `_generate_quiz_ai_summary` | career-interest quiz; AI summary is **AI call #2** |
| `_build_ai_db_context` | grounds AI answers in `AIKnowledgeEntry`/`JobMarketData`/`CareerProfile` |
| `ajax_ai_insight` | **AI call #3**, `max_tokens=250` |
| `ajax_ai_chat`, `career_chat` | **AI call #4**, main CareerNext AI chat; KB-first before GPT fallback, `max_tokens=400` |
| `_check_and_increment_ai_calls` | rate/credit gate (`AICallLog` for anon, `AIChatCredit` for logged-in), gated by `CareerConfig.ai_enabled` |
| `degree_calculate`, `degree_manual` | degree pathway grade entry |
| `degree_upload` | **AI call #5** — OCR via PyMuPDF (`fitz`) + OpenAI **Vision**, **hardcoded `model='gpt-4o'`** (not the configurable `cfg.ai_model_name`) |
| `degree_paste` | regex/heuristic parsing, no AI |
| `pathway_input` | legacy non-degree pathway input |
| `career_results` | main results view, payment-gate via `payments.services` |
| `career_results_pdf_quick` / `career_results_pdf_detailed` | reportlab PDF export — **duplicated styling code** vs `clusterpoints/views.py` |
| `share_result_create` / `shared_result_view` | `SharedResult` shareable links |
| `confirm_submission`, `recalculate_view`, `clear_session`, `loading_page`, `degree_entry`, `degree_options` | session/lock/navigation plumbing |

Uses `from openai import OpenAI` exclusively — no Anthropic client found in this file despite CLAUDE.md noting the engine can use `ANTHROPIC_API_KEY`; `kuccpss/settings.py` also only defines `OPENAI_API_KEY`. All AI calls use uniformly broad try/except with graceful degradation.

### `career/forms.py` (169 lines)
Older/simpler per-pathway grade forms; superseded in the live degree flow by `clusterpoints.forms.KCSEForm`. Likely legacy, retained for `kcse_input`/`pathway_input` only.

### `career/urls.py` (`app_name="career"`, 30 patterns)
See [URL_MAP.md](URL_MAP.md).

### `career/admin.py` (355 lines)
Registrations for TVET/KMTC/TTC/CareerProfile/Quiz/CareerConfig (singleton)/AIKnowledgeEntry/JobMarketData/AICallLog (read-only)/AIChatCredit/SubmissionLockConfig/CareerSubmission.

### `career/apps.py`
`CareerConfig(AppConfig)` — name collision with the `CareerConfig` **model** in `models.py` (two distinct classes, same name).

### `career/job_market.py` (64 lines)
`_build_lookup()` (`lru_cache`), `get_jmd_for_course(course)`, `get_jmd_lookup()`.

### `career/tasks.py` (75 lines)
`generate_ai_recommendation_async`, `save_career_snapshot`, `expire_shared_results` (periodic cleanup).

### `career/tests.py`
Empty boilerplate — no actual tests.

### `career/management/commands/`
| Command | Description |
|---|---|
| `seed_careers.py` | seeds ~20+ `CareerProfile` rows + quiz seed data |
| `expand_careers.py` | adds more `CareerProfile`s, keyword-links `courses.Course` to profiles; `--link-only` flag |
| `seed_knowledge.py` | seeds `AIKnowledgeEntry` (854 lines). **One entry restates the cluster-points formula using the older, non-canonical fraction version** (`sum/48 × aggregate/84`) — the AI knowledge base is out of sync with the live `clusterpoints/services.py` formula |
| `seed_job_market.py` | seeds ~70 `JobMarketData` rows from BrighterMonday/KNBS/KRA sources |
| `sync_career_clusters.py` | **the legacy↔new course-system bridge.** Copies `cluster` FK from `courses.Course` → `career.Course` by case-insensitive name match. Dry-run by default; `--apply` to write |

---

## clusterpoints

The KCSE cluster-points calculator — home of the canonical formula.

### `clusterpoints/models.py` (242 lines)
- `TimeStampedModel` (abstract) — `created_at`/`updated_at`.
- `GradePoint` — `grade` (unique), `points`.
- `UserKCSEResult` — `user` FK (nullable), `mean_grade`, `total_points` (editable=False). **`recalc_total_points()`** — one of the 4 duplicate aggregate-algorithm implementations (Math + best language + top 5, non-chosen language returned to pool).
- `SubjectResult` — FK to `UserKCSEResult`/`clusters.Subject`, `points` (1–12, validated in `clean()`).
- `ClusterCalculationResult` — FK to `UserKCSEResult`/`clusters.Cluster`, `cluster_points`/`weighted_calculation`, `core_subject_total`/`aggregate_total`, M2M `subjects_used`.
  - **`calculate_cluster_points()` — DEAD/NON-CANONICAL CODE.** Implements the older fraction-based formula (`weighted = 48 * sqrt((raw_core_total/48) * (aggregate_total/84))`) that CLAUDE.md explicitly forbids reverting to. Nothing in the live request path (`clusterpoints/views.py` → `clusterpoints/services.py`) calls this method — it is unused legacy code, but a latent-bug risk if anything ever invokes it directly.

### `clusterpoints/services.py` (221 lines)
**The canonical, live formula implementation.**
- `GRADE_MIDPOINT_MARKS` — dict grade-points 1–12 → KCSE midpoint raw marks (E=14.0 … A=90.2).
- `_weighted_cp(core_pts, aggregate_total)`:
  ```python
  core_marks = sum(GRADE_MIDPOINT_MARKS.get(p, p * 7.5) for p in core_pts[:4])
  return round(min(48 * sqrt((core_marks / 400) * (aggregate_total / 84)), 48.0), 3)
  ```
- `calculate_clusters_anonymous(named_points)` — in-memory only, guest flow, returns `SimpleNamespace` objects.
- `calculate_all_clusters(kcse_result)` — DB-persisting version, `transaction.atomic()`, `update_or_create`.

Both functions implement identical aggregate logic (duplicate #3 of 4) and identical per-cluster core-subject slot-filling: iterate `subject_groups` by `priority`, pick highest-scoring unused subject per slot, pad with 0 if unfillable, force `weighted=0.0` if any required slot unfillable.

### `clusterpoints/eligibility.py` (216 lines)
Constants: `COURSE_CUTOFF_CACHE_KEY`/`TTL` (15 min), `CURRENT_YEAR="2024"`, `NEARLY_ELIGIBLE_GAP=5.0`, `NEARLY_ELIGIBLE_GRADE_GAP=2`, `GRADE_POINTS`, `PATHWAY_DEFAULT_MIN_GRADE`, `COURSE_TYPE_MAP`.
- `_get_course_cutoff_data()` — cached builder scanning `courses.models.CourseOffering` (degree only, cluster required).
- `_build_results_from_cluster_map(cluster_map)` — classifies eligible/nearly/not_eligible by gap.
- `get_eligible_courses_from_map`, `get_eligible_courses(user, kcse_result)` — degree pathway (cluster points).
- **`get_eligible_courses_by_mean_grade(pathway, mean_grade)`** — **non-degree eligibility**: mean-grade-only comparison against `CourseOffering.minimum_mean_grade`; confirms the Non-Degree Filtering rule — no cluster points or required-subject checks used for non-degree pathways.

### `clusterpoints/views.py` (612 lines)
- `_GRADE_BANDS`, `_mean_grade(total)`, `_pathway_recommendation(total)` (≥60 Degree / ≥46 Degree-or-Diploma / ≥32 KMTC-TVET / else Certificate&Artisan — **must stay in sync with** `analytics/views.py::calculator_analytics`).
- `_compute_aggregate(named)` — duplicate #4 of the aggregate algorithm.
- `dashboard` (`@login_required`), `kcse_calculator_view` (main calculator; submission-lock gating via `career.models.SubmissionLockConfig`/`CareerSubmission`; guest in-memory vs authenticated DB-persisted paths), `export_cluster_pdf`/`export_full_results_pdf` (`@login_required`, reportlab, duplicated styling vs `career/views.py`), `eligible_courses_view` (degree vs non-degree branch, payment-gated), `recalculate_view` (`@login_required`, POST-only), `admin_analytics` (staff), `share_calculator_create` (AJAX).

### `clusterpoints/forms.py` (100 lines)
`DEFAULT_GRADE_CHOICES`, `GROUP_LABELS`, `COMPULSORY_SUBJECT_NAMES`, `REQUIRED_SUBJECT_NAMES` (note: Chemistry listed as compulsory for display but not actually enforced — many students take Biology/Physics instead), `get_grade_choices()`. **`KCSEForm(forms.Form)`** — dynamically built per-subject `ChoiceField`s; `clean()` requires ≥7 filled subjects; `get_points_dict()`. This is the form actually used by the live degree-calculator flow, including indirectly by `career/views.py::degree_manual`.

### `clusterpoints/urls.py` (`app_name="clusterpoints"`)
See [URL_MAP.md](URL_MAP.md).

### `clusterpoints/admin.py`
`GradePointAdmin`, `SubjectResultInline`, `UserKCSEResultAdmin`, `ClusterCalculationResultAdmin` (read-only — `has_add_permission`/`has_change_permission` return `False`, correctly preventing manual tampering with derived data).

### `clusterpoints/apps.py`
`ClusterpointsConfig`.

### `clusterpoints/templatetags/custom_filters.py`
`get_item`, `abs`, `split` template filters.

---

## clusters

Reference data: KCSE subjects, KUCCPS clusters, and the subject-group "slots" the calculator engine iterates over.

### `clusters/models.py` (215 lines)
- `TimeStampedModel` (abstract).
- `Subject` — `name` (unique), `code`, `group` (I–V).
- `Cluster` — `name` (unique), `slug` (auto), `description`, `color_code`, `icon`, `image`, `number` (unique, auto-assigned). `kuccps_number` property (master clusters 101–120 → `number-100`; sub-clusters parse trailing `(\d+)` from name). `save()` auto-generates slug + number. `get_absolute_url()`.
- `SubjectGroup` — represents one "slot" in a cluster's formula. FK to `Cluster` (related_name `subject_groups`), M2M `subjects`, `required` (bool), `priority` (lower = higher priority).

This is the reference data `clusterpoints/services.py` iterates (`cluster.subject_groups` ordered by `priority`) to pick the best unused subject per slot — confirming `clusters.Cluster`/`SubjectGroup`/`Subject` are the shared canonical data the calculator engine depends on.

### `clusters/views.py` (251 lines)
`CLUSTER_LABELS` (KUCCPS master-cluster numbers 1–20 → human labels), `_main_num(cluster)`.
- `cluster_list(request)` — `@cache_page(60*20)`, excludes master clusters (`number__gte=100`), shows the ~61 programme sub-clusters grouped under their master number.
- `_parse_requirements(desc)` — splits raw description text into requirement strings.
- `cluster_detail(request, slug)` — imports `courses.models.Course` locally to avoid circular import.
- `cluster_courses(request, slug)` — payment-gated (`payments.services`), splits into free (first 5) vs paid courses.
- `cluster_create`/`cluster_edit` (`@login_required`), `subject_group_create`/`subject_group_edit` (`@login_required`) — **not wired into `clusters/urls.py`** (only 5 routes exist; these two view functions have no URL pattern), a likely dead/orphaned-view discrepancy.

### `clusters/forms.py`
`ClusterForm`, `SubjectGroupForm` (ModelForms).

### `clusters/urls.py` (`app_name="clusters"`)
5 patterns — see [URL_MAP.md](URL_MAP.md). No routes for `subject_group_create`/`subject_group_edit`.

### `clusters/admin.py`
`SubjectAdmin`, `SubjectGroupInline`, `ClusterAdmin` (color/icon/image preview renderers, inlines `SubjectGroupInline`).

### `clusters/apps.py`
`ClustersConfig`.

### `clusters/management/commands/seed_clusters.py` (396 lines)
Seeds all 31 official KCSE subjects and the **20 KUCCPS master calculation clusters** (numbers 101–120, each with exactly 4 `SubjectGroup` slots). Does not touch the ~61 programme sub-clusters (managed elsewhere). `_seed_subjects()` deletes+recreates all `Subject` rows; `_seed_clusters()` is idempotent-but-destructive to manual `SubjectGroup` customizations (rebuilds slots from scratch each run). This is the authoritative seed source feeding the full pipeline: `seed_clusters.py` → `clusters.Cluster`/`SubjectGroup`/`Subject` → `clusterpoints.services` → `clusterpoints.eligibility` (via `kuccps_number`) → `courses.CourseOffering.cutoff_points`.

---

## courses

The **newer, unified** course system — linked to `institutions` and `clusters`. Separate from `career/models.py`'s legacy Course/TVETCourse/KMTCourse/TTCCourse (see canonical rules above).

### `courses/models.py`
- `CourseType` — top-level type (Degree, Diploma, KMTC, TTC, TVET levels, Short Courses, Artisan Certificate).
- `CourseCategory` — subcategory under a `CourseType`; `unique_together=('name','course_type')`.
- **`Course`** — `name`, `slug` (auto, collision-safe), `course_type` FK, `category` FK (`SET_NULL`), **`institutions`** (M2M → `institutions.Institution`, `through='CourseOffering'`), **`cluster`** (FK → `clusters.Cluster`, `SET_NULL`, "Only for university courses" — only populated for degree courses), `core_subjects` (M2M → `clusters.Subject`), `cutoff_points` (JSONField — legacy/summary field; the authoritative per-institution data lives on `CourseOffering.cutoff_points`, nothing in the reviewed code reads `Course.cutoff_points` directly), `minimum_mean_grade` (non-degree eligibility only), `subject_requirements` (JSONField, degree only), `duration`, `career_outcomes`, `pdf_file`. `is_university_course()` returns `self.cluster is not None`. `get_absolute_url()`.
- **`CourseOffering`** — through-model for `Course`↔`Institution`; `programme_code`, `cutoff_points` (JSONField, per-institution, e.g. `{"2024": 78.5}`); `unique_together=('course','institution')`; `latest_cutoff()`.
- `Review` — 1–5 star + optional body, for either a `course` OR `institution` (conditional `UniqueConstraint`s), FK to `settings.AUTH_USER_MODEL`.
- `CourseSpotlight` — admin-curated "Course of the Week"; `current()` classmethod, `is_live` property.

Non-degree filtering confirmed: `clusterpoints/eligibility.py::get_eligible_courses_by_mean_grade` never reads `cutoff_points` or `subject_requirements` — mean-grade-only, matching the CLAUDE.md rule.

### `courses/views.py`
`_courses_per_page()` (reads `resources.SiteSetting`). `course_types_list` (`@cache_page(60*15)`, splits main vs TVET types), `course_type_detail` (search + HTMX pagination), `course_category_detail` (falls back to `course_detail()` on slug ambiguity), `course_detail` (canonical-URL redirect, Chart.js cutoff-trend data, shortlist check, review aggregation, `career.job_market.get_jmd_for_course`), `submit_course_review` (`@login_required @require_POST`).

### `courses/forms.py`
`CourseTypeForm`, `CourseCategoryForm`, `CourseForm` — **not referenced by any view**, likely dead code / remnants of a planned CRUD UI superseded by Django admin + import-export.

### `courses/urls.py` (`app_name="courses"`)
See [URL_MAP.md](URL_MAP.md). Has a harmless duplicate `from django.urls import path` import line.

### `courses/admin.py`
`CourseOfferingForm` — exposes 4 separate `cutoff_2024`..`cutoff_2021` FloatFields (min 0, max 84) that pack/unpack into the `cutoff_points` JSONField. `CourseAdmin(ImportExportModelAdmin)`, `CourseOfferingAdmin(ImportExportModelAdmin)`, `ReviewAdmin`, `CourseSpotlightAdmin`.

### `courses/apps.py`
`CoursesConfig`.

### `courses/resources.py` (django-import-export)
`CourseResource` — imports/exports basic course metadata (CSV, `import_id_fields=['name','course_type']`). `CourseOfferingResource` — imports per-institution cutoffs from a KUCCPS-shaped CSV; `get_or_init_instance()` auto-creates `CourseType`/`Course`, looks up (not creates) `Institution`; `before_save_instance()` builds the `cutoff_points` JSON and **raises** if institution not found (reported as an import error, not silently skipped).

### `courses/trends.py`
Homepage "Course Spotlight & Trends," cached 1h (`SiteSetting.trends_cache_ttl`). `_most_viewed` (from `analytics.models.ViewLog`), `_most_competitive` (max `CourseOffering.latest_cutoff()` per course, computed in Python since Postgres JSONB has no MAX aggregate), `_most_offered`, `_top_rated`, `get_trends_context()`.

### `courses/tests.py`
`CourseListTests`, `ReviewTests` — minimal smoke coverage only.

### `courses/management/commands/`
~17 one-off seeding scripts (`assign_clusters.py`, `backfill_course_fields.py`, `categorize_degrees.py`, `seed_kmtc.py`, `seed_ttc.py`, `seed_tvet*.py`, etc.) plus `tvet_data.json` static seed data. Not part of runtime logic.

---

## institutions

Directory of universities/KMTC/TVET/TTC institutions and their paid promotions/spotlights.

### `institutions/models.py`
- `InstitutionType` — top-level type; `_BG_MAP` maps `color_code` → pastel backgrounds; `display_icon()`/`display_color()`/`bg_color`.
- `Institution` — `name`, `abbreviation`, `slug` (auto, collision-safe), `institution_type` FK, `description`, `location`, `website`, `email`, `phone`, `logo`, `pdf_file`. No direct FK to `Course` — that relationship is owned by `courses.Course.institutions` (M2M through `CourseOffering`).
- `InstitutionPromotion` — paid partnership record; `tier` (featured/scholarship/course_spotlight), `pathway` (all/Degree/Diploma/KMTC/TVET/TTC), `featured_course` (FK → `courses.Course`, `SET_NULL`, course_spotlight tier only), scholarship fields, campaign window. `is_live`, `days_remaining`, `scholarship_deadline_soon` properties.

### `institutions/views.py`
Imports `courses.models.Review` (cross-app — institutions views reuse the `Review` model defined in `courses`). `institution_types_list` (`@cache_page(60*15)`), `institution_type_detail` (search + sponsored-first DB-level `Case/When` sort), `institution_detail` (groups `CourseOffering`s by `{course_type: {category: [offerings]}}`), `submit_institution_review` (`@login_required @require_POST`).

### `institutions/forms.py`
`InstitutionTypeForm`, `InstitutionForm` — like `courses/forms.py`, **not wired to any view**.

### `institutions/urls.py` (`app_name="institutions"`)
See [URL_MAP.md](URL_MAP.md).

### `institutions/admin.py`
`InstitutionTypeAdmin`/`InstitutionAdmin` (`ImportExportModelAdmin`), `InstitutionPromotionAdmin` (live-status badge, days-remaining color coding).

### `institutions/apps.py`
`InstitutionsConfig`.

### `institutions/resources.py`
`InstitutionResource`, `InstitutionTypeResource` (django-import-export, CSV).

### `institutions/tests.py`
Effectively empty (3 lines) — no test coverage.

### `institutions/management/commands/`
`seed_institution_types.py`, `seed_institutions.py`.

---

## kuccpss (project package)

The Django project package: settings, root URLconf, middleware, email backends/utils, search API, sitemaps.

### `kuccpss/settings.py` (~484 lines)
- Cloudinary env-var guard at import time (unsets malformed `CLOUDINARY_URL` before packages read it).
- `INSTALLED_APPS`, media storage (Cloudinary in prod, local `MEDIA_ROOT` in dev), email (`RESEND_API_KEY` → `kuccpss.email_backends.ResendEmailBackend`, else console).
- **MIDDLEWARE** (exact order): `SecurityMiddleware` → `WhiteNoiseMiddleware` → `GracefulErrorMiddleware` → `HeavyEndpointRateLimitMiddleware` → `SlowRequestLogMiddleware` → `DisableHttp3Middleware` → `SessionMiddleware` → `CommonMiddleware` → `CsrfViewMiddleware` → `AuthenticationMiddleware` → `PageTrackingMiddleware` → `MessageMiddleware` → `XFrameOptionsMiddleware` → `AccountMiddleware` (allauth) → `ReferralMiddleware`.
- `DATA_VERSION`/`DATA_CYCLE`/`DATA_UPDATED` constants.
- Templates: `APP_DIRS=False`, explicit loaders (+`cached.Loader` in prod). Registered context processors: request/auth/messages + `accounts.context_processors.{unread_notifications,active_announcements}` + `resources.context_processors.deadline_banner` + `analytics.context_processors.{posthog_keys,sentry_context,ga_context,data_version}`.
- Database: Postgres via `DB_*` env vars (or `DATABASE_URL` via `dj_database_url`).
- Task queue: Django-Q2 (`Q_CLUSTER`, name `careernext`), ORM broker by default, Redis if `REDIS_URL` set.
- Caching: LocMemCache by default, `RedisCache` if `REDIS_URL` set; `SESSION_ENGINE='cached_db'`.
- Payments: IntaSend env vars (`INTASEND_PUBLISHABLE_KEY`/`SECRET_KEY`/`WEBHOOK_SECRET`/`SANDBOX`). **Production raises `RuntimeError`** if `INTASEND_WEBHOOK_SECRET` missing or `SECRET_KEY` is the insecure default.
- `AUTH_USER_MODEL="accounts.User"`. `AUTHENTICATION_BACKENDS`: `ModelBackend` + allauth. 90-day sliding session.
- Allauth/Google OAuth config block; `ACCOUNT_ADAPTER`/`SOCIALACCOUNT_ADAPTER` → `accounts.adapters`; `GOOGLE_OAUTH_AVAILABLE = bool(GOOGLE_CLIENT_ID env)` (the actual `SocialApp` DB row is provisioned by `build.sh`, outside this file).
- Other integrations: `OPENAI_API_KEY` (no `ANTHROPIC_API_KEY` reference found in settings.py, despite CLAUDE.md noting it as an alternative — if used, it must be read directly inside `career/` app code), `GEOIP_PATH`, `POSTHOG_*`, `GA_MEASUREMENT_ID`, `AFFILIATE_PAYOUT_PHONE`, VAPID keys, `SENTRY_DSN` (as `_SENTRY_DSN`).
- Production-only hardening (`if not DEBUG`): SSL redirect, HSTS 1yr+preload, secure/httponly cookies. `SECURE_CONTENT_TYPE_NOSNIFF=True` applies universally.

### `kuccpss/urls.py`
Root URLconf. Inline views: `serve_sw` (service worker), `health_check` (JSON, pings DB), `serve_robots`/`serve_llms`. Mounts every app's urls; **notable oddity: `accounts/` is mounted 3 times** (`accounts.urls` which itself includes `allauth.urls`, plus separately `django.contrib.auth.urls` and `allauth.urls` again) — see [URL_MAP.md](URL_MAP.md) and cross-cutting issues below.

### `kuccpss/middleware.py`
| Middleware | Description |
|---|---|
| `ReferralMiddleware` | captures `?ref=CODE` into session, validates against `Referral` (300s cache) |
| `DisableHttp3Middleware` | sets `alt-svc: clear` on every response |
| `SlowRequestLogMiddleware` | logs (WARNING) requests slower than 1500ms |
| `GracefulErrorMiddleware` | `process_exception` hook — passes through Http404/PermissionDenied, JSON error for HTMX, debug traceback in DEBUG, `500.html` otherwise |
| `PageTrackingMiddleware` | core analytics writer — creates `PageViewLog`, upserts `SessionLog` (with geo via `analytics.geo`), skips static/media/analytics'-own endpoints; blanket try/except |
| `HeavyEndpointRateLimitMiddleware` | cache-based IP rate limiting for specific route+method combos (`POST /clusterpoints/` 20/10min, `GET /clusterpoints/eligible-courses/` 30/10min, `POST /career/` 10/10min); 429 JSON or `429.html` |

### `kuccpss/asgi.py` / `kuccpss/wsgi.py`
Standard Django boilerplate; `wsgi.py` is the one actually used in production (gunicorn on Render).

### `kuccpss/email_backends.py`
`ResendEmailBackend(BaseEmailBackend)` — sends via Resend's REST API over HTTPS (avoids Render free-tier SMTP port blocking).

### `kuccpss/email_utils.py`
`BANNER_COLORS`. **`send_branded_email(...)`** — the shared transactional email helper used app-wide (registration, verification, affiliate payouts, admin broadcasts); renders `templates/emails/transactional.html`, builds plain-text fallback, supports attachments.

### `kuccpss/search_views.py`
Global navbar search-suggest API. `_acronym(text)`, `_score(query, name, abbr='')` (tiered scoring: 100 exact word-boundary substring, 98 exact abbreviation, 95 acronym exact, 85 abbreviation prefix, 82 word-starts-with, 75 acronym prefix, 70 multi-token, ~55/45 fuzzy via `difflib.SequenceMatcher`, else excluded below score 30). `api_search_suggest(request)` — queries `institutions.Institution`/`courses.Course`, logs via `analytics.utils.log_search`.

### `kuccpss/sitemaps.py`
7 `Sitemap` subclasses: `StaticPagesSitemap`, `CourseSitemap`, `CourseTypeSitemap`, `CourseCategorySitemap`, `InstitutionSitemap`, `InstitutionTypeSitemap`, `ClusterSitemap`, `ArticleSitemap`.

---

## mentorship

Mentor directory, booking, session lifecycle, withdrawals.

### `mentorship/models.py`
- **`MentorProfile`** — O2O to user, FK to `courses.Course`/`institutions.Institution` (`SET_NULL`), `year_of_study`, `bio`, `whatsapp`, `photo`, verification docs (`student_id_upload`, `portal_screenshot` — required at form level, not model level), `custom_session_price`/`custom_mentor_payout` (per-mentor overrides), `wallet_balance`/`total_earned`, `total_sessions`/`average_rating`, approval workflow (`is_approved`/`is_active`/`is_rejected` — permanent, blocks reapplication). Methods: `refresh_stats()`, `display_name`, `rating_int`, `available_slots_count`, `effective_session_price()`/`effective_mentor_payout()` (fall back to `MentorshipConfig.get()`).
- **`TimeSlot`** — FK to `MentorProfile`, `date`/`start_time`/`is_booked`; `unique_together=['mentor','date','start_time']`.
- **`WithdrawalRequest`** — `amount`, `mpesa_number`, `status` (`pending`/`processed`/`rejected` — **note: does not include `"failed"`**, yet both `request_withdrawal` and the auto-pay helper set `status="failed"` on exception, a latent data-integrity bug since it saves without DB-level enforcement but breaks `get_status_display()`/admin filters).
- **`MentorshipSession`** — `token` (UUID4, public identifier), FK to `MentorProfile`/user/`TimeSlot` (O2O)/`courses.Course`, payment fields (`amount`, `mentor_payout`, `payment_ref`, `manual_payment_ref`), `confirmation_sent`, `status` (pending_payment/pending_manual_verification/confirmed/completed/cancelled/refunded). `meet_link` (URLField, added migration 0007) — **confirmed dead/unused**: never written or read by any view/admin/template; calendar coordination is done via Google Calendar "add event" links + WhatsApp-coordination text instead. `rating`/`review`.
- **`MentorshipConfig`** (singleton, pk=1) — `session_price`, `mentor_payout`, `mentor_signup_enabled`.

### `mentorship/views.py`
`_admin_email()` (reads `SiteSetting['admin_email']`), `_mentors_per_page()`.

Public: `directory` (search/filter, HTMX partials), `mentor_profile` (logs view), `courses_for_institution` (AJAX cascade).

Become-mentor: `become_mentor` (`@login_required`), `become_mentor_success`, `withdraw_application` (`@login_required @require_POST`), `edit_mentor_profile` (`@login_required`).

Dashboard: `mentor_dashboard`, `add_slots`/`add_weekly_slots` (idempotent `get_or_create`), `delete_slot`, `complete_session`.

Booking: `book_session` (`@login_required`, race-condition re-check on `slot.is_booked`), `checkout`, `session_status` (AJAX poll, fallback-sends confirmation if webhook raced ahead), `initiate_payment` (`@login_required @require_POST`, calls `payments.services.initiate_stk_push` with `payment_ref=str(session.token)`), `verify_payment_manual` (fallback path — `fetch_intasend_status` direct check then manual-verification email), `_confirm_session_after_payment` (shared confirm logic: credits wallet, sends emails, calls `_maybe_auto_pay_mentor`), **`payment_webhook`** (`@csrf_exempt` — **no signature verification**, distinct from `payments.views.mpesa_webhook`).

Session lifecycle: `session_detail`, `rate_session` (`@login_required`, one-time), `my_sessions`, `cancel_session` (frees slot, debits wallet if credited, manual/admin-driven refund only), `download_ics`.

Withdrawal: `request_withdrawal` (`@require_recent_auth @require_POST` — uses `accounts.decorators.require_recent_auth`), `_maybe_auto_pay_mentor` (module constant `AUTO_PAY_THRESHOLD = getattr(settings, "MENTOR_AUTO_PAY_THRESHOLD", 500)` — **not defined anywhere in `settings.py`**, always defaults to 500), `_send_booking_confirmation`, `_send_cancellation_emails`.

**Dependencies:** `accounts.decorators`, `accounts.models.Notification`, `accounts.views._send_push_to_user`, `kuccpss.email_utils.send_branded_email`, `resources.models.SiteSetting`, `payments.models.Payment`, `payments.services` (`initiate_stk_push`, `normalise_phone`, `fetch_intasend_status`, `send_mentor_payout`), `analytics.utils.log_view`. **Reverse dependency:** `payments/views.py::mpesa_webhook` also directly manipulates `MentorshipSession` and calls `_send_booking_confirmation` — see cross-cutting issues.

### `mentorship/forms.py`
`parse_custom_time(value)`. `MentorRegistrationForm` — `__init__` restricts institution queryset to `institution_type_id__in=[2,3,4]` (**hardcoded IDs**, fragile if seed data changes); `clean_whatsapp()` normalizes to `+254XXXXXXXXX`. `BookingForm`, `AddSlotsForm` (`clean_date()` rejects past dates), `AddWeekSlotsForm` (snaps to Monday), `RatingForm`, `_mentor_min_withdrawal()` (reads `SiteSetting['mentor_min_withdrawal']`), `WithdrawalForm`, `CancelSessionForm`.

### `mentorship/urls.py` (`app_name="mentorship"`)
See [URL_MAP.md](URL_MAP.md).

### `mentorship/admin.py`
`MentorProfileAdmin` — inlines (`TimeSlotInline`, `MentorshipSessionInline`, `WithdrawalInline`), custom per-row **Reject button** (`get_urls()` → `_reject_mentor_view`), bulk actions `approve_selected`/`reject_selected`/`deactivate_selected` (approval email copy hardcodes "KES 70/session" — inconsistent with configurable `MentorshipConfig`). `MentorshipSessionAdmin` (`mark_completed`, `mark_refunded`, `confirm_manual_payment` — calls `mentorship.views._confirm_session_after_payment`). `WithdrawalRequestAdmin` (`mark_processed`, `mark_rejected`). `MentorshipConfigAdmin` (singleton pattern).

### `mentorship/apps.py`
Trivial `AppConfig`.

### `mentorship/calendar_utils.py`
Pure-Python calendar generation — **no external library, no Google Calendar API auth, no Jitsi** (despite model docstring mentioning "Jitsi room"). `google_calendar_url(session)` — client-side "add to calendar" link, location hardcoded to `"Coordinate via WhatsApp"`. `generate_ics(session)` — hand-built `VCALENDAR`/`VEVENT` with two `VALARM` reminders. Neither references `meet_link`.

### `mentorship/management/commands/mentorship_housekeeping.py`
Cron job. `_send_reminders()` (60–120min window, **no idempotency flag** — duplicate reminders possible on repeated runs), `_complete_expired()` (auto-completes sessions >30min past). **Does not** touch `WithdrawalRequest` or withdrawal `SiteSetting`s at all.

### `mentorship/management/commands/seed_test_mentors.py`
Dev/demo seeding — 5 hardcoded approved `MentorProfile`s with fallback lookups if hardcoded PKs don't exist. Idempotent.

---

## payments

IntaSend-based M-Pesa payment integration (STK push collection + B2C payouts), feature gating, exemptions.

**Important:** this app does **not** use Safaricom's Daraja API directly — it proxies everything through **IntaSend**, a payment aggregator, via `sandbox.intasend.com`/`payment.intasend.com`.

### `payments/models.py`
`PRODUCT_CHOICES` (cluster_points/career_engine/careernext_ai/mentorship), `FEATURE_TO_PRODUCT` mapping, `AFFILIATE_EXCLUDED_FEATURES = {"mentorship_booking","ai_chat_access"}`.
- `PaymentFeature` — admin-configurable toggle/price per feature.
- `Payment` — `feature` choice, `amount`, `phone_number`, `checkout_id` (IntaSend ref, unique-when-nonempty via conditional constraint), `status` (pending/completed/failed/refunded), `mentorship_session` (O2O, `SET_NULL`). `is_active()`, `product` property.
- `PaymentExemption` — free access grant (blank `feature`=all); staff always exempt regardless of a record (enforced in `services.py`, not model level).
- `Transaction` — raw IntaSend webhook payload log, FK to `Payment`.

### `payments/views.py`
`_generate_receipt_pdf` (reportlab), `_send_payment_receipt` (HTML+PDF email, best-effort), `_grant_ai_credits_if_applicable` (tops up `career.models.AIChatCredit`), `payment_required` (`@login_required`), `payment_history` (`@login_required`), `initiate_payment` (`@login_required @require_POST` — blocks free/duplicate/non-repeatable-completed features, 503 if IntaSend keys unconfigured).

**`mpesa_webhook`** (`@csrf_exempt @require_POST`) — **the signed/secured webhook**. Verifies `X-IntaSend-Signature` (HMAC-SHA256) when `INTASEND_WEBHOOK_SECRET` set. Sniffs `api_ref`: if it parses as a UUID matching a pending `MentorshipSession.token`, confirms the session **inline** (duplicated logic from `mentorship.views._confirm_session_after_payment` — does **not** call `_maybe_auto_pay_mentor`); otherwise treats `api_ref` as a `Payment` pk. On `COMPLETE`: grants AI credits, calls `lock_submission_on_payment`, sends receipt, and (unless `feature in AFFILIATE_EXCLUDED_FEATURES`) awards affiliate commission via `F()` expressions (idempotent check).

`payment_status`, `verify_payment` (`@login_required` — fallback via `fetch_intasend_status`; **does not** run affiliate-commission logic, an inconsistency vs `mpesa_webhook`), `verify_by_transaction_code` (`@login_required @require_POST` — also skips affiliate commission), `pending_payment_for_feature`.

### `payments/urls.py` (`app_name="payments"`)
See [URL_MAP.md](URL_MAP.md).

### `payments/admin.py`
`ProductListFilter`, `PaymentFeatureAdmin` (`list_editable`), `PaymentAdmin` (`list_editable=("status",)`, `mark_completed`/`mark_failed` actions), `TransactionAdmin`, `PaymentExemptionAdmin` (auto-sets `granted_by`).

### `payments/apps.py`
Trivial.

### `payments/services.py`
Base URLs `SANDBOX_BASE`/`PROD_BASE` selected by `INTASEND_SANDBOX`.
- `initiate_stk_push(phone_number, amount, payment_ref, email="", narrative="CareerNext")` — `POST {base}/payment/mpesa-stk-push/`. `payment_ref` doubles as the linking key both webhook handlers sniff (`str(payment.pk)` for generic payments, `str(session.token)` UUID for mentorship). Returns `invoice_id` → stored as `checkout_id`.
- `fetch_intasend_status(checkout_id)` — `GET .../payment/collection/{checkout_id}/`, returns uppercased `state` or `None` (swallowed on exception).
- `send_mentor_payout(phone, amount, mentor_name, ref="")` / `send_affiliate_payout(phone, amount, affiliate_name, ref="")` — B2C payouts via `.../send-money/mpesa/`.
- `normalise_phone(phone)` — → `2547XXXXXXXX` format.
- `has_paid_for_feature(user, feature)` — staff bypass → `PaymentExemption` → completed `Payment` exists.
- `has_paid_for_current_session(user, calc_feature, gate_feature)` — session-aware gate via `career.models.CareerSubmission.unlocked_by_payment_id`.
- `lock_submission_on_payment(payment)` — locks the user's `CareerSubmission` after a relevant payment completes, per `career.models.SubmissionLockConfig`.
- `price_for_feature(feature)` / `is_feature_enabled(feature)` — reads `PaymentFeature` DB row, falls back to hardcoded `FEATURE_PRICES` dict if the table lookup raises.
- `REPEATABLE_FEATURES`, `PAYMENT_TO_SUBMISSION` module constants.

### `payments/tasks.py`
`send_payment_confirmation` (plain-text, appears to be an older/alternate mechanism vs. `views.py`'s HTML+PDF version), `check_pending_payments()` (marks >30min pending as failed — no visible scheduler wiring), `top_up_ai_credits_after_payment` (alternate to the inline version in `views.py`).

### `payments/tests.py`
Empty stub.

### `payments/management/commands/seed_payment_features.py`
Seeds 5 `PaymentFeature` rows; `--force` to overwrite. Slightly diverges from the migration-seeded defaults for `advanced_analysis` (`enabled=False` here vs `enabled=True` in `0004_seed_payment_features.py` migration).

---

## predictor

Predicts future cutoff points from historical `CourseOffering.cutoff_points`, labels eligibility likelihood against a student's cluster points.

### `predictor/models.py`
`PredictionConfig` — singleton (pk=1). Fields: `rising_floor_multiplier` (0.50), `rising_floor_cap` (3.0), `stable_floor_offset` (0.0), `band_multiplier` (1.0). `get()` classmethod (`get_or_create(pk=1)`).

### `predictor/services.py`
Cluster-numbering bridge tables: **calculator clusters** (101–120, `clusterpoints`) vs **course sub-group clusters** (5–65, `CourseOffering.cutoff_points` keys) vs **KUCCPS clusters** (1–20, canonical names). `COURSE_TO_KUCCPS`, `calc_to_kuccps(calc_num)`, `CALC_TO_COURSE`, `COURSE_TO_CALC`, `KUCCPS_NAMES`, `TREND_ICON`/`TREND_COLOR`/`TREND_TIP`.

- `_get_config()` — 60s in-memory cache of `PredictionConfig`, falls back to `_DefaultConfig` if DB unavailable.
- **`predict_cutoff(history)`** — 70% weighted-moving-average + 30% naive-latest blend, plus a rising-trend floor adjustment. WMA weights scale by years of history available (1yr straight value; 2yr 60/40; 3yr 50/30/20; 4+yr 40/30/20/10 using last 4). `variance` (± confidence band) = avg abs delta between years, floored 0.5, scaled by `cfg.band_multiplier`. `trend` from last-two-year delta (rising >0.3 / falling <-0.3 / else stable). Final `predicted` clamped [0,48] (cluster-points scale). Docstring cites a backtest MAE of 1.581 vs WMA-alone 1.68 / Linear 2.49 / Holt's 3.93 on 720 KUCCPS courses.
- `eligibility(student_score, pred)` — 4-tier: High Likelihood / Likely / Borderline / Unlikely, each with rank/css/icon.
- `predict_offerings_for_calc_cluster(calc_cluster_number, student_score, limit=20)`.
- `predict_all_for_student(cluster_scores, top_per_cluster=5)`.

### `predictor/views.py`
`_cluster_scores_from_request(request)` — authenticated: latest `UserKCSEResult.cluster_results`; guest: `request.session['guest_calc']['named_points']` via `clusterpoints.services.calculate_clusters_anonymous` — confirming predictor depends on `clusterpoints` for both flows. `_all_offerings_with_pred(...)`. `predictor_index(request)` — the sole view; search/filter by cluster/type/status, paginated 30/page.

### `predictor/urls.py` (`app_name="predictor"`)
Single route (`""` → `predictor_index`, name `index`). No detail views, no POST endpoints.

### `predictor/admin.py`
`PredictionConfigAdmin` — enforces singleton in the admin UI (`has_add_permission` False if a row exists, `has_delete_permission` always False); `changelist_view()` redirects straight to the change form.

### `predictor/apps.py`
`PredictorConfig` — `verbose_name = "Cutoff Predictor"`. No `forms.py`, no `resources.py`, no `tests.py` in this app.

---

## resources

Site-wide content and configuration: articles, downloadable resources, FAQs, success stories, announcements, deadline banner, feedback, and the generic `SiteSetting` key/value store used across many other apps.

### `resources/models.py`
- **`SiteSetting`** — generic key/value config store (`key` unique, `value` TextField, `setting_type`, `group`, `help_note`). `get(key, default='')` classmethod — the universal read helper used throughout the codebase (mentorship, payments-adjacent code, career, courses pagination, etc.) to make values admin-tunable without new migrations.
- `FAQItem` — categorized Q&A (general/cluster/courses/kuccps/account).
- `SuccessStory` — homepage testimonials, auto-fills `initials` from `name`.
- `ResourceCategory` / `Resource` — downloadable content; `increment_download()` via `F()`.
- `Article` — blog content; `get_tags_list()`, `featured` flag, `reading_time` property.
- `Announcement` — site-wide banner with optional scheduling window.
- `DeadlineBanner` — countdown-bar model, admin-restricted to one row (not a true DB-level singleton); two configurable deadline date/label pairs, separate link sets for authenticated vs guest.
- `SiteFeedback` — user-submitted feedback/bug reports.

### `resources/views.py`
`resource_list` (filter/paginate/HTMX), `resource_detail` (increments counter, logs via `analytics.utils.log_download`), `article_list` (search/tag filter, HTMX), `article_detail` (related-articles: shared-tag match first, backfills to 3), `kuccps_calendar`, `how_to_guides` (static renders), `submit_feedback` (`@require_POST`).

### `resources/urls.py` (`app_name="resources"`)
See [URL_MAP.md](URL_MAP.md). Note: `<slug:slug>/` catch-all for `resource_detail` must stay last in the pattern list.

### `resources/admin.py`
Registrations for all 8 models. `DeadlineBannerAdmin` enforces singleton via `has_add_permission`/`has_delete_permission`. `SiteFeedbackAdmin` disables add permission, most fields readonly except `status`/`admin_note`.

### `resources/apps.py`
Trivial.

### `resources/context_processors.py`
`deadline_banner(request)` — the only context processor in this app; caches the active `DeadlineBanner` 120s under key `'deadline_banner'`.

### `resources/management/commands/seed_content.py`
One-time bootstrap: `FAQ_DATA` (~24 entries), `STORIES_DATA` (6 testimonials), `SETTINGS_DATA` (9 `SiteSetting` rows). Idempotent (`get_or_create`).

### `resources/` one-off ETL scripts (not registered Django commands)
A large family of standalone developer-tooling scripts living directly in `resources/` (not `management/commands/`) used once to extract KUCCPS PDF programme lists into seed data: `extract_pdfs.py` (pdfplumber → text dumps), `fix_normalize.py` (patches `courses/management/commands/seed_tvet_programmes.py`'s `normalize()` function), `audit_zero_offerings.py`, and ~35 more (`check_types.py`, `analyze_pdfs.py`, `verify_tables.py`, `fix_misplaced_courses.py`, `audit_level3.py`/`audit_level4.py`, `fix_level_mixing.py`, `fix_ttc_institutions.py`, etc.), plus intermediate `.txt`/`.tsv` output artifacts. This is historical ETL trace, not live application code.

---

## Known cross-cutting issues

Documented here because they span multiple files/apps and are easy to miss when reading a single file in isolation:

1. **Duplicate `/accounts/` URL mounts** — `kuccpss/urls.py` mounts `accounts.urls` (which itself already includes `allauth.urls`), plus separately `django.contrib.auth.urls` and `allauth.urls` again at the same `/accounts/` prefix. Likely accumulated technical debt; Django resolves by list order so `accounts.urls` wins for name collisions, but the duplicate `allauth.urls` include is redundant.

2. **`get_client_ip` inconsistency** — `accounts/views.py::get_client_ip` uses the **last** entry of `X-Forwarded-For`; `accounts/signals.py::get_client_ip` uses the **first** entry. Same name, same app, different logic.

3. **Async tasks vs. sync helpers duplication** — `accounts/tasks.py`, `analytics/tasks.py`, and `payments/tasks.py` (Django-Q) largely duplicate functionality already called synchronously inline in the corresponding `views.py`/`utils.py` (e.g. verification emails sent directly via `send_branded_email` in `RegisterView.post`, not enqueued). The task-queue versions may be legacy or reserved for a future migration to background processing. `analytics.tasks.purge_old_logs` and `payments.tasks.check_pending_payments` have no visible scheduler wiring in the codebase.

4. **`clusterpoints/models.py::ClusterCalculationResult.calculate_cluster_points`** implements the deprecated fraction-based formula and is dead code — see canonical rules at the top of this document.

5. **The aggregate-total algorithm is duplicated in 4 places** — `career/models.py::_compute_aggregate`, `clusterpoints/models.py::UserKCSEResult.recalc_total_points`, `clusterpoints/services.py` (inline), `clusterpoints/views.py::_compute_aggregate`. Any future change to the aggregate rule must be made in all four.

6. **`career/models.py::career_guidance_engine`** duplicates `career/engine.py`'s dispatcher (same name, same purpose, different file). `career/views.py` imports the `engine.py` version. The `models.py` copy appears to be dead/legacy.

7. **AI knowledge base drift** — `career/management/commands/seed_knowledge.py` seeds an `AIKnowledgeEntry` that states the cluster-points formula using the **older, non-canonical fraction version**, out of sync with the live `clusterpoints/services.py` implementation.

8. **Two independent mentorship-payment-confirmation webhooks** — `mentorship.views.payment_webhook` (unsigned) and `payments.views.mpesa_webhook` (HMAC-signed, but reimplements confirmation logic inline and does **not** call `_maybe_auto_pay_mentor`). A future change to the shared confirm helper must be manually mirrored in `payments/views.py`.

9. **`MentorshipSession.meet_link`** (migration 0007) is a dead column — never written or read anywhere in the app; calendar coordination happens via Google Calendar links + WhatsApp text instead.

10. **`WithdrawalRequest.status="failed"`** is used by application code but not present in the model's `STATUS_CHOICES` (`pending`/`processed`/`rejected` only) — saves without error but breaks `get_status_display()`/admin filters.

11. **Affiliate commission inconsistency** — awarded in `payments.views.mpesa_webhook` but **not** in the `verify_payment` or `verify_by_transaction_code` fallback confirmation paths, meaning payments confirmed via those fallbacks never earn affiliate commissions.

12. **Dead/unwired forms** — `courses/forms.py` (`CourseTypeForm`, `CourseCategoryForm`, `CourseForm`) and `institutions/forms.py` (`InstitutionTypeForm`, `InstitutionForm`) are defined but referenced by no view — likely remnants of a planned CRUD UI superseded by Django admin + import-export. `clusters/views.py::subject_group_create`/`subject_group_edit` have no URL pattern in `clusters/urls.py`.

13. **`MENTOR_AUTO_PAY_THRESHOLD`** referenced via `getattr(settings, ..., 500)` in `mentorship/views.py` but never defined in `kuccpss/settings.py` — always uses the 500 default.

14. **No `ANTHROPIC_API_KEY` found in `kuccpss/settings.py`** — only `OPENAI_API_KEY` is defined/used (career AI chat, quiz summary, insight, and vision-OCR calls all use `from openai import OpenAI` exclusively). Per CLAUDE.md the engine can use either; if Anthropic is wired anywhere it was not found in the reviewed files.

15. **PDF export styling duplication** — the reportlab NAVY/TEAL/EMERALD/AMBER/PURPLE/SLATE branded header/footer drawing code is independently reimplemented in `career/views.py` (`career_results_pdf_quick`/`_detailed`), `clusterpoints/views.py` (`export_cluster_pdf`/`export_full_results_pdf`), `accounts/views.py` (`export_shortlist_pdf`), and `payments/views.py` (`_generate_receipt_pdf`) rather than factored into a shared module.

16. **Password strength minimum is 4 characters** (`accounts/forms.py::validate_password_strength`) — intentionally low, separate from and not consistently applied alongside Django's `AUTH_PASSWORD_VALIDATORS` (`MinimumLengthValidator` min_length=6), which is not obviously invoked in the custom registration/change-password paths.
