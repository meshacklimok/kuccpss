# Code Flow — Step-by-Step User Journeys

This doc traces full request/response paths through the codebase for the app's core user flows.
For the underlying route table see [URL_MAP.md](URL_MAP.md); for models touched see
[DATABASE.md](DATABASE.md); for per-file detail see [FILE_EXPLANATIONS.md](FILE_EXPLANATIONS.md).

## 1. Registration → Login → Dashboard

```mermaid
sequenceDiagram
    participant U as User (browser)
    participant V as accounts.views.RegisterView
    participant F as UserRegistrationForm
    participant DB as accounts.User
    participant E as email_utils.send_branded_email
    U->>V: POST /accounts/register/
    V->>F: validate (email domain/MX check, 4-char min password)
    F-->>V: valid
    V->>DB: create User (is_active=True, is_verified=False)
    V->>DB: create EmailVerificationToken
    V->>E: send_branded_email (verification link)
    V->>DB: Referral.attribute_from_session (if ?ref= present)
    V->>U: log user in immediately + redirect to dashboard
    U->>V: GET /accounts/verify-email/<token>/
    V->>DB: mark token used, User.is_verified=True
```

The user is logged in **before** email verification completes — verification only flips a flag,
it does not gate dashboard access. Google OAuth (`allauth`) skips this entirely: `accounts/signals.py`
auto-sets `is_verified=True` on social signup.

`dashboard_view` (`accounts/views.py`) then aggregates: recommended courses (from the user's latest
`ClusterCalculationResult`s), cluster-points chart data, `CourseShortlist`, `Application` timeline,
`SiteFeedback` prompt, trending courses (`courses/trends.py`, 1h cache), `CourseSpotlight`.

## 2. KCSE Cluster Points Calculator

```mermaid
flowchart TD
    A["GET /clusterpoints/calculator/"] --> B["KCSEForm: grade dropdown per Subject"]
    B --> C{"POST — authenticated?"}
    C -- guest --> D["calculate_clusters_anonymous()\n(in-memory, session-stashed)"]
    C -- yes --> E["persist UserKCSEResult + SubjectResult"]
    E --> F["calculate_all_clusters()\ninside transaction.atomic()"]
    F --> G["update_or_create ClusterCalculationResult\nper cluster (101-120)"]
    D --> H["render results accordion\n(guest state restored after signup)"]
    G --> H
    H --> I{"payment gate\n(payments.services.has_paid_for_feature)"}
    I -- unpaid --> J["payment_required.html / paywall_overlay.html\nM-Pesa STK push polling"]
    I -- paid/exempt --> K["full eligible-course detail\n+ PDF export"]
```

Formula (`clusterpoints/services.py::_weighted_cp`, canonical — see [CLAUDE.md](../CLAUDE.md)):
```
cluster_points = 48 × sqrt( (core_midpoint_marks / 400) × (aggregate_total / 84) )
```
Each cluster's `subject_groups` (ordered by priority) are filled by picking the best not-yet-used
subject per slot; a required slot that can't be filled forces `weighted = 0.0`.

## 3. Career Guidance Engine — full pathway flow

```mermaid
flowchart TD
    A["career:home — pick pathway\n(Degree/Diploma/TVET/KMTC/TTC)"] --> B["career:kcse_input or pathway_input"]
    B --> C{"Degree: entry method"}
    C -- manual --> D["degree_manual (reuses clusterpoints.forms.KCSEForm)"]
    C -- upload --> E["degree_upload: PyMuPDF rasterize\n+ GPT-4o Vision OCR"]
    C -- paste --> F["degree_paste: regex-parsed pasted cluster points"]
    D --> G["degree_calculate: review/confirm grades"]
    E --> G
    G --> H["career.engine.career_guidance_engine()"]
    B -- non-degree --> H
    H --> I["dispatch to match_degree/diploma/tvet/kmtc/ttc_courses()\n(career/models.py, legacy Course system)"]
    I --> J["generate_ai_recommendation()\n(STUB — placeholder text)"]
    I --> K["career_results_v2.html\nfilters, WhatsApp share, payment-gate blur"]
    K --> L{"paid?"}
    L -- no --> M["blurred preview + paywall_overlay.html"]
    L -- yes --> N["full results + PDF export (quick/detailed)"]
```

Non-degree pathways match against the **legacy** `career.models.TVETCourse`/`KMTCourse`/`TTCCourse`
— a separate system from `courses.models.Course` (see [DATABASE.md](DATABASE.md) two-course-systems
note). AI chat (`career:chat`) is a parallel flow: searches `AIKnowledgeEntry` first, falls back to
an OpenAI chat completion, gated by `AIChatCredit`/`AICallLog` and `CareerConfig.ai_enabled`.

## 4. Payment (IntaSend M-Pesa STK push) — the shared gate mechanism

```mermaid
sequenceDiagram
    participant U as Browser (payment_required.html / paywall_overlay.html)
    participant V as payments.views
    participant S as payments.services
    participant IS as IntaSend API
    participant W as payments.views.mpesa_webhook
    U->>V: POST /payments/initiate/ {phone, feature}
    V->>S: initiate_stk_push()
    S->>IS: POST /payment/mpesa-stk-push/
    IS-->>S: invoice_id
    V->>V: create Payment (status=pending, checkout_id=invoice_id)
    loop every 3s, up to 40 attempts (2 min)
        U->>V: GET /payments/status/<id>/
        V-->>U: {status: pending}
    end
    IS->>W: POST /payments/webhook/mpesa/ (X-IntaSend-Signature header)
    W->>W: verify HMAC-SHA256 (compare_digest) — 403 if invalid
    W->>W: Payment.status = completed
    W->>W: if feature has AI credits: top up AIChatCredit
    W->>W: lock_submission_on_payment() — prevents free recalculation
    W->>W: email branded PDF receipt
    alt feature not in AFFILIATE_EXCLUDED_FEATURES
        W->>W: credit AffiliateCommission to referrer
    end
    U->>V: GET /payments/status/<id>/ → {status: completed}
    V-->>U: redirect to unlocked feature
```

Manual fallback if the webhook never arrives: user pastes their M-Pesa SMS code →
`verify_by_transaction_code` matches against `Transaction.mpesa_ref`. **Note:** this fallback path
(and `verify_payment`) does **not** credit affiliate commissions — only the webhook path does (see
[IMPLEMENTATION_STATUS.md](IMPLEMENTATION_STATUS.md)).

## 5. Mentorship booking → payment → session lifecycle

```mermaid
flowchart TD
    A["mentorship:directory — browse mentors"] --> B["mentor_profile — view slots"]
    B --> C["book_session: race-check slot,\ncreate MentorshipSession(status=pending_payment)"]
    C --> D["checkout: same STK-push flow as §4\n(feature=mentorship_booking, api_ref=session.token)"]
    D --> E{"which webhook fires first?"}
    E -- "payments:mpesa_webhook (signed)" --> F["inline duplicated confirmation logic\ndoes NOT call _maybe_auto_pay_mentor"]
    E -- "mentorship:payment_webhook (UNSIGNED)" --> G["_confirm_session_after_payment()\ncalls _maybe_auto_pay_mentor"]
    F --> H["session.status = confirmed\nmentor.wallet_balance += payout"]
    G --> H
    H --> I["email + ICS + in-app Notification + push"]
    I --> J["session occurs"]
    J --> K["complete_session (mentor) / rate_session (mentee)"]
    H --> L{"wallet_balance >= MENTOR_AUTO_PAY_THRESHOLD (500, hardcoded default)?"}
    L -- yes, via path G only --> M["send_mentor_payout() — IntaSend B2C"]
```

The unsigned `mentorship:payment_webhook` endpoint is a **confirmed security gap** (see
[SECURITY.md](SECURITY.md) §3): a booking's UUID `token` is already visible in the checkout URL, so
anyone who observes it can POST directly to this endpoint and confirm the session — and trigger
auto-payout — without ever paying.

## 6. Affiliate/referral attribution → commission → payout

```mermaid
flowchart LR
    A["Affiliate shares link with ?ref=CODE"] --> B["ReferralMiddleware stores code in visitor session"]
    B --> C["Visitor registers"]
    C --> D["accounts.signals.on_user_signed_up\nReferral.attribute_from_session()"]
    D --> E["Referred user makes ANY paid-feature payment\n(except mentorship_booking, ai_chat_access)"]
    E --> F["payments.views.mpesa_webhook computes\ncommission = rate% x payment.amount"]
    F --> G["AffiliateCommission created (idempotent)\naffiliate.wallet_balance += commission"]
    G --> H["accounts:affiliate_dashboard — view stats"]
    H --> I["request_affiliate_payout (@require_recent_auth)\nbounded by SiteSetting['affiliate_min_withdrawal']"]
    I --> J["payments.services.send_affiliate_payout()\nIntaSend B2C"]
```

## 7. Full request lifecycle (every request)

```mermaid
flowchart TD
    A["Incoming request"] --> B["GracefulErrorMiddleware\n(catches unhandled exceptions -> 500.html, logs to Sentry)"]
    B --> C["HeavyEndpointRateLimitMiddleware\n(429 on breach for /clusterpoints/, /career/ POSTs)"]
    C --> D["SlowRequestLogMiddleware\n(logs requests exceeding a threshold)"]
    D --> E["DisableHttp3Middleware\n(strips Alt-Svc — Kenyan ISP UDP/QUIC issues)"]
    E --> F["Django auth/session/CSRF middleware"]
    F --> G["PageTrackingMiddleware\n(writes PageViewLog, upserts SessionLog)"]
    G --> H["ReferralMiddleware\n(captures ?ref=CODE into session)"]
    H --> I["URL resolution (kuccpss/urls.py -> app urls.py)"]
    I --> J["View (function or class-based)"]
    J --> K["Template render (extends base.html\nvia 9 registered context processors)"]
    K --> L["Response"]
```

See [DJANGO_ARCHITECTURE.md](DJANGO_ARCHITECTURE.md) for the exact `MIDDLEWARE` ordering and each
class's implementation detail.

## 8. Career quiz flow

```mermaid
flowchart LR
    A["career:quiz_view — answer QuizQuestion/QuizOption"] --> B["QuizSubmission + QuizAnswer rows"]
    B --> C["score against CareerProfile tags"]
    C --> D["quiz_results_view — top 6 matches"]
    D --> E["_generate_quiz_ai_summary — OpenAI 2-sentence narration\n(gpt-4o-mini default, 120 max_tokens)"]
```

## Cross-references

- The dual `get_client_ip()` implementations (§7's `PageTrackingMiddleware` uses first-XFF-entry,
  the rate limiter uses last-XFF-entry) mean the same request can be "seen" as two different client
  IPs by different parts of the stack — see [SECURITY.md](SECURITY.md) §9.
- Every AI call site (§3, §8) wraps the OpenAI call in a broad try/except that degrades to
  templated/KB-only text on failure — no raw API error ever reaches the user. See
  [API_AND_SERVICES.md](API_AND_SERVICES.md).
