# URL Map

All routes below were read directly from each app's `urls.py` plus [kuccpss/urls.py](../kuccpss/urls.py)
(the root URLconf). Auth requirement column reflects decorators actually present on the view
(`@login_required`, staff-only checks, etc.) — "Public" means no decorator was found.

## Root routes ([kuccpss/urls.py](../kuccpss/urls.py))

| Path | View | Name | Auth |
|---|---|---|---|
| `health/` | `health_check` | health_check | Public |
| `sw.js` | `serve_sw` | service_worker | Public |
| `robots.txt` | `serve_robots` | robots_txt | Public |
| `llms.txt` | `serve_llms` | llms_txt | Public |
| `sitemap.xml` | Django `sitemap` view | — | Public |
| `offline/` | `TemplateView` → offline.html | offline | Public |
| `cn-staff/` | `admin.site.urls` | — | Staff (Django admin) — **note: not `/admin/`** |
| `` | `public_home_view` | home | Public (redirects to dashboard after 4 guest visits) |
| `dashboard/` | `accounts.views.dashboard_view` | dashboard_root | Public (guest preview) / full for auth |
| `career.html` | `RedirectView` → `/career/` | — | Public |
| `api/search/` | `kuccpss.search_views.api_search_suggest` | api_search_suggest | Public |
| `api/email-lead/` | `accounts.views.email_lead_capture` | email_lead_capture | Public |
| DEBUG only | `/errors/404/`, `/errors/500/` | — | Dev-only |

`+static(MEDIA_URL, ...)` appended for dev media serving.

**Included app URLconfs** (all namespaced except where noted):
`accounts/` (also duplicated by direct `django.contrib.auth.urls` and `allauth.urls` includes —
see [SECURITY.md](SECURITY.md) note), `clusterpoints/`, `clusters/`, `institutions/`, `courses/`,
`career/`, `resources/`, `predictor/`, `payments/`, `analytics/`, `mentorship/`.

## accounts (`/accounts/`, `app_name="accounts"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `login/` | `LoginView` | login | Public |
| `logout/` | `logout_view` | logout | Public |
| `register/` | `RegisterView` | register | Public |
| `verify-email/<str:token>/` | `email_verify_view` | email_verify | Public |
| `change-password/` | `change_password_view` | change_password | `@require_recent_auth` |
| `re-auth/` | `re_auth_view` | re_auth | `@login_required` |
| `dashboard/` | `dashboard_view` | dashboard | Public (guest preview) / full for auth |
| `profile/` | `profile_update_view` | profile | `@login_required` |
| `saved-courses/` | `saved_courses_view` | saved_courses | `@login_required` |
| `save-course/<int:course_id>/` | `toggle_save_course` | toggle_save_course | `@login_required` |
| `save-career/<int:profile_id>/` | `toggle_save_career` | toggle_save_career | `@login_required` |
| `shortlist/` | `shortlist_view` | shortlist | `@login_required` |
| `comparison/` | `course_comparison_view` | comparison | `@login_required` |
| `shortlist/toggle/<int:course_id>/` | `shortlist_toggle` | shortlist_toggle | `@login_required` |
| `shortlist/notes/<int:course_id>/` | `shortlist_update_notes` | shortlist_notes | `@login_required` |
| `shortlist/rank/<int:course_id>/` | `shortlist_set_rank` | shortlist_rank | `@login_required` |
| `shortlist/export/pdf/` | `export_shortlist_pdf` | shortlist_pdf | `@login_required` |
| `notifications/` | `notifications_view` | notifications | `@login_required` |
| `notifications/mark-read/` | `mark_notifications_read` | mark_notifications_read | `@login_required` |
| `notifications/<int:notif_id>/read/` | `mark_notification_read` | mark_notification_read | `@login_required` |
| `notifications/broadcast/` | `broadcast_notification_view` | broadcast_notification | Staff-only |
| `push/subscribe/` | `push_subscribe` | push_subscribe | `@login_required` |
| `staff/team/` | `staff_team_view` | staff_team | Superuser-only |
| `` (include) | `allauth.urls` | — | — |
| `terms/`, `about/`, `privacy/`, `faq/`, `how-it-works/` | static views | resp. names | Public |
| `referral/` | `referral_view` | referral | `@login_required` |
| `affiliate/` | `affiliate_dashboard` | affiliate_dashboard | `@login_required` (404 if no AffiliateProfile) |
| `affiliate/withdraw/` | `request_affiliate_payout` | affiliate_withdraw | `@login_required @require_recent_auth` |
| `applications/`(+add/edit/delete) | Application CRUD | applications/application_* | `@login_required` |

## clusterpoints (`/clusterpoints/`, `app_name="clusterpoints"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `calculator/` | `kcse_calculator_view` | calculator | Public (guest session flow) / persists for auth |
| `export/` | `export_cluster_pdf` | export_cluster_pdf | `@login_required` |
| `export/full/` | `export_full_results_pdf` | export_full_results_pdf | `@login_required` |
| `recalculate/` | `recalculate_view` | recalculate | `@login_required`, POST-only |
| `admin-analytics/` | `admin_analytics` | admin_analytics | Staff-only |
| `eligible/` | `eligible_courses_view` | eligible_courses | Public/gated by payment |
| `share/create/` | `share_calculator_create` | share_calculator_create | `@login_required`, AJAX |

Rate-limited by `HeavyEndpointRateLimitMiddleware`: `POST /clusterpoints/` (calculator) 20/10min;
`GET /clusterpoints/eligible-courses/` 30/10min.

## clusters (`/clusters/`, `app_name="clusters"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `cluster_list` | cluster_list | Public, `@cache_page(1200s)` |
| `create/` | `cluster_create` | cluster_create | `@login_required` |
| `<slug:slug>/` | `cluster_detail` | cluster_detail | Public |
| `<slug:slug>/courses/` | `cluster_courses` | cluster_courses | Public/gated by payment |
| `<slug:slug>/edit/` | `cluster_edit` | cluster_edit | `@login_required` |

Note: `clusters/views.py` defines `subject_group_create`/`subject_group_edit` but neither is
wired into `clusters/urls.py` — likely orphaned/unused views (flagged in
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)).

## courses (`/courses/`, `app_name="courses"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `course_types_list` | course_types_list | Public, `@cache_page(900s)` |
| `<slug:type_slug>/` | `course_type_detail` | course_type_detail | Public |
| `<slug:type_slug>/<slug:category_slug>/` | `course_category_detail` | course_category_detail | Public |
| `<slug:type_slug>/<slug:category_slug>/<slug:course_slug>/` | `course_detail` | course_detail | Public |
| `<slug:type_slug>/<slug:course_slug>/` | `course_detail` | course_detail_no_category | Public |
| `.../review/` (both forms) | `submit_course_review` | submit_course_review[_no_category] | `@login_required`, POST |

## institutions (`/institutions/`, `app_name="institutions"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `institution_types_list` | institution_types_list | Public, `@cache_page(900s)` |
| `<slug:type_slug>/` | `institution_type_detail` | institution_type_detail | Public |
| `<slug:type_slug>/<slug:institution_slug>/` | `institution_detail` | institution_detail | Public |
| `<slug:type_slug>/<slug:institution_slug>/review/` | `submit_institution_review` | submit_institution_review | `@login_required`, POST |

## career (`/career/`, `app_name="career"`) — 30 patterns

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `home` | home | Public |
| `kcse-input/` | `kcse_input` | kcse_input | Public |
| `course/<int:match_id>/` | `course_detail` | course_detail | Public |
| `filter-matches/` | `filter_matches` | filter_matches | Public |
| `ai-recommendations/` | `ai_recommendations` | ai_recommendations | Public/session-based |
| `ajax/validate-tvet-subjects/` | `ajax_validate_tvet_subjects` | — | Public, AJAX |
| `ajax/update-admission/` | `ajax_update_admission` | — | Public, AJAX |
| `search-courses/` | `search_courses` | search_courses | Public |
| `export-matches/` | `export_matches_csv` | export_matches_csv | Public/session-based |
| `profiles/` | `career_profiles_list` | career_profiles_list | Public |
| `profiles/<slug:slug>/` | `career_profile_detail` | career_profile_detail | Public |
| `quiz/` | `quiz_view` | quiz_view | Public |
| `quiz/results/` | `quiz_results_view` | quiz_results_view | Public |
| `degree/` | `degree_entry` | degree_entry | Public |
| `degree/calculate/` | `degree_calculate` | degree_calculate | Public, rate-limited (10/10min POST) |
| `degree/options/` | `degree_options` | degree_options | Public |
| `degree/upload/` | `degree_upload` | degree_upload | Public — OCR/Vision AI call |
| `degree/paste/` | `degree_paste` | degree_paste | Public |
| `degree/manual/` | `degree_manual` | degree_manual | Public |
| `input/<str:pathway>/` | `pathway_input` | pathway_input | Public |
| `loading/<str:pathway>/` | `loading_page` | loading_page | Public |
| `results/` | `career_results` | career_results | Public/session-based, payment-gated |
| `results/pdf/quick/` | `career_results_pdf_quick` | pdf_quick | Public/session-based |
| `results/pdf/report/` | `career_results_pdf_detailed` | pdf_report | Public/session-based |
| `ajax/ai-insight/` | `ajax_ai_insight` | — | Public, AJAX, credit-gated |
| `ajax/ai-chat/` | `ajax_ai_chat` | — | Public, AJAX, credit-gated |
| `chat/` | `career_chat` | career_chat | Public, credit-gated |
| `submission/confirm/` | `confirm_submission` | confirm_submission | Public/session-based |
| `submission/recalculate/` | `recalculate_view` | recalculate | Public/session-based |
| `clear/` | `clear_session` | clear_session | Public |
| `share/create/` | `share_result_create` | share_result_create | Public |
| `share/<uuid:token>/` | `shared_result_view` | shared_result | Public |

Rate-limited by `HeavyEndpointRateLimitMiddleware`: `POST /career/` → 10/10min.

## mentorship (`/mentorship/`, `app_name="mentorship"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `directory` | directory | Public |
| `courses-for-institution/` | `courses_for_institution` | courses_for_institution | Public, AJAX |
| `become-mentor/` | `become_mentor` | become_mentor | `@login_required` |
| `become-mentor/success/` | `become_mentor_success` | become_mentor_success | Public |
| `dashboard/` | `mentor_dashboard` | dashboard | `@login_required` (must be approved mentor) |
| `dashboard/slots/add/` | `add_slots` | add_slots | `@login_required`, POST |
| `dashboard/slots/add-week/` | `add_weekly_slots` | add_weekly_slots | `@login_required`, POST |
| `dashboard/slots/<int:slot_id>/delete/` | `delete_slot` | delete_slot | `@login_required` |
| `mentor/<int:mentor_pk>/` | `mentor_profile` | mentor_profile | Public |
| `mentor/<int:mentor_pk>/book/` | `book_session` | book_session | `@login_required` |
| `checkout/<uuid:token>/` | `checkout` | checkout | `@login_required`(implicit via session ownership) |
| `checkout/<uuid:token>/pay/` | `initiate_payment` | initiate_payment | `@login_required`, POST, AJAX |
| `checkout/<uuid:token>/verify-manual/` | `verify_payment_manual` | verify_payment_manual | `@login_required`, POST |
| `webhook/payment/` | `payment_webhook` | payment_webhook | `@csrf_exempt`, **no signature check** |
| `checkout/<uuid:token>/status/` | `session_status` | session_status | Public, AJAX poll |
| `dashboard/edit/` | `edit_mentor_profile` | edit_profile | `@login_required` (approved mentors only) |
| `session/<uuid:token>/` | `session_detail` | session_detail | mentee/mentor/staff only |
| `session/<uuid:token>/complete/` | `complete_session` | complete_session | mentor only |
| `session/<uuid:token>/rate/` | `rate_session` | rate_session | `@login_required`, mentee only |
| `session/<uuid:token>/cancel/` | `cancel_session` | cancel_session | `@login_required`, mentee/mentor |
| `my-sessions/` | `my_sessions` | my_sessions | `@login_required` |
| `session/<uuid:token>/calendar.ics` | `download_ics` | download_ics | `@login_required`, mentee/mentor |
| `dashboard/withdraw/` | `request_withdrawal` | request_withdrawal | `@require_recent_auth`, POST |
| `dashboard/withdraw-application/` | `withdraw_application` | withdraw_application | `@login_required`, POST |

## payments (`/payments/`, `app_name="payments"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `required/` | `payment_required` | payment_required | `@login_required` |
| `history/` | `payment_history` | payment_history | `@login_required` |
| `initiate/` | `initiate_payment` | initiate_payment | `@login_required`, POST, AJAX |
| `webhook/mpesa/` | `mpesa_webhook` | mpesa_webhook | `@csrf_exempt`, POST — **HMAC signature verified** |
| `status/<int:payment_id>/` | `payment_status` | payment_status | `@login_required` |
| `verify/<int:payment_id>/` | `verify_payment` | verify_payment | `@login_required` |
| `pending/` | `pending_payment_for_feature` | pending_payment | `@login_required` |
| `verify-code/` | `verify_by_transaction_code` | verify_by_transaction_code | `@login_required`, POST |

## predictor (`/predictor/`, `app_name="predictor"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `predictor_index` | index | Public — single-page app, no detail/POST routes |

## resources (`/resources/`, `app_name="resources"`)

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `resource_list` | resource_list | Public |
| `articles/` | `article_list` | article_list | Public |
| `articles/<slug>/` | `article_detail` | article_detail | Public |
| `kuccps-calendar/` | `kuccps_calendar` | kuccps_calendar | Public |
| `how-to-guides/` | `how_to_guides` | how_to_guides | Public |
| `feedback/submit/` | `submit_feedback` | submit_feedback | Public, POST |
| `<slug:slug>/` | `resource_detail` | resource_detail | Public (catch-all, must be last) |

## analytics (`/analytics/`, `app_name="analytics"`) — staff-only dashboards

| Path | View | Name | Auth |
|---|---|---|---|
| `` | `analytics_dashboard` | dashboard | Staff-only |
| `export/` | `export_csv` | export_csv | Staff-only |
| `live-feed/` | `live_feed_json` | live_feed | Staff-only |
| `mentors/` | `mentor_analytics` | mentor_analytics | Staff-only |
| `affiliates/` | `affiliate_analytics` | affiliate_analytics | Staff-only |
| `pwa-install/` | `pwa_install` | pwa_install | Public, `@csrf_exempt`, POST |
| `heartbeat/` | `heartbeat` | heartbeat | Public, POST |
| `payments/` | `payments_overview` | payments | Staff-only |
| `pages/` | `pages_analytics` | pages | Staff-only |
| `actions/` | `actions_analytics` | actions | Staff-only |
| `users/<uuid:user_pk>/` | `user_timeline` | user_timeline | Staff-only |
| `insights/` | `insights_dashboard` | insights | Staff-only |
| `calculator/` | `calculator_analytics` | calculator_analytics | Staff-only |
| `career-engine/` | `career_engine_analytics` | career_engine_analytics | Staff-only |
| `conversion/` | `conversion_analytics` | conversion_analytics | Staff-only |
| `retention/` | `retention_analytics` | retention_analytics | Staff-only |
| `ai-chat/` | `ai_chat_analytics` | ai_chat_analytics | Staff-only |

`staff_only = user_passes_test(lambda u: u.is_active and u.is_staff, login_url='/accounts/login/')`
guards every dashboard view.

## Notable routing oddities

1. `/accounts/` is mounted **three times** in `kuccpss/urls.py`: once via `accounts.urls`
   (which itself already `include()`s `allauth.urls`), once via `django.contrib.auth.urls`, and
   once again directly via `allauth.urls`. Django resolves by list order, so `accounts.urls`
   patterns win on name collisions, but the duplicate `allauth.urls` include is redundant.
2. `/dashboard/` is registered at the project root (`dashboard_root`) in addition to
   `/accounts/dashboard/` (`accounts:dashboard`) — both point to the same view function.
3. Admin is served at `/cn-staff/`, not the Django default `/admin/`.
