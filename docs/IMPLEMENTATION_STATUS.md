# Implementation Status

A consolidated Completed vs. Remaining/Incomplete/Broken view of the codebase, synthesized from
every other doc in this set (especially [FEATURES.md](FEATURES.md), [DATABASE.md](DATABASE.md),
[SECURITY.md](SECURITY.md), [FILE_EXPLANATIONS.md](FILE_EXPLANATIONS.md)). Where the root
[FEATURES.md](../FEATURES.md)/[TODO.md](../TODO.md) already track a status legend, this doc adds
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
  than real KUCCPS requirement text (per root [CHANGELOG.md](../CHANGELOG.md)/TODO.md, unresolved
  as of the most recent dated changelog entry, 2026-06-30).

## 🚧 Stubbed / placeholder functionality

- **`career/models.py::generate_ai_recommendation()`** (the non-chat, results-page recommendation
  text) still returns placeholder text — confirmed by [API_NOTES.md](../API_NOTES.md) as a known
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

| Issue | Where | Detail |
|---|---|---|
| Unsigned mentorship webhook | `mentorship/views.py::payment_webhook` | No HMAC signature check — a guessed/observed session UUID token can be POSTed to confirm payment and credit a mentor's wallet without ever paying. See [SECURITY.md](SECURITY.md) §3. |
| Duplicated, diverging webhook logic | `payments/views.py::mpesa_webhook` vs. `mentorship/views.py::_confirm_session_after_payment` | The payments-app webhook reimplements mentorship confirmation inline and does **not** call `_maybe_auto_pay_mentor` — mentor auto-payout depends on which webhook IntaSend happens to hit. |
| Affiliate commission not credited on fallback paths | `payments/views.py::verify_payment`, `verify_by_transaction_code` | Only `mpesa_webhook` credits `AffiliateCommission`; manual-verification fallbacks silently skip it. |
| `WithdrawalRequest.status = "failed"` not in `STATUS_CHOICES` | `mentorship/models.py` | Saves without DB error (Django doesn't enforce choices at the DB layer) but breaks `get_status_display()` and choices-based admin filters. |
| `get_client_ip()` disagreement | `accounts/views.py` (last XFF entry) vs. `accounts/signals.py` (first XFF entry) | Rate limiting uses the trustworthy last-entry convention; login-history/analytics IP logging uses the spoofable first-entry convention. See [SECURITY.md](SECURITY.md) §9. |
| Password-strength validator never invoked | `kuccpss/settings.py` `AUTH_PASSWORD_VALIDATORS` (6-char min) vs. `accounts/forms.py::validate_password_strength` (4-char min, actually used) | Django's registered validator is dead for registration/change-password; both flows bypass it. |
| AI knowledge base has the wrong formula | `career/management/commands/seed_knowledge.py` | Seeds an `AIKnowledgeEntry` restating the old fraction-based cluster-points formula, not the midpoint-marks version actually implemented. CareerNext AI chat could explain the formula incorrectly if it surfaces this entry verbatim. |
| Hardcoded OCR model | `career/views.py::degree_upload` | Uses a hardcoded `model='gpt-4o'` instead of the admin-configurable `CareerConfig.ai_model_name` used by every other AI call site. |
| `advanced_analysis` feature default mismatch | `payments/migrations/0004_seed_payment_features.py` (enabled) vs. `payments/management/commands/seed_payment_features.py` (disabled) | Re-running the command with `--force` would silently flip production behavior. |
| Duplicate `/accounts/` URL mounts | `kuccpss/urls.py` | Includes `accounts.urls` (which itself includes `allauth.urls`), then separately `django.contrib.auth.urls`, then separately `allauth.urls` again. Harmless (resolved by list order) but redundant. |
| Duplicate `dashboard/` route | `kuccpss/urls.py` | Registered at project root (`dashboard_root`) in addition to `accounts:dashboard`, pointing to the same view. |
| Orphaned `clusters` views | `clusters/views.py::subject_group_create`/`subject_group_edit` | Defined but not wired into `clusters/urls.py`. |
| `mentorship/directory.html` dark-mode selector | Template | Uses `[data-bs-theme="dark"]` instead of the site-wide `body.dark` pattern — likely does not respond to the dark-mode toggle. |
| Duplicated paywall polling JS | `templates/payments/payment_required.html` vs. `paywall_overlay.html` | Near-identical M-Pesa polling logic under separate JS namespaces (`pr*` vs `pw*`). |
| No shared PDF-styling module | `clusterpoints/views.py`, `career/views.py`, `payments/views.py` | Branded palette/header/footer drawing logic copy-pasted independently in 3 files. |
| `MentorRegistrationForm` hardcoded institution-type IDs | `mentorship/forms.py` | `institution_type_id__in=[2,3,4]` — fragile if seed IDs ever change. |
| `MENTOR_AUTO_PAY_THRESHOLD` never defined | `kuccpss/settings.py` | Read via `getattr(..., 500)` everywhere; always silently uses the 500 default. |
| Untracked migration | `resources/migrations/0010_seed_withdrawal_settings.py` | Confirmed untracked in git as of this documentation pass — functionally harmless (code fallbacks match seeded values) but should be committed before deploy. |

## 📋 No test coverage / thin coverage

- `payments/tests.py` — empty stub.
- `institutions/tests.py` — effectively empty (3 lines).
- `courses/tests.py` — smoke/review flows only, not chart logic, category-fallback redirects, or `trends.py`.
- `predictor/` — no `tests.py` at all.
- No formula-correctness unit tests exist anywhere for the cluster-points calculation or the
  aggregate algorithm, despite both being business-critical and independently reimplemented in 4
  places (see [FILE_EXPLANATIONS.md](FILE_EXPLANATIONS.md)).

## Two unmerged systems (structural, not a bug)

`career/models.py`'s legacy `Course`/`TVETCourse`/`KMTCourse`/`TTCCourse` and `courses/models.py`'s
unified `Course`/`CourseOffering` remain separate by design, bridged one-way (name-match only, dry-run
by default) via `career/management/commands/sync_career_clusters.py`. Per CLAUDE.md, do not merge
without explicit instruction — but any feature work touching "courses" must first determine which
system is in play. See [DATABASE.md](DATABASE.md) and [FEATURES.md](FEATURES.md) §4/§5.

## Infrastructure / operational gaps

- No scheduled job visibly purges old analytics logs (`analytics/tasks.py::purge_old_logs` exists
  but has no cron/management-command wiring found).
- No automated cron processes `WithdrawalRequest` rows beyond the synchronous request-time call —
  `mentorship_housekeeping` only handles session reminders/completion.
- No dependency vulnerability scanning (`pip-audit`/`safety`/Dependabot) found in the repo.
- No Content-Security-Policy headers configured.
- `.env.example` omits `CLOUDINARY_URL`, `GOOGLE_CLIENT_ID`/`GOOGLE_SECRET`, and `VAPID_*` keys
  despite [DEPLOY.md](../DEPLOY.md) documenting them as required/optional for production.
