"""
Copy site content (mentors, quiz, career profiles, FAQs, calendar, configs, course
offering cutoffs…) from one database to another without relying on primary keys.

    python manage.py sync_content --export   # local: writes data/live_content.json (+ data/live_media/)
    python manage.py sync_content            # live:  upserts it; skipped if this exact file was already applied
    python manage.py sync_content --force    # live:  apply even if already applied
    python manage.py sync_content --with-portal  # build.sh: also run import_kuccps_portal once per data change

Rows are matched on natural keys (slug, email, unique fields), so it's safe to run
against a database whose ids differ. Quiz questions/options and offering cutoffs
mirror local exactly (stale live rows are deleted / cleared); everything else is upsert-only. User activity (sessions, payments, logins,
quiz submissions) is never exported, nor are personal contacts or real mentors'
accounts (the repo is public) — only demo mentors, created with an unusable password.
"""
import hashlib
import json
import os
import shutil

from django.apps import apps
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files import File
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

DATA_FILE = os.path.join(settings.BASE_DIR, 'data', 'live_content.json')
MEDIA_DIR = os.path.join(settings.BASE_DIR, 'data', 'live_media')
MARKER_KEY = '_content_sync_hash'
PORTAL_MARKER_KEY = '_portal_import_hash'

# How a foreign-key target is identified across databases
FK_KEYS = {
    'accounts.User': 'email',
    'courses.Course': 'slug',
    'institutions.Institution': 'slug',
    'career.CareerProfile': 'slug',
    'career.QuizQuestion': 'text',
    'resources.CalendarCycle': 'title',
}

# (model, match fields — empty means singleton, fields never copied)
SPECS = [
    ('resources.SiteSetting',        ['key'], []),
    ('resources.FAQItem',            ['question'], []),
    ('resources.SuccessStory',       ['name', 'quote'], []),
    ('resources.Article',            ['slug'], []),
    ('resources.DeadlineBanner',     [], []),
    ('resources.CalendarCycle',      ['title'], []),
    ('resources.CalendarEvent',      ['cycle', 'title'], []),
    ('career.CareerConfig',          [], []),
    ('career.SubmissionLockConfig',  ['feature'], []),
    ('career.CareerProfile',         ['slug'], []),
    ('career.QuizQuestion',          ['text'], []),
    ('career.QuizOption',            ['question', 'text'], []),
    ('career.AIKnowledgeEntry',      ['question'], []),
    ('career.JobMarketData',         ['career_name'], []),
    ('payments.PaymentFeature',      ['feature'], []),
    ('predictor.PredictionConfig',   [], []),
    ('mentorship.MentorshipConfig',  [], []),
    ('courses.CourseSpotlight',      ['course'], []),
    ('institutions.InstitutionPromotion', ['institution'], []),
    ('accounts.User',                ['email'], []),   # mentor accounts only, see _queryset
    ('mentorship.MentorProfile',     ['user'], [
        # earnings/stats come from real sessions and payments; contacts and ID documents stay private
        'wallet_balance', 'total_earned', 'payout_debt', 'total_sessions', 'average_rating',
        'student_id_upload', 'portal_screenshot', 'whatsapp', 'university_email',
    ]),
    ('mentorship.TimeSlot',          ['mentor', 'date', 'start_time'], ['is_booked']),
]

USER_FIELDS = ['email', 'full_name', 'is_active', 'is_verified', 'county']

# Local is the source of truth for these: live rows missing from the file are deleted.
# (Quiz rows are matched on their text, so a reworded question would otherwise sit
# beside the old one. Deleting an old question also drops past answers to it.)
PRUNE = {'career.QuizQuestion', 'career.QuizOption'}

# Course offering cutoffs, matched on (course slug, institution slug). Applied after
# the portal import, so live ends up with exactly the local cutoff_points.
CUTOFFS_KEY = 'courses.CourseOffering.cutoff_points'

# The export is committed to a public repo: only demo mentor accounts go in it.
# Real mentors (personal emails) sign up on the live site themselves.
DEMO_EMAIL_DOMAINS = ('@example.com', '@test.careernext.co.ke')
PRIVATE_SETTINGS = ('admin_email',)


def _demo_users():
    q = models.Q()
    for domain in DEMO_EMAIL_DOMAINS:
        q |= models.Q(email__iendswith=domain)
    return get_user_model().objects.filter(q)


def _queryset(label):
    model = apps.get_model(label)
    if label == 'accounts.User':
        return _demo_users().filter(pk__in=apps.get_model('mentorship.MentorProfile').objects.values('user_id'))
    if label == 'mentorship.MentorProfile':
        return model.objects.filter(user__in=_demo_users())
    if label == 'mentorship.TimeSlot':
        from django.utils import timezone
        return model.objects.filter(date__gte=timezone.localdate(), is_booked=False,
                                    mentor__user__in=_demo_users())
    if label == 'resources.SiteSetting':
        return model.objects.exclude(key__in=PRIVATE_SETTINGS).exclude(key__startswith='_')
    return model.objects.all()


def _fields(model, skip):
    for f in model._meta.fields:
        if f.primary_key or f.name in skip or f.name in ('created_at', 'updated_at'):
            continue
        if model is get_user_model() and f.name not in USER_FIELDS:
            continue
        yield f


def _fk_key(f):
    return FK_KEYS.get(f.related_model._meta.label, None)


class Command(BaseCommand):
    help = 'Export/import site content between databases by natural keys'

    def add_arguments(self, parser):
        parser.add_argument('--export', action='store_true', help='Write data/live_content.json from this database')
        parser.add_argument('--force', action='store_true', help='Import even if this file was already applied')
        parser.add_argument('--dry-run', action='store_true', help='Import, report, then roll back')
        parser.add_argument('--with-portal', action='store_true',
                            help='First run import_kuccps_portal if data/kuccps_portal_degrees.json changed '
                                 'since it was last imported (18 clusters + degree courses)')

    def _portal_import(self):
        from django.core.management import call_command
        path = os.path.join(settings.BASE_DIR, 'data', 'kuccps_portal_degrees.json')
        if not os.path.exists(path):
            return
        digest = hashlib.sha256(open(path, 'rb').read()).hexdigest()
        SiteSetting = apps.get_model('resources.SiteSetting')
        if SiteSetting.objects.filter(key=PORTAL_MARKER_KEY, value=digest).exists():
            self.stdout.write('KUCCPS portal data already imported — skipping')
            return
        call_command('import_kuccps_portal', stdout=self.stdout, stderr=self.stderr)
        SiteSetting.objects.update_or_create(key=PORTAL_MARKER_KEY, defaults={
            'value': digest, 'label': 'Portal import marker (internal)', 'group': 'system'})

    def handle(self, *args, **opts):
        if opts['export']:
            return self._export()
        if opts['with_portal']:
            self._portal_import()
        if not os.path.exists(DATA_FILE):
            self.stdout.write('No data/live_content.json — nothing to sync')
            return
        raw = open(DATA_FILE, 'rb').read()
        digest = hashlib.sha256(raw).hexdigest()
        SiteSetting = apps.get_model('resources.SiteSetting')
        if not opts['force'] and SiteSetting.objects.filter(key=MARKER_KEY, value=digest).exists():
            self.stdout.write('Content already synced — skipping')
            return
        try:
            with transaction.atomic():
                self._import(json.loads(raw))
                SiteSetting.objects.update_or_create(key=MARKER_KEY, defaults={
                    'value': digest, 'label': 'Content sync marker (internal)', 'group': 'system'})
                if opts['dry_run']:
                    raise _Rollback
        except _Rollback:
            self.stdout.write(self.style.WARNING('Dry run — rolled back'))

    # ── export ──────────────────────────────────────────────────────────────
    def _export(self):
        out, files = {}, set()
        for label, keys, skip in SPECS:
            model = apps.get_model(label)
            rows = []
            for obj in _queryset(label):
                row = {}
                for f in _fields(model, skip):
                    val = getattr(obj, f.name if not f.is_relation else f.attname)
                    if f.is_relation:
                        target = getattr(obj, f.name)
                        if target is not None and f.related_model._meta.label == 'mentorship.MentorProfile':
                            val = target.user.email
                        elif target is not None:
                            k = _fk_key(f)
                            if not k:
                                raise CommandError(f'No natural key for {label}.{f.name}')
                            val = getattr(target, k)
                    elif isinstance(f, models.FileField):
                        val = val.name if val else ''
                        if val and os.path.exists(os.path.join(settings.MEDIA_ROOT, val)):
                            files.add(val)
                    elif val is not None and not isinstance(val, (str, int, float, bool)):
                        val = str(val)
                    row[f.name] = val
                for m2m in model._meta.many_to_many:
                    k = FK_KEYS.get(m2m.related_model._meta.label)
                    if k:
                        row[m2m.name] = sorted(getattr(t, k) for t in getattr(obj, m2m.name).all())
                rows.append(row)
            out[label] = rows
            self.stdout.write(f'{label:38} {len(rows)}')

        CourseOffering = apps.get_model('courses.CourseOffering')
        out[CUTOFFS_KEY] = [
            {'course': course, 'institution': inst, 'cutoff_points': cp}
            for course, inst, cp in CourseOffering.objects.exclude(cutoff_points=None)
            .order_by('course__slug', 'institution__slug')
            .values_list('course__slug', 'institution__slug', 'cutoff_points')
        ]
        self.stdout.write(f'{CUTOFFS_KEY:38} {len(out[CUTOFFS_KEY])}')

        with open(DATA_FILE, 'w', encoding='utf-8') as fh:
            json.dump(out, fh, indent=1, ensure_ascii=False, sort_keys=True)
        shutil.rmtree(MEDIA_DIR, ignore_errors=True)
        for name in files:
            dest = os.path.join(MEDIA_DIR, name)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(os.path.join(settings.MEDIA_ROOT, name), dest)
        self.stdout.write(self.style.SUCCESS(f'Wrote {DATA_FILE} and {len(files)} media file(s)'))

    # ── import ──────────────────────────────────────────────────────────────
    def _resolve(self, f, value):
        if value in (None, ''):
            return None
        rel = f.related_model
        if rel._meta.label == 'mentorship.MentorProfile':
            return rel.objects.filter(user__email=value).first()
        return rel.objects.filter(**{_fk_key(f): value}).first()

    def _import(self, data):
        for label, keys, skip in SPECS:
            model = apps.get_model(label)
            created = updated = missing = 0
            kept = set()
            for row in data.get(label, []):
                values, m2m, file_vals, broken = {}, {}, {}, False
                for f in _fields(model, skip):
                    if f.name not in row:
                        continue
                    v = row[f.name]
                    if f.is_relation:
                        target = self._resolve(f, v)
                        if v and target is None:
                            if f.name in keys or not f.null:
                                broken = True
                                break
                            self.stdout.write(f'  {label}: {f.name}={v!r} not on this site — left blank')
                        values[f.name] = target
                    elif isinstance(f, models.FileField):
                        file_vals[f.name] = v
                    else:
                        values[f.name] = f.to_python(v) if v is not None else None
                if broken:
                    missing += 1
                    continue
                for m in model._meta.many_to_many:
                    if m.name in row:
                        k = FK_KEYS[m.related_model._meta.label]
                        m2m[m.name] = list(m.related_model.objects.filter(**{f'{k}__in': row[m.name]}))

                lookup = {k: values[k] for k in keys}
                obj = model.objects.filter(**lookup).first() if keys else model.objects.order_by('pk').first()
                if label == 'accounts.User':
                    if obj:   # never touch an existing live account
                        continue
                    obj = model(**values)
                    obj.set_unusable_password()
                    created += 1
                elif obj is None:
                    obj = model(**values)
                    created += 1
                else:
                    for k, v in values.items():
                        setattr(obj, k, v)
                    updated += 1
                for name, path in file_vals.items():
                    self._attach(obj, name, path)
                obj.save()
                kept.add(obj.pk)
                for name, targets in m2m.items():
                    getattr(obj, name).set(targets)
            pruned = 0
            if label in PRUNE and data.get(label):   # never wipe a table because the file lacks it
                pruned, _ = model.objects.exclude(pk__in=kept).delete()
            self.stdout.write(f'{label:38} +{created} ~{updated}' + (f' -{pruned}' if pruned else '')
                              + (f' skipped {missing}' if missing else ''))
        if CUTOFFS_KEY in data:
            self._import_cutoffs(data[CUTOFFS_KEY])

    def _import_cutoffs(self, rows):
        from django.core.cache import cache
        from courses.management.commands.import_kuccps_portal import CACHE_KEYS
        CourseOffering = apps.get_model('courses.CourseOffering')
        wanted = {(r['course'], r['institution']): r['cutoff_points'] for r in rows}
        changed, found = [], set()
        for o in (CourseOffering.objects.select_related('course', 'institution')
                  .only('cutoff_points', 'course__slug', 'institution__slug')):
            key = (o.course.slug, o.institution.slug)
            cp = wanted.get(key)
            if key in wanted:
                found.add(key)
            if o.cutoff_points != cp:
                o.cutoff_points = cp
                changed.append(o)
        CourseOffering.objects.bulk_update(changed, ['cutoff_points'], batch_size=500)
        for key in CACHE_KEYS:
            cache.delete(key)
        missing = len(wanted) - len(found)
        self.stdout.write(f'{CUTOFFS_KEY:38} ~{len(changed)}'
                          + (f' ({missing} offerings not on this site)' if missing else ''))

    def _attach(self, obj, name, path):
        """Upload a bundled media file to this site's storage (Cloudinary on live)."""
        current = getattr(obj, name)
        if not path:
            return
        if current and current.name == path and default_storage.exists(path):
            return
        src = os.path.join(MEDIA_DIR, path)
        if not os.path.exists(src):
            if not current:
                setattr(obj, name, path)   # keep the reference; file may already be in storage
            return
        with open(src, 'rb') as fh:
            getattr(obj, name).save(os.path.basename(path), File(fh), save=False)


class _Rollback(Exception):
    pass
