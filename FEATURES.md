# Features

Status legend: ✅ Done | 🚧 In Progress | 📋 Planned | ❌ Blocked | [-] Dropped

---

## Authentication & Accounts
| Feature | Status | Notes |
|---|---|---|
| Email/password registration | ✅ | Custom User model, UUID PK |
| Email verification | ✅ | 24h token, one-time use; send_mail() via Resend SMTP in prod |
| Email/password login | ✅ | Checks is_active, is_suspended, is_verified |
| Google OAuth login | ✅ | django-allauth, is_google_user flag |
| Remember me (7-day session) | ✅ | RememberToken stored in DB |
| Password change | ✅ | Re-authenticates session after change |
| Password reset (email) | ✅ | 2h token via allauth; works once email backend configured |
| Profile update | ✅ | Edits User fields directly (no Profile model) |
| Device session tracking | ✅ | DeviceSession per login |
| Login history / audit trail | ✅ | LoginHistory model |
| Account soft delete | ✅ | soft_delete() sets deleted_at + is_active=False |
| Terms & conditions page | ✅ | agreed_terms + terms_version fields |
| Suspend/unsuspend (admin) | ✅ | Bulk admin actions in UserAdmin |
| Email lead capture | ✅ | `/api/email-lead/` endpoint; pre-registration interest collection |

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
| Cutoff trend prediction on results | ✅ | predictor app; trend arrows + band prediction per cluster |
| Guest/anonymous calculation | ✅ | Works without login; session stashed; CTA prompts registration |
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
| Course detail page | ✅ | Linked to institution + cluster; redirects transparently on slug→type changes |
| Cutoff points per year | ✅ | JSONField: {"2024": 65, "2023": 62} — degree/uni courses only |
| KMTC minimum mean grade | ✅ | `minimum_mean_grade` field on Course (e.g. "C+") |
| KMTC subject requirements | ✅ | `subject_requirements` JSONField; shown as slot/subjects/min-grade table |
| KMTC programme codes | ✅ | `programme_code` on CourseOffering (e.g. `5000K32`) |
| TVET Diploma (L6) data | ✅ | 319 courses / 4,515 offerings seeded from `DIPLOMA_PROGRAMMES.pdf` |
| TVET Certificate (L5) data | ✅ | 159 courses / 4,947 offerings seeded |
| TVET Artisan Certificate (L4) data | ✅ | 68 courses / 2,738 offerings seeded |
| TVET Craft Certificate (L3) data | ✅ | 77 courses / 1,801 offerings seeded |
| TTC programme data | ✅ | 83 courses / 141 offerings; 36 TTC institutions |
| KMTC programme data | ✅ | 33 courses / 342 offerings at 88 campuses |
| Course search | ✅ | `?q=` name filter on type and category detail pages |
| PDF upload per course | ✅ | course_pdfs/ upload path |
| Link degree courses to clusters | ✅ | FK to Cluster (university degree courses) |
| TVET/TTC cutoff points | 📋 | Not in PDFs — need KUCCPS portal historical data |
| TVET minimum subject requirements | 📋 | Reference: `TVET_CLUSTER_DOCUMENT_2025.pdf`; not yet linked to Course model |
| Link TVET/TTC/KMTC courses to clusters | 📋 | `cluster` FK on Course not set for seeded records |
| Filter courses by institution | 📋 | Not yet implemented |
| County-based campus filter (KMTC/TTC) | 📋 | 88 KMTC campuses exist; location data not yet populated |

---

## Cutoff Predictor (predictor app)
| Feature | Status | Notes |
|---|---|---|
| PredictionConfig model | ✅ | Per-cluster config with band multipliers |
| predict_all_for_student() | ✅ | Called from clusterpoints results view; attaches trend data |
| Standalone predictor page | ✅ | `/predictor/` — select cluster, see trend analysis |
| Trend arrows on calculator results | ✅ | TREND_ICON/TREND_COLOR/TREND_TIP from predictor.services |
| Career engine integration | ✅ | predict_cutoff() called in career degree results view |

---

## Career Guidance Engine
| Feature | Status | Notes |
|---|---|---|
| Pathway selection (Degree/Diploma/KMTC/TVET/TTC) | ✅ | career/home view |
| KCSE grade input for career matching | ✅ | career/kcse_input view; unified accordion UI |
| Document Scanner (OCR) | ✅ | GPT-4o vision; supports JPG/PNG/PDF; detects KCSE slips vs cluster point docs |
| Degree course matching by cluster points | 🚧 | Logic in models.py; engine.py is stub |
| Diploma/KMTC/TVET/TTC matching by mean grade | 🚧 | Logic exists, engine.py is stub |
| Admission chance prediction | ✅ | VERY HIGH / HIGH / MEDIUM / LOW |
| AI recommendation text | 🚧 | Stub only; OpenAI not yet connected |
| Match results display + filtering | ✅ | Filter by university, admission chance, sort |
| Paginated results | ✅ | 15 per page |
| Course detail from match | ✅ | career/course_detail view |
| AI recommendation history | ✅ | Stored AIRecommendation objects |
| CSV export of matches | ✅ | career/export_matches_csv |
| Payment gate on results | ✅ | Blurred preview cards + lock card until payment |
| AJAX TVET subject validation | ✅ | ajax_validate_tvet_subjects |
| AJAX live admission update | ✅ | ajax_update_admission |
| Career insights (salary, demand) | 📋 | Model exists, no data or UI yet |
| Real OpenAI integration | 📋 | See API_NOTES.md |
| Save matches per user (not session) | 📋 | Currently saves globally, not user-scoped |
| PDF export of career results | 📋 | Download matched courses as PDF from career engine |
| Course Comparison Tool | 📋 | Compare 2–3 courses side-by-side |
| Grade simulator | 📋 | "What if I scored B+ instead of C?" re-run |

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

## Mentorship (mentorship app)
| Feature | Status | Notes |
|---|---|---|
| MentorProfile model | ✅ | OneToOne to User; course + institution FK; bio, WhatsApp, wallet, ratings |
| TimeSlot model | ✅ | Date + start_time; unique per mentor; is_booked flag |
| MentorshipSession model | ✅ | UUID token; links mentor + mentee + slot; status flow; rating + review |
| Mentor approval workflow | ✅ | is_approved flag + rejection_reason; admin-controlled |
| Mentor payout tracking | ✅ | wallet_balance, total_earned, mentor_payout (70% of session fee) |
| Mentor directory (public list) | 📋 | Views/templates not yet built |
| Session booking flow | 📋 | Views/templates not yet built |
| M-Pesa payment for sessions | 📋 | payment_ref + phone_used fields exist; Daraja not wired |
| Post-session rating | 📋 | Fields exist; rating form not yet built |
| Mentor earnings dashboard | 📋 | wallet_balance tracked; no dashboard view yet |

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
| Mark notification as read | ✅ | notifications_view auto-marks all read on visit |

---

## Resources
| Feature | Status | Notes |
|---|---|---|
| Resource categories | ✅ | ResourceCategory model |
| Resource items (PDF / video / link) | ✅ | Resource model with download_count |
| Articles (content + tags) | ✅ | Article model with is_published flag |
| Resources views / templates | ✅ | resource_list, resource_detail, article_list, article_detail; category sidebar; search; tag filter; pagination |
| KUCCPS Application Calendar | ✅ | Static page at /resources/kuccps-calendar/ — 2025 & 2024 cycles, timeline layout |
| How-To Guides | ✅ | Static page at /resources/how-to-guides/ — 6 guides |

---

## Payments
| Feature | Status | Notes |
|---|---|---|
| Payment model | ✅ | FEATURE_CHOICES: cluster points, eligible courses, premium report, advanced analysis |
| PaymentFeature model | ✅ | Per-feature is_enabled toggle; admin-controllable via `/cn-staff/` |
| M-Pesa Transaction model | ✅ | mpesa_ref, phone_number, raw_response JSONField |
| Career results payment gate UI | ✅ | Blurred preview + lock card; "Unlock My Results" CTA |
| Live M-Pesa integration | 📋 | Stub only — Daraja STK push not yet wired |
| Daraja webhook handler | 📋 | Confirm payment → unlock session → mark Payment completed |
| Payment success page | 📋 | Show unlocked results after confirmed payment |
| Feature gating enforcement | 📋 | Payment records exist but no enforcement in views yet |

---

## Community & Communication
| Feature | Status | Notes |
|---|---|---|
| WhatsApp share button | ✅ | On career results filter bar — shows match count in pre-filled message |
| Student Success Stories | ✅ | 6 curated stories on homepage; tagged by grade/pathway/institution |
| News Panel | 📋 | Platform updates, KUCCPS announcements on dashboard |
| Shareable results link | 📋 | Token-based URL so results can be shared without login |
| Urgency / deadline banner | ✅ | Site-wide red/amber/blue countdown bar June–Aug; auto-hides outside 60-day window; color escalates at 21d/7d; CTA differs for auth vs guest; sessionStorage dismiss |

---

## PWA & Mobile
| Feature | Status | Notes |
|---|---|---|
| Service worker | ✅ | `static/js/sw.js` (cache-v5); cache-first for `/` and `/static/`; network-first for dynamic pages |
| Web app manifest | ✅ | `static/manifest.json`; start_url `/dashboard/`; standalone display |
| Web Push notifications | ✅ | VAPID keys; push event handler in SW; notification click → opens URL |
| PWA install prompt | ✅ | Shows on all devices; 7-day cooldown first dismiss, 4-day after |
| Splash screen (first open only) | ✅ | Graduation cap animation + "CareerNext" shimmer; sessionStorage guard; standalone mode only |
| Offline fallback | ✅ | SW serves cached homepage when network unavailable |

---

## General / Infrastructure
| Feature | Status | Notes |
|---|---|---|
| Custom 404 / 500 pages | ✅ | Branded 404 + standalone 500; preview at /errors/404/ and /errors/500/ in DEBUG mode |
| Dark mode toggle | ✅ | Moon/sun button in navbar; `body.dark` CSS class; localStorage |
| Back to top button | ✅ | Fixed floating button; appears after 400px scroll |
| Static files | ✅ | WhiteNoise; `staticfiles/` collected on deploy |
| Media files | ✅ | MEDIA_ROOT and MEDIA_URL configured |
| PostgreSQL database | ✅ | Render managed; 21,601+ objects |
| Credentials in env vars | ✅ | All secrets in Render environment variables; .env for local dev |
| GitHub repository | ✅ | Private repo under meshacklimok |
| Deployment config | ✅ | `render.yaml` + `build.sh`; gunicorn WSGI server |
| Email backend | ✅ | Resend SMTP in production (RESEND_API_KEY env var); console in dev |
| Rate limiting | ✅ | 5 registrations/IP/hour; 10 login failures/IP/15min |
| Security headers | ✅ | HSTS (1yr), secure cookies, MIME-sniff protection; production-only block |
| Admin URL obfuscated | ✅ | `/cn-staff/` instead of `/admin/` |
| HTTP/3 disabled | ✅ | DisableHttp3Middleware → `alt-svc: clear` (fixes ERR_FAILED on Kenyan ISPs) |
| Search autocomplete | ✅ | `/api/search/` endpoint; client-side filtering on course/institution search |
| Referral tracking | ✅ | ReferralMiddleware captures referral source to User model |
| SEO meta tags | ✅ | OpenGraph + Twitter Card on key pages |
| Google Analytics / event tracking | 📋 | Page views, pathway selections, payment funnel |
| Sentry error monitoring | ✅ | sentry-sdk[django] 2.x; init guarded by SENTRY_DSN env var; filters 404/403/CSRF noise; 10% trace sampling; no PII |
| Unit tests (cluster formula) | 📋 | Formula must never regress |
| N+1 query audit | 📋 | Eligible courses + career results loops need select_related pass |
