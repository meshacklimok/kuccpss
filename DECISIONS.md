# Key Design Decisions

Records *why* major choices were made. Read this before refactoring or "improving" anything listed here.

---

## 1. Custom User Model with UUID Primary Key
**Decision:** `accounts.User` replaces Django's default `auth.User`. PK is UUID, login is email-only.

**Why:** Django's default User uses integer PKs (enumerable/guessable) and username-based login, which doesn't fit a Kenyan education platform where students identify by email. UUID PKs prevent user enumeration attacks.

**Impact:** All foreign keys to users must use `settings.AUTH_USER_MODEL`, never `auth.User` directly. Changing this later would require wiping all tables.

---

## 2. Cluster Points Formula Uses Midpoint Marks (Not Grade-Point Fraction)
**Decision:** The formula is `48 × sqrt( (core_midpoint_marks / 400) × (aggregate/84) )` — not the naive `(core_pts/48)` fraction.

**Why:** KUCCPS computes cluster points from midpoint raw marks per grade band (A=90.2, A-=77.5, B+=71.0, …, E=14.0), not from a simple grade-point fraction. Switched from the old approach in June 2026 after discovering the earlier `(pts×7/400)` formula gave wrong values vs official KUCCPS outputs. `GRADE_MIDPOINT_MARKS` dict in `clusterpoints/services.py` is the single source of truth. The shared `_weighted_cp()` helper is used by both the saved-result and anonymous calculators, and by `career/models.py`.

**Impact:** Do not change `GRADE_MIDPOINT_MARKS` values or switch back to the grade-point fraction approach. Any KUCCPS formula update must be confirmed officially before code changes.

---

## 3. Aggregate Total Uses Best-7 Rule
**Decision:** KCSE aggregate = Mathematics + best(English, Kiswahili) + next 5 best remaining subjects.

**Why:** This is the Kenya National Examinations Council (KNEC) rule for computing KCSE mean grade and aggregate. It is not configurable.

**Impact:** The order of subject selection in `recalc_total_points()` and `calculate_all_clusters()` must be preserved exactly.

---

## 4. Two Parallel Course Systems (Not Yet Merged)
**Decision:** `career/models.py` and `courses/models.py` exist as separate course systems.

**Why:** `career/models.py` was built first as a standalone career guidance module. `courses/models.py` was built later as a cleaner, institution-linked system. Merging requires migrating data and updating the career engine — not yet done.

**Impact:** Do not merge them without a deliberate migration plan. When adding course features, clarify which system is the target.

---

## 5. SubjectGroup with Required/Optional Flag
**Decision:** Subjects in a cluster are organised into `SubjectGroup` objects with a `required` boolean.

**Why:** In KUCCPS clusters, some subjects are mandatory (e.g. Mathematics in Engineering cluster) and others are chosen as best-of alternatives. The required flag drives which subjects are selected first in the core calculation.

**Impact:** Adding cluster subjects without the correct `required` flag will silently produce wrong cluster points.

---

## 6. Email Verification via Custom Token (Not allauth)
**Decision:** Email verification uses a custom `EmailVerificationToken` model and `send_mail()` in `RegisterView`, not allauth's built-in verification.

**Why:** The custom `RegisterView` was built before the allauth integration was complete. allauth's verification only covers social/allauth signups; the custom registration path needed its own flow. `is_verified` is set to `False` on register and `True` only after the user clicks the link.

**Email sending:** `send_mail()` uses Resend SMTP (`smtp.resend.com:465`) in production when `RESEND_API_KEY` env var is set. Falls back to `console.EmailBackend` in dev — emails print to the terminal, making them easy to find during development.

**Impact:** The `email_verify_view` at `/accounts/verify-email/<token>/` handles the click. The allauth `ACCOUNT_EMAIL_VERIFICATION` setting only affects allauth-managed signups (e.g. Google OAuth), not the custom registration flow.

---

## 7. django-allauth for Social Auth
**Decision:** Google OAuth is handled by django-allauth rather than a custom OAuth flow.

**Why:** allauth handles token refresh, account linking, and email collision edge cases. Building this from scratch would be high-risk for a security-sensitive feature.

**Impact:** allauth URL patterns must remain included in `kuccpss/urls.py`. Do not remove `allauth.account.middleware.AccountMiddleware` from MIDDLEWARE. `SOCIALACCOUNT_LOGIN_ON_GET = False` — changing this back to True re-introduces a CSRF risk.

---

## 8. ReportLab for PDF Export
**Decision:** Cluster result PDFs are generated with ReportLab directly in the view.

**Why:** ReportLab is the most straightforward pure-Python PDF library. No external service dependency.

**Impact:** Currently exports one cluster at a time. A full-results PDF (all clusters) would need a loop or a separate view — do not refactor the existing export view when adding this.

---

## 9. Cutoff Points as JSONField
**Decision:** `courses.Course.cutoff_points` is a JSONField (`{"2024": 65.0, "2023": 62.0}`).

**Why:** Cutoffs change every year. A JSONField avoids needing a separate `CourseCutoffHistory` table for the `courses` app (though the `career` app has one). Flexible and admin-editable.

**Impact:** Queries against specific years require JSON lookups (`cutoff_points__2024`). Don't convert to a related model without updating all template references.

---

## 10. Admin URL Obfuscated
**Decision:** Django admin is at `/cn-staff/`, not `/admin/`.

**Why:** Automated bots and brute-force scripts universally target `/admin/` on Django sites. Moving it reduces exposure without adding complexity.

**Impact:** Bookmark `/cn-staff/`. Do not revert to `/admin/`. Any internal docs or links pointing to `/admin/` must be updated.

---

## 11. Resend for Transactional Email
**Decision:** Production email is sent via Resend SMTP (`smtp.resend.com`, port 465 SSL).

**Why:** Resend has a 3,000 email/month free tier, simple SMTP setup that works with Django's built-in `send_mail()`, and good deliverability. No SDK required — just standard SMTP credentials.

**Setup:** `RESEND_API_KEY` env var on Render activates SMTP; if absent, Django falls back to `console.EmailBackend` so development works with zero configuration. Domain `careernext.co.ke` verified in Resend via TXT (SPF) and CNAME (DKIM) DNS records in TrueHost.

**Impact:** The `DEFAULT_FROM_EMAIL` env var sets the "from" address (default: `CareerNext <noreply@careernext.co.ke>`). Do not change `EMAIL_HOST_USER` — it must be the literal string `"resend"` for Resend's SMTP auth.

---

## 12. HTTP/3 Disabled in Middleware
**Decision:** `DisableHttp3Middleware` sets `alt-svc: clear` on every response.

**Why:** Render/Cloudflare advertises HTTP/3 (QUIC) via the `alt-svc` header. Some Kenyan ISPs (Safaricom, Airtel) block UDP traffic, which QUIC requires. Users on these networks get `ERR_FAILED`. Clearing `alt-svc` forces the browser to stay on HTTP/1.1 or HTTP/2.

**Impact:** Slight performance overhead (one header set per response, negligible). Remove this middleware only if Cloudflare is removed from the traffic path or Kenyan ISP UDP blocking is resolved.

---

## 14. Cloudinary for Media Storage in Production
**Decision:** Cloudinary (`cloudinary-storage` + `cloudinary` packages) handles media file storage in production when `CLOUDINARY_URL` env var is set; falls back to local `MEDIA_ROOT` in dev.

**Why:** Render's filesystem is ephemeral — files written to disk disappear on every deploy. Cloudinary provides persistent, CDN-served media storage with a generous free tier and no code changes required (drop-in Django storage backend).

**Impact:** `CLOUDINARY_URL` must be set in the production environment (format: `cloudinary://api_key:api_secret@cloud_name`). The app guards against a malformed `CLOUDINARY_URL` at startup (strips it if it doesn't start with `cloudinary://`). Do not use `DEFAULT_FILE_STORAGE` pointing to local storage in production.

---

## 15. MentorshipConfig + CareerConfig as Admin Singletons
**Decision:** Configurable platform settings (session price, payout rate, AI message limits, feature toggles) live in singleton DB models (`MentorshipConfig`, `CareerConfig`) rather than env vars or code constants.

**Why:** These values change frequently as the business operates — pricing experiments, free-tier adjustments, enabling/disabling features mid-season. Redeploying just to change a price or message limit is slow and risky. Admin singletons let the operator change these in real-time via `/cn-staff/`.

**Impact:** Always read price/limits from these models, not from settings.py or hardcoded constants. Both are `get_or_create`-style singletons — call `.load()` or `CareerConfig.get_solo()` to fetch them.

---

## 13. Mentorship Payout Split (70/30)
**Decision:** Mentor receives 70% of session fee; platform keeps 30%.

**Why:** Industry standard for marketplace platforms. The 30% covers M-Pesa transaction fees, platform infrastructure, and support costs.

**Impact:** `MentorshipSession.mentor_payout = amount * 0.70`. Do not change this without updating the payout calculation. `MentorProfile.wallet_balance` tracks accrued payouts; disbursement flow is not yet built.
