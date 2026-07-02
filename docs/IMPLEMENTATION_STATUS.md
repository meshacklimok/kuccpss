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
| Career engine dispatch | `career/engine.py::career_guidance_engine` — real dispatcher, not a stub, covers Degree/Diploma/TVET/KMTC/TTC. |
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

- **All 61 KUCCPS sub-clusters (numbers < 100) have zero `SubjectGroup` rows.** Only the 20
  master calculation clusters (101–120) are seeded by `clusters/management/commands/seed_clusters.py`.
  Course-matching/requirements display for sub-clusters may be relying on a top-4-subjects
  fallback rather than true per-cluster slots. See [DATABASE.md](DATABASE.md) and
  [FEATURES.md](FEATURES.md) §2.
- **TVET/TTC cutoff points and subject requirements** are largely unsourced — `Course.minimum_mean_grade`/
  `subject_requirements` rows are blank for most non-KMTC non-degree courses. Eligibility *logic*
  is correct; results will simply be less precise until this data-entry work is done.
- Clusters **1A, 2B, 3D** (and part of 2A) have placeholder requirement-description text rather
  than real KUCCPS requirement text (per [CHANGELOG.md](CHANGELOG.md)/TODO.md, unresolved
  as of the most recent dated changelog entry, 2026-06-30).

## 🚧 Stubbed / placeholder functionality

- **`career/models.py::generate_ai_recommendation()`** (the non-chat, results-page recommendation
  text) still returns placeholder text — confirmed by [API_NOTES.md](API_NOTES.md) as a known
  stub. AI chat and quiz-summary AI calls are real; this specific call site is not.
## ❌ Dead code

- **`clusterpoints/models.py::ClusterCalculationResult.calculate_cluster_points()`** — implements
  the old, forbidden fraction-based formula (`core_pts/48` instead of midpoint-marks). Never
  called by the live request path (`views.py` → `services.py`), but its presence is a latent-bug
  risk if anything ever calls it directly. **Do not use this method as a reference for the formula.**
- **`career/models.py`'s duplicate `career_guidance_engine()`** — same name/purpose as the live
  `career/engine.py` version; `career/views.py` imports only the `engine.py` copy.
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

## Two unmerged systems (structural, not a bug)

`career/models.py`'s legacy `Course`/`TVETCourse`/`KMTCourse`/`TTCCourse` and `courses/models.py`'s
unified `Course`/`CourseOffering` remain separate by design, bridged one-way (name-match only, dry-run
by default) via `career/management/commands/sync_career_clusters.py`. Per CLAUDE.md, do not merge
without explicit instruction — but any feature work touching "courses" must first determine which
system is in play. See [DATABASE.md](DATABASE.md) and [FEATURES.md](FEATURES.md) §4/§5.

## Infrastructure / operational gaps

Now resolved (previously listed as gaps): dependency vulnerability scanning
(`.github/workflows/dependency-audit.yml`), Content-Security-Policy headers
(`kuccpss.middleware.ContentSecurityPolicyMiddleware`), and `.env.example` sync
(`CLOUDINARY_URL`, `GOOGLE_CLIENT_ID`, `VAPID_*` now present).

- No scheduled job visibly purges old analytics logs (`analytics/tasks.py::purge_old_logs` exists
  but has no cron/management-command wiring found).
- No automated cron processes `WithdrawalRequest` rows beyond the synchronous request-time call —
  `mentorship_housekeeping` only handles session reminders/completion.
