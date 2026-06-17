# Features

Status legend: ✅ Done | 🚧 In Progress | 📋 Planned | ❌ Blocked

---

## Authentication & Accounts
| Feature | Status | Notes |
|---|---|---|
| Email/password registration | ✅ | Custom User model, UUID PK |
| Email verification | ✅ | 24h token, one-time use |
| Email/password login | ✅ | Checks is_active, is_suspended, is_verified |
| Google OAuth login | ✅ | django-allauth, is_google_user flag |
| Remember me (7-day session) | ✅ | RememberToken stored in DB |
| Password change | ✅ | Re-authenticates session after change |
| Password reset (email) | ✅ | 2h token via allauth |
| Profile update | ✅ | Edits User fields directly (no Profile model) |
| Device session tracking | ✅ | DeviceSession per login |
| Login history / audit trail | ✅ | LoginHistory model |
| Account soft delete | ✅ | soft_delete() sets deleted_at + is_active=False |
| Terms & conditions page | ✅ | agreed_terms + terms_version fields |
| Send verification email | 🚧 | Token created but email not actually sent yet |
| Suspend/unsuspend (admin) | ✅ | Bulk admin actions: "Suspend selected users" and "Unsuspend selected users" added to UserAdmin |

---

## KCSE Calculator (clusterpoints)
| Feature | Status | Notes |
|---|---|---|
| KCSE grade input form | ✅ | KCSEForm with all subjects |
| Grade → points conversion | ✅ | GradePoint model, A=12 to E=1 |
| Aggregate total calculation | ✅ | Math + best lang + 5 best others, max 84; language-pool bug fixed 2026-06-11 |
| Cluster points calculation | ✅ | Weighted formula, all clusters |
| Results dashboard (per user) | ✅ | Latest result + all cluster results |
| PDF export (per cluster) | ✅ | ReportLab, A4 format |
| Admin analytics | ✅ | Total users, results, clusters calculated |
| Save/overwrite previous result | ✅ | Deletes old results on new submission |
| Guest/anonymous calculation | 📋 | Currently requires login |
| Compare multiple results | 📋 | History view not yet built |
| Full results PDF (all clusters) | 📋 | Currently exports one cluster at a time |

---

## Clusters
| Feature | Status | Notes |
|---|---|---|
| Cluster list/detail views | ✅ | clusters app with URLs |
| Subject groups within clusters | ✅ | SubjectGroup with required/optional flag |
| Auto-slug generation | ✅ | On Cluster.save() |
| Auto-number assignment | ✅ | Increments from last cluster number |
| Cluster image/icon/color | ✅ | Fields exist; UI integration TBD |
| Admin CRUD for clusters | ✅ | Via Django admin |
| Minimum subject requirements display | 🚧 | Shows for 57/61 clusters; 1A, 2B, 3D have no data (placeholder); 2A truncated — all need official KUCCPS PDF |
| Subject groups populated | ❌ | All 61 clusters have 0 SubjectGroups; calculator uses top-4 fallback |

---

## Institutions
| Feature | Status | Notes |
|---|---|---|
| Institution types list | ✅ | 5 coloured category cards (Public Uni, Private Uni, KMTC, TVET, TTC) with institution count |
| Institution type detail page | ✅ | Cards with abbreviation badge, location pin, course count; search via `?q=` |
| Institution detail page | ✅ | Courses grouped by type → category; cutoff/min-grade badge; sidebar with abbreviation, location, contacts |
| Abbreviation field | ✅ | CharField on Institution; back-filled for 30 public universities via seed command |
| Institution type icons & colours | ✅ | `icon`, `color_code`, `bg_color` on InstitutionType; seeded for all 5 types |
| PDF brochure upload | ✅ | FileField on Institution model |
| Search institutions | ✅ | `?q=` name filter on institution type detail page |
| Map / location display | 📋 | Only text location field currently |

---

## Courses
| Feature | Status | Notes |
|---|---|---|
| Course type list/detail | ✅ | Degree, Diploma, KMTC, TTC, TVET |
| Course category detail | ✅ | Subcategories per type |
| Course detail page | ✅ | Linked to institution + cluster; URL routing bug fixed 2026-06-11; redirects transparently on slug→type changes |
| Cutoff points per year | ✅ | JSONField: {"2024": 65, "2023": 62} — degree/uni courses only |
| KMTC minimum mean grade | ✅ | `minimum_mean_grade` field on Course (e.g. "C+") |
| KMTC subject requirements | ✅ | `subject_requirements` JSONField; shown as slot/subjects/min-grade table |
| KMTC programme codes | ✅ | `programme_code` on CourseOffering (e.g. `5000K32`) |
| KMTC course detail (no cutoff table) | ✅ | Shows min grade, subject requirements, campuses list |
| TVET Diploma (L6) data | ✅ | 319 courses / 4,515 offerings seeded from `DIPLOMA_PROGRAMMES.pdf` |
| TVET Certificate (L5) data | ✅ | 159 courses / 4,947 offerings seeded from `CERTIFICATE_PROGRAMMES.pdf` |
| TVET Artisan Certificate (L4) data | ✅ | 68 courses / 2,738 offerings seeded from `ARTISAN_18_03_2024_RV2.pdf` |
| TVET Craft Certificate (L3) data | ✅ | 77 courses / 1,801 offerings seeded from `CRAFT_18_03_2024_RV2.pdf` |
| TTC programme data | ✅ | 83 courses / 141 offerings seeded from `DSTE_18_03_2024_RV2.pdf`; 36 TTC institutions |
| KMTC programme data | ✅ | 33 courses / 342 offerings at 88 campuses (seeded 2026-06-11, confirmed 2026-06-13) |
| TVET/TTC cutoff points | 📋 | Not in PDFs — need KUCCPS portal historical data |
| TVET minimum subject requirements | 📋 | Reference: `TVET_CLUSTER_DOCUMENT_2025.pdf`; not yet linked to Course model |
| Link TVET/TTC/KMTC courses to clusters | 📋 | `cluster` FK on Course not set for seeded TVET/TTC/KMTC courses |
| PDF upload per course | ✅ | course_pdfs/ upload path |
| Link degree courses to clusters | ✅ | FK to Cluster (university degree courses) |
| Course search | ✅ | `?q=` name filter on type and category detail pages |
| Filter courses by institution | 📋 | Not yet implemented |
| County-based campus filter (KMTC/TTC) | 📋 | 88 KMTC campuses exist; location data not yet populated |

---

## Career Guidance Engine
| Feature | Status | Notes |
|---|---|---|
| Pathway selection (Degree/Diploma/KMTC/TVET/TTC) | ✅ | career/home view |
| KCSE grade input for career matching | ✅ | career/kcse_input view |
| Degree course matching by cluster points | 🚧 | Logic in models.py; engine.py is stub |
| Diploma/KMTC/TVET/TTC matching by mean grade | 🚧 | Logic exists, engine.py is stub |
| Admission chance prediction | ✅ | VERY HIGH / HIGH / MEDIUM / LOW |
| AI recommendation text | 🚧 | Stub only; OpenAI not yet connected |
| Match results display + filtering | ✅ | Filter by university, admission chance, sort |
| Paginated results | ✅ | 15 per page |
| Course detail from match | ✅ | career/course_detail view |
| AI recommendation history | ✅ | Stored AIRecommendation objects |
| CSV export of matches | ✅ | career/export_matches_csv |
| AJAX TVET subject validation | ✅ | ajax_validate_tvet_subjects |
| AJAX live admission update | ✅ | ajax_update_admission |
| Career insights (salary, demand) | 📋 | Model exists, no data or UI yet |
| Real OpenAI integration | 📋 | See API_NOTES.md |
| Save matches per user (not session) | 📋 | Currently saves globally, not user-scoped |
| PDF export of career results | 📋 | Download matched courses as PDF from career engine |
| Course Comparison Tool | 📋 | Compare 2–3 courses side-by-side (cutoffs, requirements, institutions) |
| Career Mistake Detector | 📋 | Warn "This course does NOT match your KCSE subjects" before results |
| Grade simulator | 📋 | "What if I scored B+ instead of C in Chemistry?" re-run without re-entering |

---

## AI & Intelligence Features
| Feature | Status | Notes |
|---|---|---|
| AI Career Advisor (OpenAI) | 📋 | Conversational guidance via career/engine.py once OpenAI live |
| Placement Probability Score | 📋 | Predict likelihood of admission based on past KCSE distributions and competition per course |
| Cutoff Prediction Engine | 📋 | Predict next year's cutoff based on year-by-year intake trends |
| Admission Shock Predictor | 📋 | Warn "This cutoff is rising fast — you may not qualify next year" |
| AI Admission Strategy Builder | 📋 | Given grade + preferred course: auto-generate 1st / 2nd / 3rd choice + backup plan |
| Backup Plan Generator | 📋 | If student doesn't qualify for top course, auto-suggest alternatives (e.g. Medicine ❌ → Nursing, Clinical Medicine, Lab Tech) |
| Fail-Safe Career Path Engine | 📋 | Multi-step fallback paths: preferred course → diploma bridge → degree upgrade route |
| AI "Explain Like I'm 5" Mode | 📋 | Toggle: Simple / Normal / Advanced explanations (e.g. cluster formula explained as "your best 7 subjects decide your score") |
| AI Parent Mode | 📋 | Plain-language explanations for parents: "What does this course mean?", "Is it worth it?", "Job prospects in Kenya" |
| Hidden Talent Career Match | 📋 | Personality quiz → "You are best suited for Data Science, not Medicine" — viral shareable result |
| Alternative Subject Suggestions | 📋 | For weak subjects: suggest alternatives that open better cluster paths |
| Smart Course Recommendation Feed | 📋 | TikTok-style feed: "Top 5 courses for B+ students", "Low competition, high salary", "Hidden gem courses in Kenya" |

---

## Analytics & Insights
| Feature | Status | Notes |
|---|---|---|
| Admin Analytics Dashboard | 📋 | Track: most searched course, most viewed institution, most saved programme, most downloaded PDF |
| Placement Trends Dashboard | 📋 | Most applied courses, fastest growing careers, most competitive programmes year-on-year |
| Competition Pressure Indicator | 📋 | Per-course badge: Low / Medium / High / Extreme 🔥 competition level |
| Top Trending Courses Live Feed | 📋 | "Computer Science +32% this month" — creates urgency and social virality |
| Cutoff Trend Chart | 📋 | Year-on-year cutoff history chart per course/university pair |
| Peer Comparison | 📋 | "Among students with similar grades, 60% chose Medicine, 30% chose Engineering" |

---

## Career Planning Tools
| Feature | Status | Notes |
|---|---|---|
| Career Path Roadmaps | 📋 | Full journey maps: e.g. Doctor → KCSE → MBChB → Internship → Specialisation → Consultant → Salary growth |
| Multi-Path Planner | 📋 | Show 3 parallel paths: Safe (Nursing) / Balanced (Pharmacy) / Risky high-reward (Medicine) |
| Job Market Intelligence | 📋 | Demand levels, salary ranges, growth outlook per career in Kenya |
| Placement Reports (PDF) | 📋 | Downloadable PDF career report: matched courses, cluster scores, strategy, backup paths |
| Student Success Stories | 📋 | Alumni stories: "I scored C+ and got into KMTC Nursing — here's how" |
| Alumni Outcome Tracking | 📋 | Track where past users enrolled; surface anonymised aggregate outcomes |
| Reviews | 📋 | Students rate and review courses / institutions they applied to |

---

## Personalisation & Engagement
| Feature | Status | Notes |
|---|---|---|
| Personalised Dashboard | 📋 | Student-specific view: their chances, saved courses, alerts, recommended changes — "Netflix for careers" |
| Smart Alerts System | 📋 | Notify: cutoff changes, application deadline approaching, new matching courses added |
| Onboarding Walkthrough | 📋 | 3-step intro overlay / tooltip tour for first-time users |
| How-to Guides | 📋 | Step-by-step guides: how to apply on KUCCPS, how cluster points work, how to choose a course |

---

## Career Profiles
| Feature | Status | Notes |
|---|---|---|
| Career profiles list with search + demand filter | ✅ | career/career_profiles_list view, paginated 12/page |
| Career profile detail page | ✅ | career/career_profile_detail view with slug URL |
| Save/unsave a career profile | ✅ | toggle_save_career in accounts; SavedCareer model |
| Related careers sidebar | ✅ | 4 random profiles shown on detail page |
| Career assessment quiz | ✅ | QuizQuestion/QuizOption/QuizSubmission models; tag-based scoring |
| Quiz results (top matching profiles) | ✅ | quiz_results_view; top 6 profiles by tag score |
| Populate CareerProfile data | 📋 | Models exist; no real data loaded yet |
| Populate CareerInsight data | 📋 | Model exists (demand, salary); no data loaded |

---

## Saved Items & Applications
| Feature | Status | Notes |
|---|---|---|
| Save/unsave courses | ✅ | SavedCourse model; toggle_save_course AJAX endpoint |
| Saved courses list page | ✅ | accounts/saved_courses view |
| Save/unsave career profiles | ✅ | SavedCareer model; toggle_save_career AJAX endpoint |
| Application tracking (create/edit/delete) | ✅ | ApplicationTracking model; STATUS_CHOICES (draft→accepted/rejected) |
| Application list + detail views | ✅ | accounts app; login required |

---

## Notifications
| Feature | Status | Notes |
|---|---|---|
| Notification model | ✅ | TYPE_CHOICES: info/success/warning/deadline/system; is_read flag |
| Unread notification count in navbar | ✅ | Context processor: unread_notification_count |
| Notifications list view | ✅ | accounts/notifications view |
| Mark notification as read | ✅ | `mark_notifications_read` view + URL exist; notifications_view auto-marks all read on visit |

---

## Resources
| Feature | Status | Notes |
|---|---|---|
| Resource categories | ✅ | ResourceCategory model |
| Resource items (PDF / video / link) | ✅ | Resource model with download_count |
| Articles (content + tags) | ✅ | Article model with is_published flag |
| Resources views / templates | ✅ | resource_list, resource_detail, article_list, article_detail views and templates; category sidebar; search; tag filter; pagination |
| KUCCPS Application Calendar | ✅ | Static page at /resources/kuccps-calendar/ — 2025 & 2024 cycles, timeline layout, application checklist, tips sidebar |
| How-To Guides | ✅ | Static page at /resources/how-to-guides/ — 6 guides: cluster points formula, KUCCPS portal steps, course selection strategy, Degree vs KMTC vs TVET, revision windows, HELB basics |

---

## Payments (Stub)
| Feature | Status | Notes |
|---|---|---|
| Payment model | ✅ | FEATURE_CHOICES: cluster points, eligible courses, premium report, advanced analysis |
| M-Pesa Transaction model | ✅ | mpesa_ref, phone_number, raw_response JSONField |
| Live M-Pesa integration | 📋 | Stub only — no Daraja API calls yet |
| Feature gating by payment | 📋 | Payment records exist but no enforcement in views |

---

## Community & Communication
| Feature | Status | Notes |
|---|---|---|
| News Panel | 📋 | Platform updates, KUCCPS announcements, deadline alerts displayed on dashboard/homepage |
| Student-to-Admin Chat | 📋 | In-app messaging: students ask questions, admins respond |
| WhatsApp share button | ✅ | On career results filter bar — shows match count in pre-filled message |
| Shareable results link | 📋 | Token-based URL so results can be shared without login |
| Instagram-style result card | 📋 | Generated PNG showing top 3 matches (Pillow/canvas) |

---

## General / Infrastructure
| Feature | Status | Notes |
|---|---|---|
| Custom 404 / 500 pages | ✅ | Branded 404 (extends base) + standalone 500; preview at /errors/404/ and /errors/500/ in DEBUG mode |
| Dark mode toggle | ✅ | Moon/sun button in navbar; `body.dark` CSS class; preference saved to localStorage |
| Back to top button | ✅ | Fixed floating button on all pages; appears after 400px scroll |
| Static files setup | ✅ | STATICFILES_DIRS configured; static/css/style.css and static/js/main.js in place |
| Media files setup | ✅ | MEDIA_ROOT and MEDIA_URL configured in settings.py |
| PostgreSQL database | ✅ | Migrated from SQLite; 21,601 objects loaded to PostgreSQL 17 |
| Credentials in .env | ✅ | SECRET_KEY, DB credentials, OPENAI_API_KEY loaded from .env; .gitignore excludes it |
| GitHub repository | ✅ | Private repo under meshacklimok |
| Terms & Conditions update flow | 📋 | Currently static page; needs version tracking + re-acceptance prompt on update |
| Production settings | 📋 | DEBUG=True, ALLOWED_HOSTS=[] — dev only |
| Deployment config | 📋 | No Dockerfile / Procfile yet |
| Email backend config | 🚧 | Console backend set; needs SMTP/SendGrid for production |
| SEO & OpenGraph meta tags | 📋 | Course/institution detail pages need structured data (JSON-LD) |
| PWA / offline support | 📋 | Service worker + manifest for mobile install |
| Google Analytics / event tracking | 📋 | Page views, pathway selections, payment funnel |
| Rate limiting (login/register) | 📋 | Prevent brute force |
| Unit tests (cluster formula) | 📋 | Formula must never regress |
| Sentry error monitoring | 📋 | Production exception tracking |
