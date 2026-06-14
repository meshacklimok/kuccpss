# Key Design Decisions

Records *why* major choices were made. Read this before refactoring or "improving" anything listed here.

---

## 1. Custom User Model with UUID Primary Key
**Decision:** `accounts.User` replaces Django's default `auth.User`. PK is UUID, login is email-only.

**Why:** Django's default User uses integer PKs (enumerable/guessable) and username-based login, which doesn't fit a Kenyan education platform where students identify by email. UUID PKs prevent user enumeration attacks.

**Impact:** All foreign keys to users must use `settings.AUTH_USER_MODEL`, never `auth.User` directly. Changing this later would require wiping all tables.

---

## 2. Cluster Points Formula Is Fixed
**Decision:** The weighted formula `48 × sqrt( (core/48) × (aggregate/84) )` must not be changed.

**Why:** This is the official KUCCPS formula used by the Kenyan government. Any deviation would give students incorrect results and potentially mislead their university applications.

**Impact:** Do not "optimise", simplify, or adjust the formula without explicit confirmation that KUCCPS has changed it officially.

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

## 6. Email Verification Is Mandatory
**Decision:** New users must verify their email before they can log in (`is_verified = False` on registration).

**Why:** Prevents fake accounts and ensures students receive important notifications at a valid email.

**Impact:** The email sending code is currently a TODO stub. Until a real email backend is configured, `is_verified` is set to `True` immediately on registration (short-circuit in RegisterView) — this must be fixed before production.

---

## 7. django-allauth for Social Auth
**Decision:** Google OAuth is handled by django-allauth rather than a custom OAuth flow.

**Why:** allauth handles token refresh, account linking, and email collision edge cases. Building this from scratch would be high-risk for a security-sensitive feature.

**Impact:** allauth URL patterns must remain included in `kuccpss/urls.py`. Do not remove `allauth.account.middleware.AccountMiddleware` from MIDDLEWARE.

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
