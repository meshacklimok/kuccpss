# TODO — Prioritised Backlog

Format: `[ ]` not done | `[x]` done | `[~]` in progress

---

## P0 — Blockers (Fix Before Launch)

- [ ] Configure email backend (SMTP / SendGrid) so verification emails are actually sent (console backend is set, not production-ready)
- [ ] Remove the `is_verified = True` short-circuit in `accounts/views.py` RegisterView (currently bypasses email verification)
- [x] Set `MEDIA_ROOT` and `MEDIA_URL` in settings so uploaded logos/PDFs are served
- [ ] Add `STATICFILES_DIRS` and run `collectstatic` for production
- [ ] Set `ALLOWED_HOSTS` and `DEBUG = False` for production
- [ ] Rotate `SECRET_KEY` — current one is the insecure default, committed to code
- [ ] Remove hardcoded `OPENAI_API_KEY` placeholder from settings — use environment variable
- [x] Fix `TIME_ZONE` double-definition in settings.py — removed duplicate UTC line; now consistently `Africa/Nairobi`
- [x] Fix Unicode en-dash (U+2013) garbled characters in cluster descriptions — replaced with ` -` across all affected clusters (12A, 13A, 15B–15G, 20A, 3E, 4A, 5B, 5C, 6B, 9B, 11A)
- [ ] Fix cluster requirements data gaps — update descriptions for 4 clusters with missing/placeholder data (need official KUCCPS PDF):
  - **1A (Law)**: `KUCCPS sub-cluster 1A` — placeholder, no real data
  - **2A (Business)**: truncated (`MAT ALTERNATIVE A/B -`) — cut off mid-sentence during PDF extraction
  - **2B (Hospitality/Tourism)**: `KUCCPS sub-cluster 2B` — placeholder
  - **3D (Social Sciences)**: `KUCCPS sub-cluster 3D` — placeholder

---

## P1 — Core Features (MVP)

- [ ] Wire up real OpenAI call in `career/engine.py` (see API_NOTES.md)
- [ ] Scope `StudentCourseMatch` records to the logged-in user (currently saves globally)
- [ ] Build full-results PDF export (all clusters on one page)
- [ ] Add KCSE result history page — let users compare multiple past calculations
- [ ] Add anonymous/guest calculator flow (no login required to try)
- [ ] Fix: verification email token is created in RegisterView but email is never dispatched — add `send_verification_email()` utility

---

## P2 — Important Improvements

- [ ] Merge `career/models.py` course system with `courses/models.py` (see DECISIONS.md #4)
- [x] Add institution search page — `?q=` filter on institution type detail page
- [x] Add course search page — `?q=` filter on course type and category detail pages
- [x] Add custom 404 and 500 error pages
- [x] Seed all TVET programmes (Diploma L6, Certificate L5, Artisan L4, Craft L3) from KUCCPS PDFs
- [x] Seed TTC programmes (DSTE PDF — 79 courses, 88 offerings, 36 institutions)
- [x] Confirm KMTC programmes fully seeded (33 courses, 342 offerings at 88 campuses)
- [x] Fix TVET level mapping contamination (Craft/Artisan/Certificate cross-seeding)
- [x] Fix course detail 404 after level moves — view now redirects using correct URL namespace
- [ ] Add county-based filtering for KMTC and TTC campuses (88 KMTC campuses seeded — location data needed)
- [ ] Populate `cutoff_points` for TVET/TTC/KMTC courses (currently 0 — PDFs don't include historical cutoffs; use KUCCPS portal data)
- [ ] Populate minimum subject requirements for TVET courses (reference: `TVET_CLUSTER_DOCUMENT_2025.pdf`)
- [ ] Link TVET/TTC/KMTC courses to clusters (currently no `cluster` FK set on seeded courses)
- [ ] Populate CareerInsight data (demand level, average salary) for major courses
- [ ] Add cutoff trend chart (year-on-year for a course/university pair)
- [ ] Admin UI for suspending/unsuspending users

---

## P2 (continued) — Payments & Resources

- [x] Build Resources views and templates — views, templates, admin, URLs all complete; navbar updated to dropdown with Guides & Articles links
- [ ] Integrate Daraja M-Pesa API (Payment + Transaction models are stubs)
- [ ] Enforce feature gating in views based on Payment records

---

## P3 — Nice to Have

- [ ] Course comparison tool (compare 2–3 courses side-by-side)
- [ ] Share results via link (shareable token-based URL)
- [ ] Mobile-responsive UI audit
- [ ] Switch from SQLite to PostgreSQL
- [ ] Docker / deployment config (Procfile or Dockerfile)
- [ ] Write tests for cluster points calculation (critical formula)
- [ ] Add rate limiting to login and registration views
- [ ] Mark notifications as read (endpoint missing; model supports it)
- [ ] Populate CareerProfile and CareerInsight data for major Kenyan courses
