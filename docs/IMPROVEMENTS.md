# Improvements

Suggestions only — no code in this repository was changed to produce this document. Each item
references the doc where the underlying finding is detailed. Ordered by category, roughly
priority-ordered within each category.

## Security

1. **Sign the mentorship webhook.** `mentorship:payment_webhook` accepts unsigned POSTs and can
   confirm a session (crediting a mentor's wallet, potentially triggering auto-payout) using only
   a UUID token already visible in the checkout URL. Either remove this endpoint (since
   `payments:mpesa_webhook` already handles mentorship `api_ref`s) or add the same HMAC-SHA256
   verification `payments:mpesa_webhook` already performs. This is the single highest-severity
   finding in the codebase — see [SECURITY.md](SECURITY.md) §3.
2. **Consolidate `get_client_ip()`.** Two disagreeing implementations exist (first-XFF-entry vs.
   last-XFF-entry). Since rate limiting already correctly uses the trustworthy last-entry
   convention, migrate `accounts/signals.py` and `PageTrackingMiddleware` to match, and extract a
   single shared helper so a third divergent copy can't appear later. See
   [SECURITY.md](SECURITY.md) §9.
3. **Reconcile password-strength rules.** `AUTH_PASSWORD_VALIDATORS` declares a 6-char minimum
   that nothing actually enforces; registration/change-password use a separate, un-synced 4-char
   check. Either route both flows through Django's `validate_password()` or delete the unused
   validator registration so the settings file isn't misleading.
4. **Add a Content-Security-Policy header** and consider `django-csp` — none is currently
   configured, and the app renders a fair amount of inline `<script>` (chart data, dark-mode
   toggle, PWA install prompts) that a CSP would need to account for.
5. **Add dependency vulnerability scanning** (`pip-audit` or GitHub Dependabot) to CI/deploy — none
   exists today, and `requirements.txt` pins are not audited automatically.

## Correctness / consistency

1. **Single-source the KCSE aggregate algorithm.** It is independently reimplemented in at least
   four places (`career/models.py::_compute_aggregate`, `clusterpoints/models.py::UserKCSEResult
   .recalc_total_points`, `clusterpoints/services.py`, `clusterpoints/views.py::_compute_aggregate`).
   Extract one canonical function (e.g. into `clusterpoints/services.py`, already the canonical
   home for the cluster-points formula) and have the other three import it. This is the most
   consequential maintainability risk in the codebase given the formula's business criticality —
   see [FILE_EXPLANATIONS.md](FILE_EXPLANATIONS.md) and [FEATURES.md](FEATURES.md) §2.
2. **Delete or clearly mark the dead formula in `clusterpoints/models.py`.**
   `ClusterCalculationResult.calculate_cluster_points()` implements the old, forbidden fraction-based
   formula and is unreachable from the live path — but its presence risks someone copying it as a
   reference. Either delete it or add a large warning comment pointing at `services.py`.
3. **Fix the AI knowledge base formula text.** `seed_knowledge.py`'s `AIKnowledgeEntry` describes
   the old fraction-based formula; CareerNext AI chat could recite it verbatim to a user. Re-seed
   with the correct midpoint-marks description.
4. **Unify mentorship payment confirmation.** `payments:mpesa_webhook` reimplements
   `mentorship._confirm_session_after_payment` inline instead of calling it, and the two have
   already drifted (`mpesa_webhook`'s copy doesn't trigger auto-payout). Extract one shared
   confirmation function both webhooks call.
5. **Extend affiliate-commission crediting to the fallback verification paths.** `verify_payment`
   and `verify_by_transaction_code` currently skip commission crediting entirely, meaning users who
   pay and manually confirm (rather than waiting for the webhook) never generate a commission for
   their referrer.
6. **Fix `WithdrawalRequest.status = "failed"`** — either add `"failed"` to `STATUS_CHOICES` or stop
   setting a value the choices don't recognize; currently breaks `get_status_display()` silently.
7. **Wire up the orphaned `clusters` subject-group views** (`subject_group_create`/`_edit`) or
   remove them if superseded by admin/import-export.
8. **Clean up the triple `/accounts/` URL mount** in `kuccpss/urls.py` and the duplicate root
   `dashboard/` route — cosmetic today but adds confusing, redundant URL surface.

## Performance

1. **Audit for N+1 queries** in the analytics dashboards and course/institution list views — the
   TODO.md already flags this as an open item; the heavy per-dashboard ORM aggregation in
   `analytics/views.py` (~1600 lines) is the most likely hotspot given its volume of annotated
   querysets.
2. **Schedule `analytics/tasks.py::purge_old_logs`.** It exists but nothing calls it — analytics
   tables (`PageViewLog`, `SessionLog`, `EventLog`, etc.) may be growing unbounded. Wire it into a
   cron/management command alongside `mentorship_housekeeping`.
3. **Consolidate duplicate PDF-styling code.** The NAVY/TEAL/EMERALD/AMBER/PURPLE/SLATE palette and
   header/footer drawing logic is copy-pasted across `clusterpoints/views.py`, `career/views.py`,
   and `payments/views.py`. A shared `pdf_utils.py` module would cut ~3x the maintenance burden for
   any future rebrand.
4. **Bump the service worker cache version deliberately.** `sw.js`'s `CACHE = 'careernext-v7'` must
   be manually incremented on any static-asset-affecting deploy; there's no build-time
   cache-busting. A content-hash-based cache name would remove this manual step.

## Maintainability

1. **Remove or document the confirmed dead code** listed in
   [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) (`career/models.py`'s duplicate
   `career_guidance_engine`, `courses/forms.py`/`institutions/forms.py`, unused `PasswordChangeForm`,
   dead `MentorshipSession.meet_link` column, unused `Course.cutoff_points`, `analytics/tasks.py`
   duplicating `analytics/utils.py`, `accounts/tasks.py`/`payments/tasks.py::send_payment_confirmation`).
   Dead code that closely resembles live code (e.g. two `career_guidance_engine` functions with the
   same name) is a real risk for a future contributor calling the wrong one.
2. **Introduce a shared "event name" constants module for analytics.** `EventLog.name` values
   (`calculator_run`, `ai_chat_message`, `ai_chat_paywall_hit`, etc.) are freeform strings scattered
   across many view files with no shared enum/constants — a typo silently breaks a dashboard metric
   with no error anywhere.
3. **Move the two unmerged course systems toward an explicit deprecation plan** (or document why
   they must stay separate long-term). `career/management/commands/sync_career_clusters.py`
   already bridges them one-way; a documented target-state (e.g. "career app migrates to
   `courses.Course` by Q_") would help future contributors avoid building new features against the
   legacy system.
4. **Fix `MentorRegistrationForm`'s hardcoded `institution_type_id__in=[2,3,4]`** — reference
   `InstitutionType` by a stable slug/name instead of raw PKs so re-seeding doesn't silently break
   mentor signup eligibility.
5. **Define `MENTOR_AUTO_PAY_THRESHOLD` explicitly in `settings.py`** rather than relying on an
   undocumented `getattr(..., 500)` default that a reader can't discover without grepping.
6. **Commit `resources/migrations/0010_seed_withdrawal_settings.py`** — confirmed untracked in git
   at the time of this documentation pass; deploying without it means the mentor/affiliate minimum
   withdrawal amounts are not yet admin-editable in production (though the code fallback values
   currently match, so this is low-urgency, not a live bug).

## Testing

1. **Add unit tests for the cluster-points formula and the aggregate algorithm.** These are the two
   most business-critical, most-duplicated calculations in the app and have zero dedicated
   correctness tests today. A single well-known-input/expected-output test suite would catch
   formula drift immediately (especially important once the aggregate logic is consolidated per
   the Correctness section above).
2. **Fill in the empty test stubs**: `payments/tests.py`, `institutions/tests.py`, `predictor/`
   (no `tests.py` at all). Payments in particular is money-moving logic with the app's most
   complex webhook/fallback branching and currently has no coverage.
3. **Add integration tests for the two-webhook mentorship confirmation path** specifically —
   given it's flagged as both a security gap and a correctness inconsistency, a regression test
   would catch any future attempt to "fix" one path without the other.

## UI/UX & accessibility

1. **Fix `mentorship/directory.html`'s dark-mode selector.** It uses `[data-bs-theme="dark"]`
   instead of the site-wide `body.dark` pattern, so it likely doesn't respond to the dark-mode
   toggle used everywhere else — a visible inconsistency for any user who enables dark mode and
   visits the mentor directory.
2. **Deduplicate the paywall polling UI/JS.** `payment_required.html` (`pr*` namespace) and
   `paywall_overlay.html` (`pw*` namespace) implement near-identical M-Pesa polling state machines
   independently — a shared JS module (or a single parameterized template) would halve the
   surface area for payment-UI bugs.
3. **Build the `degree_paste` pathway** or remove its dead URL/view/template if it's been
   deprioritized — a partially-wired route is worse for discoverability than no route.

## Scalability / deployment

1. [TODO.md](TODO.md) already tracks the headline scalability item (migrating off Render
   Free's ~40-concurrent-user ceiling) — no additional finding to add here beyond confirming the
   plan exists and is detailed.
2. **Sync `.env.example` with actual production requirements.** It currently omits
   `CLOUDINARY_URL`, `GOOGLE_CLIENT_ID`/`GOOGLE_SECRET`, and `VAPID_*` despite
   [DEPLOY.md](DEPLOY.md) documenting them as required/optional — a new developer following only
   `.env.example` would hit confusing runtime gaps (missing media storage, no Google login, no push).

## Monitoring

1. **Add a scheduled job for stale/pending payment cleanup verification.** `payments/tasks.py
   ::check_pending_payments` (stale >30min → failed) exists — confirm it's actually scheduled
   (via django-q2) in production, since several other `tasks.py` files in this codebase were found
   to be unwired duplicates of synchronous logic.
2. **Surface the "which webhook confirmed this mentorship session" fact in logs/Sentry breadcrumbs**
   so the confirmed webhook-divergence issue (auto-payout depends on which webhook fires) is at
   least observable in production until it's fixed in code.

## Documentation

1. **Keep this `docs/` set and the hand-maintained docs (`ARCHITECTURE.md`, `DECISIONS.md`, `FEATURE_STATUS.md`,
   `TODO.md`, `CHANGELOG.md`) in sync going forward** — this documentation pass found them broadly
   accurate and detailed, which is a real asset; the main risk is drift as the two unmerged course
   systems, the webhook duplication, and the aggregate-algorithm duplication get fixed (or don't).
2. Consider a short **"known issues" section in the root README/CLAUDE.md** pointing at
   [IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md) so new contributors see the confirmed-bugs
   list before they rediscover it independently.
