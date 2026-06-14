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
| Suspend/unsuspend (admin) | 📋 | Model field exists, no admin UI yet |

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
| Mark notification as read | 📋 | Model supports it; no endpoint yet |

---

## Resources
| Feature | Status | Notes |
|---|---|---|
| Resource categories | ✅ | ResourceCategory model |
| Resource items (PDF / video / link) | ✅ | Resource model with download_count |
| Articles (content + tags) | ✅ | Article model with is_published flag |
| Resources views / templates | ✅ | resource_list, resource_detail, article_list, article_detail views and templates; category sidebar; search; tag filter; pagination |

---

## Payments (Stub)
| Feature | Status | Notes |
|---|---|---|
| Payment model | ✅ | FEATURE_CHOICES: cluster points, eligible courses, premium report, advanced analysis |
| M-Pesa Transaction model | ✅ | mpesa_ref, phone_number, raw_response JSONField |
| Live M-Pesa integration | 📋 | Stub only — no Daraja API calls yet |
| Feature gating by payment | 📋 | Payment records exist but no enforcement in views |

---

## General / Infrastructure
| Feature | Status | Notes |
|---|---|---|
| Custom 404 / 500 pages | ✅ | Branded 404 (extends base) + standalone 500; preview at /errors/404/ and /errors/500/ in DEBUG mode |
| Static files setup | 📋 | STATIC_URL set, STATICFILES_DIRS not configured |
| Media files setup | ✅ | MEDIA_ROOT and MEDIA_URL configured in settings.py |
| Production settings | 📋 | DEBUG=True, ALLOWED_HOSTS=[] — dev only |
| PostgreSQL migration | 📋 | Currently SQLite |
| Deployment config | 📋 | No Dockerfile / Procfile yet |
| Email backend config | 🚧 | Console backend set; needs SMTP/SendGrid for production |
| Fix TIME_ZONE double-definition | ✅ | Removed duplicate UTC line; consistently `Africa/Nairobi` |
