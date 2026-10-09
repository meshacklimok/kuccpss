# Implementation Status

A consolidated Completed vs. Remaining/Incomplete/Broken view of the codebase, synthesized from
every other doc in this set (especially [FEATURES.md](FEATURES.md), [DATABASE.md](DATABASE.md),
[SECURITY.md](SECURITY.md), [FILE_EXPLANATIONS.md](FILE_EXPLANATIONS.md)). Where the root
[FEATURE_STATUS.md](FEATURE_STATUS.md)/[TODO.md](TODO.md) already track a status legend, this doc adds
concrete, code-verified detail rather than repeating the summary table.

## ✅ Completed and live

| Area | Notes |
|---|---|
| Auth (email/password + Google OAuth) | Custom UUID `accounts.User`, email verification, password reset, re-auth gate. See [SECURITY.md](SECURITY.md) §1. |
| KCSE Cluster Points Calculator | Canonical formula in `clusterpoints/services.py`, live and correct for both guest and authenticated flows. |
| Degree eligibility matching | `clusterpoints/eligibility.py::get_eligible_courses` — cluster-points-based, complete. |
| Non-degree eligibility matching | `get_eligible_courses_by_mean_grade` — mean-grade-only logic is complete and correct; underlying data is incomplete (see Remaining). |
| Career engine | `career/views.py` pathway flow on `courses.Course` — Degree by cutoff points, every other pathway by mean grade. Legacy `career/engine.py` removed 2026-10-08. |
| CareerNext AI chat | Knowledge-base-first, OpenAI-fallback, credit/rate-gated, master-switched via `CareerConfig`. |
| Career quiz | Tag-based scoring against `CareerProfile`, AI-narrated summary. |
| OCR grade upload | GPT-4o Vision extraction from photo/PDF, degrades gracefully to manual entry on failure. |
| Course & institution directories | Browsing, reviews, shortlist (max 5, ranked), comparison, saved courses — complete. |
| Payments (IntaSend M-Pesa) | STK push, webhook confirmation, manual code fallback, feature gating/exemptions — live in production. |
| Mentorship marketplace | Directory, booking, session lifecycle, wallet, withdrawals — complete; payout depends on IntaSend B2C activation (external, unverifiable from code). |
| Affiliate/referral system | Code generation, attribution, commission crediting, payout — complete. |
| Analytics & staff dashboards | 16 dashboards, comprehensive fail-silent event logging — complete. |
| Notifications (in-app + push) | VAPID web push, broadcast, booking confirmations — complete. |
| PDF export | Cluster results, shortlist, career results, payment receipts — all implemented (see Remaining for full-results parity caveat). |
| Predictor | WMA+naive cutoff-trend blend, 4-tier eligibility labeling — complete, no test coverage. |
| Resources (articles/FAQs/deadline banner) | Complete, `SiteSetting` as the universal config pattern. |
| PWA | Manifest, service worker, offline fallback, install prompts (including iOS), push — complete. |
| Production hardening | `SECRET_KEY`/`INTASEND_WEBHOOK_SECRET` startup guards, HSTS, secure cookies, HMAC webhook verification (payments only) — real, confirmed in `settings.py`. |

## 🚧 Incomplete / data gaps (logic is correct, data is not)

- ~~Sub-cluster data gap~~ — resolved Sept 2026: sub-clusters removed; all degree courses sit in
  the 18 KUCCPS clusters (101–118) with portal entry/subject requirements.
- **Degree eligibility on `clusterpoints` "eligible courses" does not check `subject_requirements`**
  (only cutoffs); the career degree flow does. Old `CareerSessionSnapshot`s keyed on the 20-cluster
  numbering are not migrated.
- **Degree courses not on the 2025 KUCCPS portal** kept their old data and were moved to a cluster
  by renumbering only (see [KUCCPS_2025_CLUSTER_MOVES.md](KUCCPS_2025_CLUSTER_MOVES.md)).
- **TVET/TTC cutoff points and subject requirements** are largely unsourced — `Course.minimum_mean_grade`/
  `subject_requirements` rows are blank for most non-KMTC non-degree courses. Eligibility *logic*
  is correct; results will simply be less precise until this data-entry work is done.
- Clusters **1A, 2B, 3D** (and part of 2A) have placeholder requirement-description text rather
  than real KUCCPS requirement text (per [CHANGELOG.md](CHANGELOG.md)/TODO.md, unresolved
  as of the most recent dated changelog entry, 2026-06-30).

## 🚧 Stubbed / placeholder functionality

## ❌ Dead code

- **`clusterpoints/models.py::ClusterCalculationResult.calculate_cluster_points()`** — implements
  the old, forbidden fraction-based formula (`core_pts/48` instead of midpoint-marks). Never
  called by the live request path (`views.py` → `services.py`), but its presence is a latent-bug
  risk if anything ever calls it directly. **Do not use this method as a reference for the formula.**
- **`courses/forms.py`** (`CourseTypeForm`, `CourseCategoryForm`, `CourseForm`) and
  **`institutions/forms.py`** (`InstitutionTypeForm`, `InstitutionForm`) — not referenced by any
  view, likely superseded by Django admin + `django-import-export`.
- **`accounts/forms.py::PasswordChangeForm`** — defined but `change_password_view` implements its
  own inline validation instead.
- **`MentorshipSession.meet_link`** column (migration `0007`) — never written or read anywhere.
- **`Course.cutoff_points`** (on the parent `Course`, not `CourseOffering`) — appears unused;
  `CourseOffering.cutoff_points` is the authoritative per-institution field everywhere it matters.
- **`analytics/tasks.py`** — Django-Q async logging variants that largely duplicate the synchronous
  helpers in `analytics/utils.py` actually called from views; usage/purpose unclear.
- **`payments/tasks.py::send_payment_confirmation`** — plain-text email, appears superseded by the
  HTML+PDF receipt path in `payments/views.py::_send_payment_receipt`.
- **`accounts/tasks.py`** async email tasks — appear to duplicate the synchronous email sending
  already inlined in `RegisterView.post`.

## 🐛 Confirmed bugs / inconsistencies

Re-verified against the code on 2026-07-02. Items previously listed here that are now fixed:
mentorship webhook HMAC verification, unified webhook payout logic (`_confirm_session_after_payment`),
affiliate commission on all verification paths, `WithdrawalRequest` "failed" status choice,
`get_client_ip()` unified in `kuccpss/ip_utils.py`, password-validator sync (6-char in both places),
AI knowledge-base formula (now midpoint-marks), duplicate `/accounts/` + `dashboard/` URL mounts,
orphaned `clusters` views (now wired), `mentorship/directory.html` dark-mode selector,
`MentorRegistrationForm` slug-based institution filter, `MENTOR_AUTO_PAY_THRESHOLD` (defined in
settings), and the previously untracked `resources/0010` migration (committed).

Still open:

| Issue | Where | Detail |
|---|---|---|
| `advanced_analysis` feature default mismatch | `payments/migrations/0004_seed_payment_features.py` (enabled) vs. `payments/management/commands/seed_payment_features.py` (disabled) | Re-running the command with `--force` would silently flip production behavior. |
| Duplicated paywall polling JS | `templates/payments/payment_required.html` vs. `paywall_overlay.html` | Near-identical M-Pesa polling logic under separate JS namespaces (`pr*` vs `pw*`). |
| No shared PDF-styling module | `clusterpoints/views.py`, `career/views.py`, `payments/views.py` | Branded palette/header/footer drawing logic copy-pasted independently in 3 files. |

## 📋 Test coverage

Now covered (previously listed as gaps): `payments/tests.py` (pricing/feature-gate tests),
`institutions/tests.py`, `predictor/tests.py`, and formula-correctness tests in
`clusterpoints/tests.py` (weighted formula, 48 cap, aggregate max-84 selection rules — 12 tests, passing).

Remaining thin spots:

- `courses/tests.py` — smoke/review flows only, not chart logic, category-fallback redirects, or `trends.py`.
- No integration test for the full grade entry → loading → results flow (tracked in TODO.md).

## Course systems merged (2026-10-08, phase 1)

All course matching now reads `courses.Course` / `CourseOffering` / `institutions.Institution`.
The legacy career code path (`career/engine.py`, `career/forms.py`, the match/calc helpers and
`generate_ai_recommendation()` in `career/models.py`, `sync_career_clusters`, and the
`kcse_input`/`results`/`course_detail`/`ai_recommendations` views and templates) was removed.
Old URLs 301 to `/career/` (or `/career/input/<pathway>/` when `?pathway=` is given).

The legacy model classes (`KCSEGrade`, `University`, `CourseCategory`, `Course`, `CourseCutoff`,
`CourseCutoffHistory`, `TVET*`, `KMT*`, `TTC*`, `StudentCourseMatch`, `AIRecommendation`,
`CareerInsight`) and their tables were dropped in phase 2 (2026-10-09, `career/migrations/0026_drop_legacy_course_models.py`). They were not shape-compatible with `courses.Course` (separate per-pathway tables,
cutoffs as rows, no `Institution` link), so there was nothing to copy across.

**Eligibility rule:** only **Degree** uses cutoff points (cluster points vs `CourseOffering.cutoff_points`). Diploma, Certificate/Artisan (TVET), KMTC and TTC never use cutoff points — they compare the KCSE mean grade with `Course.minimum_mean_grade` (pathway default when blank), plus `subject_requirements` where a course has them.

## Infrastructure / operational gaps

Now resolved (previously listed as gaps): dependency vulnerability scanning
(`.github/workflows/dependency-audit.yml`), Content-Security-Policy headers
(`kuccpss.middleware.ContentSecurityPolicyMiddleware`), and `.env.example` sync
(`CLOUDINARY_URL`, `GOOGLE_CLIENT_ID`, `VAPID_*` now present).

- Periodic jobs run in-process via `kuccpss/scheduler.py` (no qcluster/cron on Render):
  `check_pending_payments`, `release_abandoned_bookings`, mentorship reminders (sent once, tracked
  by `reminder_sent`, email + web push) and auto-complete, every 10 min under a Postgres advisory lock, started per gunicorn worker by
  `post_worker_init`. Each cycle pings `KEEPALIVE_URL/health/` so Render's free tier stays awake. Log purges run on each deploy from `build.sh`.
- No automated cron processes `WithdrawalRequest` rows beyond the synchronous request-time call —
  `mentorship_housekeeping` handles abandoned-booking release and session reminders/completion.
- Refund status after IntaSend accepts a chargeback is not tracked (no chargeback webhook handler);
  the session is marked refunded once the request is accepted.
