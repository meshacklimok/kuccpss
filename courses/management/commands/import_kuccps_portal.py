"""
Management command: import_kuccps_portal

Imports degree data from the official KUCCPS programmes portal
(https://students.kuccps.net/programmes/), as scraped by
scripts/scrape_kuccps_portal.py into data/kuccps_portal_degrees.json.

What it does (all inside one transaction):
  1. Restructures the calculator clusters to the 18 KUCCPS clusters
     (101–118 = clusters 1–18): portal names + SubjectGroups rebuilt from the
     portal's "Minimum Entry Requirements". Clusters 119/120 are removed.
  2. Matches every portal offering (unique programme code) to a CourseOffering —
     by code, then (institution, course name), then a close name at the same
     institution — creating institutions/courses/offerings the DB lacks.
  3. Merges portal cutoffs into CourseOffering.cutoff_points. Years are stored
     exactly as the portal labels them (KCSE exam year) — never shifted.
  4. Moves each degree course to its portal cluster and stores its
     entry_requirements (4 cluster-subject slots) and subject_requirements.
     Courses not on the portal keep their data and move by renumbering only.
  5. Deletes the old sub-clusters (numbers < 100), recalculates saved cluster
     results and clears the cutoff caches.

GSC (General Science) is ignored, MAT A / MAT B both mean Mathematics.

Usage:
    python manage.py import_kuccps_portal --dry-run     # report only, rolls back
    python manage.py import_kuccps_portal
"""
import difflib
import json
import os
import re
from collections import Counter, defaultdict

from django.conf import settings
from django.core.cache import cache
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from clusters.constants import KUCCPS_CLUSTER_NAMES, NUM_KUCCPS_CLUSTERS
from clusters.models import Cluster, Subject, SubjectGroup
from courses.models import Course, CourseCategory, CourseOffering, CourseType
from institutions.models import Institution, InstitutionType

DATA_PATH = os.path.join(settings.BASE_DIR, 'data', 'kuccps_portal_degrees.json')

CLUSTER_NAMES = KUCCPS_CLUSTER_NAMES
NUM_CLUSTERS = NUM_KUCCPS_CLUSTERS

# Old 20-cluster numbering -> 18-cluster numbering, for courses not on the portal
RENUMBER = {16: 14, 17: 3, 18: 16, 19: 17, 20: 18}

# Portal subject codes -> Subject.name. GSC is deliberately absent (ignored).
CODE_TO_SUBJECT = {
    'ENG': 'English', 'KIS': 'Kiswahili', 'KSL': 'Kenyan Sign Language',
    'MAT A': 'Mathematics', 'MAT B': 'Mathematics',
    'BIO': 'Biology', 'BSC': 'Biology', 'CHE': 'Chemistry', 'PHY': 'Physics', 'PSC': 'Physics',
    'HAG': 'History and Government', 'GEO': 'Geography',
    'CRE': 'Christian Religious Education', 'IRE': 'Islamic Religious Education',
    'HRE': 'Hindu Religious Education',
    'HSC': 'Home Science', 'ARD': 'Art and Design', 'AGR': 'Agriculture',
    'WW': 'Woodwork', 'MW': 'Metalwork', 'BC': 'Building Construction',
    'PM': 'Power Mechanics', 'ECT': 'Electricity', 'DRD': 'Drawing and Design',
    'AVT': 'Aviation Technology', 'CMP': 'Computer Studies',
    'FRE': 'French', 'GER': 'German', 'ARB': 'Arabic', 'MUC': 'Music',
    'BST': 'Business Studies',
}
IGNORED_CODES = {'GSC'}

# Portal institution name -> existing DB name (renamed on import)
INSTITUTION_RENAMES = {'BOMET UNIVERSITY': 'Bomet University College'}
UNIVERSITY_TYPE_SLUGS = {'PUBLIC': 'public-university', 'PRIVATE': 'private-university'}

CACHE_KEYS = ('homepage_trends_v1', 'degree_course_min_cutoffs_v1')


def norm(s):
    s = (s or '').upper().replace('&', ' AND ')
    return ' '.join(re.sub(r'[^A-Z0-9 ]', ' ', s).split())


def title_name(s):
    small = {'of', 'and', 'the', 'for', 'in'}
    words = s.title().split()
    return ' '.join(w.lower() if i and w.lower() in small else w for i, w in enumerate(words))


def clean_codes(codes):
    return [c for c in codes if c not in IGNORED_CODES]


def cluster_patterns(portal):
    """KUCCPS cluster number -> its 4 cluster-subject slots (first programme page seen)."""
    patterns = {}
    for p in portal:
        patterns.setdefault(p['cluster_number'], p['cluster_subjects'])
    return patterns


class Command(BaseCommand):
    help = 'Import KUCCPS portal degree cutoffs, clusters and requirements'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only; roll back all changes')
        parser.add_argument('--file', default=DATA_PATH)
        parser.add_argument('--no-recalc', action='store_true', help='Skip recalculating saved cluster results')

    def handle(self, *args, **opts):
        portal = json.load(open(opts['file'], encoding='utf-8'))
        self.log = []
        try:
            with transaction.atomic():
                self.run(portal, recalc=not opts['no_recalc'])
                if opts['dry_run']:
                    raise _DryRun
        except _DryRun:
            self.stdout.write(self.style.WARNING('DRY RUN — all changes rolled back.'))
        else:
            for key in CACHE_KEYS:
                cache.delete(key)
            self.stdout.write(self.style.SUCCESS('Import committed; caches cleared.'))

    def note(self, msg):
        self.log.append(msg)
        self.stdout.write(msg)

    # ------------------------------------------------------------------
    def run(self, portal, recalc):
        subjects = {s.name: s for s in Subject.objects.all()}
        self.year_counts = Counter()
        self.course_reqs = defaultdict(list)
        self.degree_type = CourseType.objects.get(name='Degree')

        patterns = cluster_patterns(portal)
        masters = self.restructure_clusters(patterns, subjects)

        # Unique offerings by programme code (pages repeat offerings across name variants)
        by_code = {}
        for p in portal:
            for o in p['offerings']:
                by_code.setdefault(o['programme_code'], {**o, 'page': p})
        self.note(f'Portal: {len(portal)} programme pages, {len(by_code)} unique offerings')

        insts = self.resolve_institutions(by_code.values())
        course_reqs = self.import_offerings(by_code, insts, masters)
        self.update_courses(course_reqs, masters, patterns)
        self.remove_subclusters()
        if recalc:
            self.recalculate()

    # ------------------------------------------------------------------
    def restructure_clusters(self, patterns, subjects):
        existing = {c.number: c for c in Cluster.objects.filter(number__gte=100)}
        # Park current names first: the new names reuse old ones on other numbers (unique constraint)
        for c in existing.values():
            Cluster.objects.filter(pk=c.pk).update(name=f'__tmp_{c.number}', slug=f'tmp-{c.number}')

        masters = {}
        for n, name in CLUSTER_NAMES.items():
            c = existing.get(100 + n) or Cluster(number=100 + n)
            c.name = name
            c.slug = slugify(name)[:120]
            c.description = f'KUCCPS Cluster {n}: {name}.'
            c.save()
            c.subject_groups.all().delete()
            for slot in patterns[n]:
                codes = clean_codes(slot['subjects'])
                names = list(dict.fromkeys(CODE_TO_SUBJECT[c_] for c_ in codes))
                label = '/'.join(codes) if len(codes) <= 8 else 'Any other subject'
                sg = SubjectGroup.objects.create(
                    cluster=c, name=f'Cluster subject {slot["slot"]}: {label}'[:100],
                    required=True, priority=slot['slot'],
                )
                sg.subjects.set([subjects[x] for x in names])
            masters[n] = c
        self.note(f'Clusters: 101–{100 + NUM_CLUSTERS} renamed and subject groups rebuilt from portal')

        for num in sorted(existing):
            if num > 100 + NUM_CLUSTERS:
                c = existing[num]
                courses = Course.objects.filter(cluster=c).count()
                if courses:
                    raise RuntimeError(f'Cluster {num} still has {courses} courses')
                c.delete()
                self.note(f'Clusters: removed calculator cluster {num} (KUCCPS now has {NUM_CLUSTERS})')
        return masters

    # ------------------------------------------------------------------
    def resolve_institutions(self, rows):
        uni = Institution.objects.filter(institution_type__slug__in=UNIVERSITY_TYPE_SLUGS.values())
        by_name = {norm(i.name): i for i in uni}
        types = {k: InstitutionType.objects.get(slug=v) for k, v in UNIVERSITY_TYPE_SLUGS.items()}
        out = {}
        for r in rows:
            key = norm(r['institution'])
            if key in out:
                continue
            inst = by_name.get(key)
            if inst is None and key in INSTITUTION_RENAMES:
                inst = by_name.get(norm(INSTITUTION_RENAMES[key]))
                if inst:
                    old = inst.name
                    inst.name = title_name(r['institution'])
                    inst.save(update_fields=['name', 'updated_at'])
                    self.note(f'Institution renamed: {old} -> {inst.name}')
            if inst is None:
                inst = Institution.objects.create(
                    name=title_name(r['institution']),
                    institution_type=types[r['inst_type']],
                    location=title_name(r['county']),
                )
                self.note(f'Institution created: {inst.name} ({inst.institution_type.name}, {inst.location})')
            out[key] = inst
        return out

    # ------------------------------------------------------------------
    def import_offerings(self, by_code, insts, masters):
        ours = {}
        by_prog_code = {}
        for o in (CourseOffering.objects.filter(course__course_type=self.degree_type)
                  .select_related('course', 'institution')):
            ours[(o.institution_id, norm(o.course.name))] = o
            if o.programme_code:
                by_prog_code[o.programme_code] = o
        courses_by_name = {norm(c.name): c for c in Course.objects.filter(course_type=self.degree_type)}

        # Category guess for new courses: most common category among courses in that portal cluster
        cat_votes = defaultdict(Counter)

        pending, claimed = [], {}
        stats = Counter()
        for code, r in by_code.items():
            inst = insts[norm(r['institution'])]
            o = by_prog_code.get(code) or ours.get((inst.pk, norm(r['programme_name'])))
            how = 'exact'
            if o is None:
                pending.append((code, r, inst))
                continue
            if o.pk in claimed:
                stats['duplicate'] += 1
                self.note(f'  SKIP duplicate {code} {r["programme_name"]} @ {inst.name} (already {claimed[o.pk]})')
                continue
            claimed[o.pk] = code
            stats[how] += 1
            self.apply(o, code, r)
            if o.course.category_id:
                cat_votes[r['page']['cluster_number']][o.course.category_id] += 1

        # Close name at the same institution, among offerings the portal did not claim
        free = defaultdict(dict)
        for (inst_id, nm), o in ours.items():
            if o.pk not in claimed:
                free[inst_id][nm] = o
        still = []
        for code, r, inst in pending:
            cands = free.get(inst.pk, {})
            m = difflib.get_close_matches(norm(r['programme_name']), cands.keys(), n=1, cutoff=0.88)
            # A close name only counts when cutoffs agree on every year both sides have
            cp = (cands[m[0]].cutoff_points or {}) if m else {}
            agree = all(abs(float(cp[y]) - v) < 0.01 for y, v in r['cutoffs'].items() if y in cp)
            if m and agree and cands[m[0]].pk not in claimed:
                o = cands.pop(m[0])
                claimed[o.pk] = code
                stats['close-name'] += 1
                self.note(f'  close match {code}: "{r["programme_name"]}" -> "{o.course.name}" @ {inst.name}')
                self.apply(o, code, r)
            else:
                still.append((code, r, inst))

        for code, r, inst in still:
            n = r['page']['cluster_number']
            course = courses_by_name.get(norm(r['programme_name']))
            if course is None:
                votes = cat_votes.get(n)
                cat = CourseCategory.objects.filter(pk=votes.most_common(1)[0][0]).first() if votes else None
                course = Course.objects.create(
                    name=r['programme_name'], course_type=self.degree_type,
                    category=cat, cluster=masters[n],
                )
                courses_by_name[norm(course.name)] = course
                stats['new course'] += 1
            if CourseOffering.objects.filter(course=course, institution=inst).exists():
                stats['duplicate'] += 1
                self.note(f'  SKIP duplicate {code} {r["programme_name"]} @ {inst.name}')
                continue
            o = CourseOffering(course=course, institution=inst)
            stats['new offering'] += 1
            self.apply(o, code, r)

        self.note(f'Offerings: {dict(stats)}')
        self.note(f'Cutoff values written per year: {dict(sorted(self.year_counts.items()))}')
        return self.course_reqs

    def apply(self, o, code, r):
        cp = dict(o.cutoff_points or {})
        for y, v in r['cutoffs'].items():
            cp[str(y)] = round(float(v), 3)
            self.year_counts[str(y)] += 1
        o.cutoff_points = dict(sorted(cp.items())) or None
        o.programme_code = code
        o.save()
        page = r['page']
        self.course_reqs[o.course_id].append((
            page['cluster_number'],
            json.dumps(page['cluster_subjects']),
            json.dumps(page['subject_requirements']),
        ))

    # ------------------------------------------------------------------
    def update_courses(self, course_reqs, masters, patterns):
        moves = Counter()
        mixed = 0
        for course in Course.objects.filter(course_type=self.degree_type).select_related('cluster'):
            old = course.cluster.kuccps_number if course.cluster else None
            recs = course_reqs.get(course.pk)
            if recs:
                votes = Counter(recs)
                if len(votes) > 1:
                    mixed += 1
                n, cs, sr = votes.most_common(1)[0][0]
                entry = json.loads(cs)
                subj = [
                    {'slot': s['slot'], 'subjects_str': '/'.join(clean_codes(s['subjects'])),
                     'min_grade': s['min_grade']}
                    for s in json.loads(sr) if clean_codes(s['subjects'])
                ]
                course.subject_requirements = subj or None
            else:
                if old is None:
                    continue
                n = RENUMBER.get(old, old)
                entry = patterns[n]
            course.entry_requirements = [
                {'slot': s['slot'], 'subjects_str': '/'.join(clean_codes(s['subjects']))} for s in entry
            ]
            course.cluster = masters[n]
            course.save(update_fields=['cluster', 'entry_requirements', 'subject_requirements', 'updated_at'])
            if old != n:
                moves[(old, n, 'portal' if recs else 'renumber')] += 1
                if recs and RENUMBER.get(old, old) != n:
                    self.note(f'  MOVED C{old} -> C{n}: {course.name}')
        self.note(f'Courses whose offerings disagree on requirements (majority used): {mixed}')
        self.note('Cluster moves (old -> new, source: count): ' + ', '.join(
            f'{a}->{b} {src}: {c}' for (a, b, src), c in sorted(moves.items(), key=lambda x: -x[1])))

    # ------------------------------------------------------------------
    def remove_subclusters(self):
        subs = Cluster.objects.filter(number__lt=100)
        left = Course.objects.filter(cluster__in=subs).count()
        if left:
            raise RuntimeError(f'{left} courses still point at sub-clusters')
        n = subs.count()
        subs.delete()
        self.note(f'Sub-clusters deleted: {n}')

    def recalculate(self):
        from clusterpoints.models import UserKCSEResult
        from clusterpoints.services import calculate_all_clusters
        done = 0
        for kr in UserKCSEResult.objects.filter(subject_results__isnull=False).distinct():
            calculate_all_clusters(kr)
            done += 1
        self.note(f'Recalculated saved cluster results: {done}')


class _DryRun(Exception):
    pass
