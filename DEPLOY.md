# Deploy — Exact Steps

## Push to GitHub (every time you make changes)

```bash
git add <file1> <file2>      # stage specific files
git add -A                    # or stage everything (be careful)
git status                    # confirm what's staged
git commit -m "Your message"
git push origin master
```

Render auto-deploys from GitHub on every push to `master`. Wait ~2 min then check https://careernext.co.ke.

---

## After a Push — What Render Does Automatically

Render runs `build.sh` on every deploy:
```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate
```

You do **not** need to run these manually unless something failed.

---

## One-Off Commands (run in Render Shell)

Open: Render dashboard → careernext web service → **Shell**

```bash
# Apply migrations manually (if auto-migrate failed)
python manage.py migrate

# Seed payment features (only needed once, or after adding new features)
python manage.py seed_payment_features

# Create a superuser
python manage.py createsuperuser

# Collect static files manually
python manage.py collectstatic --noinput

# Open Django shell
python manage.py shell
```

---

## Environment Variables (Render dashboard → Environment)

| Variable | What it does | Required |
|---|---|---|
| `SECRET_KEY` | Django secret key | ✅ |
| `DJANGO_DEBUG` | Set to `False` | ✅ |
| `DATABASE_URL` | Render PostgreSQL URL | ✅ |
| `ALLOWED_HOSTS` | `careernext.co.ke,.onrender.com` | ✅ |
| `RESEND_API_KEY` | Transactional email (Resend SMTP) | ✅ |
| `OPENAI_API_KEY` | AI chat + OCR document scanner | ✅ |
| `INTASEND_PUBLISHABLE_KEY` | M-Pesa STK push | ✅ |
| `INTASEND_SECRET_KEY` | M-Pesa STK push + webhook verify | ✅ |
| `INTASEND_WEBHOOK_SECRET` | Webhook HMAC verification | ✅ |
| `CLOUDINARY_URL` | Media file storage (format: `cloudinary://key:secret@cloud`) | ✅ |
| `GOOGLE_CLIENT_ID` | Google OAuth | ✅ |
| `GOOGLE_SECRET` | Google OAuth | ✅ |
| `SENTRY_DSN` | Error monitoring | recommended |
| `GA_MEASUREMENT_ID` | Google Analytics | optional |
| `POSTHOG_JS_KEY` | PostHog analytics | optional |
| `VAPID_PUBLIC_KEY` | Web Push notifications | optional |
| `VAPID_PRIVATE_KEY` | Web Push notifications | optional |
| `DEFAULT_FROM_EMAIL` | From address (default: `CareerNext <noreply@careernext.co.ke>`) | optional |

---

## IntaSend Webhook Setup (do once)

1. Log into IntaSend dashboard → **Webhooks**
2. Add webhook URL: `https://careernext.co.ke/payments/webhook/mpesa/`
3. Copy the webhook secret → paste into `INTASEND_WEBHOOK_SECRET` env var on Render
4. Also add: `https://careernext.co.ke/mentorship/webhook/payment/` for mentorship session payments

---

## After Adding a New PaymentFeature

```bash
python manage.py seed_payment_features
```

Or add the feature manually in Django admin → `/cn-staff/` → Payment Features.

---

## Check the Site Is Working

After every deploy:
1. https://careernext.co.ke — home page loads
2. https://careernext.co.ke/clusterpoints/ — calculator loads
3. https://careernext.co.ke/career/ — career engine home loads
4. https://careernext.co.ke/cn-staff/ — admin loads
5. Register a new account → check email arrives
6. Run the calculator with real grades → results appear

---

## Rollback a Bad Deploy

```bash
# Locally — revert last commit
git revert HEAD
git push origin master

# Or on Render — go to Deploys tab → click "Rollback" on the last good deploy
```

---

## DNS / Domain (careernext.co.ke)

- Registrar: TrueHost
- DNS: Cloudflare (proxied → Render)
- SSL: Cloudflare handles TLS termination; Render sees HTTP behind the proxy
- `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` is set in settings so Django knows the connection is HTTPS

If the site goes down after a DNS change, wait up to 24h for propagation.
