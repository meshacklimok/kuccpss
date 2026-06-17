"""
Management command: python manage.py seed_content

Populates FAQItem, SuccessStory, and SiteSetting with the initial
hardcoded content so the admin dashboard is ready to use on first run.
Safe to re-run — skips records that already exist (matched by key/question).
"""
from django.core.management.base import BaseCommand
from resources.models import FAQItem, SuccessStory, SiteSetting


FAQ_DATA = [
    # ── General ──────────────────────────────────────────────────────────────
    ("general", "What is CareerNext?",
     "CareerNext is a free online platform that helps Kenyan KCSE graduates calculate their cluster points, discover which university, KMTC, TVET, and TTC courses they qualify for, and explore career options — all using the official KUCCPS formula and placement criteria."),

    ("general", "Is CareerNext the same as KUCCPS?",
     "No. KUCCPS (Kenya Universities and Colleges Central Placement Service) is the official government body that places students into institutions. You apply at kuccps.ac.ke.\n\nCareerNext (careernext.co.ke) is an independent, free tool to help you prepare for that application — by calculating your points and finding your eligible courses before the portal opens. We are not affiliated with the government."),

    ("general", "Is CareerNext free to use?",
     "Yes — completely free. Every feature including the cluster points calculator, eligible courses list, career engine, course shortlist, and PDF exports is free for all students. There are no hidden charges or premium tiers."),

    ("general", "Do I need to create an account?",
     "The cluster points calculator and basic course browsing are available without an account. However, creating a free account unlocks: saving your grades between sessions, bookmarking courses to a watchlist, building a shortlist, tracking your applications, and getting personalised career engine recommendations."),

    ("general", "Is my data safe on CareerNext?",
     "Yes. Your grades and personal information are stored securely and are never shared with third parties. We do not sell your data. You can delete your account at any time from your Profile settings."),

    # ── Cluster Points ────────────────────────────────────────────────────────
    ("cluster", "How are cluster points calculated?",
     "The official KUCCPS formula is:\n\nCluster Points = 48 × √( (cluster_subjects / 48) × (aggregate / 84) )\n\nWhere cluster_subjects is the sum of your raw marks in the 4 subjects that form each specific cluster (max 48), and aggregate is your KCSE total (max 84). The maximum possible cluster points score is 48."),

    ("cluster", "What is the KCSE aggregate (total)?",
     "The aggregate is your best 7 subjects scored as follows:\n\nMathematics + best of (English or Kiswahili) + your next 5 best subjects. The maximum aggregate is 84 points (7 subjects × A = 12 each)."),

    ("cluster", "What are the 20 KUCCPS clusters?",
     "KUCCPS has 20 subject clusters (C1–C20), each grouping 4 subjects relevant to a field of study. For example, Cluster 1 (Medicine) includes Biology, Chemistry, Mathematics, and Physics. Visit the Clusters page to view all 20 clusters and their subject compositions."),

    ("cluster", "My cluster points seem lower than expected — why?",
     "A few common reasons:\n\n• Weak cluster subjects — the formula weights your performance in the specific 4 cluster subjects heavily. A weak subject in the cluster drags the score down even if your overall grades are good.\n• Low aggregate — the aggregate (all 7 best subjects) also factors in.\n• Grade entry error — double-check you entered the correct grade for each subject, especially distinguishing A (12) from A- (11), etc."),

    ("cluster", "Can I enter grades from a photo of my result slip?",
     "Yes. The calculator has an OCR (Optical Character Recognition) feature powered by GPT-4o. Take a clear, well-lit photo of your KNEC result slip and upload it — the system will attempt to read your grades automatically. If the photo is unclear, enter grades manually for best accuracy."),

    # ── Courses & Pathways ────────────────────────────────────────────────────
    ("courses", "What pathways does CareerNext cover?",
     "CareerNext covers all four KUCCPS placement pathways:\n\n• Degree — Public and private universities (cluster-points based)\n• KMTC — Kenya Medical Training College programmes (grade-based)\n• TVET — Technical and Vocational Education Training institutions\n• TTC — Teacher Training Colleges"),

    ("courses", "How do I find courses I qualify for?",
     "1. Go to the Cluster Points Calculator and enter your grades.\n2. Click 'View Eligible Courses' — you'll see every course whose cutoff point is at or below your calculated cluster score.\n3. Or use the Career Guidance Engine for a more personalised, filtered recommendation."),

    ("courses", "What does 'cutoff points' mean?",
     "The cutoff point is the minimum cluster score a student needed to be placed into a given course in a recent intake. If your cluster points are equal to or above the cutoff, you generally qualify. Cutoffs change each year based on applicant demand — a course in high demand may have a higher cutoff than its stated minimum."),

    ("courses", "Why do some courses show a minimum grade instead of cluster points?",
     "KMTC, TVET, and TTC programmes use minimum mean grade requirements (e.g. C, C+, B-) rather than cluster points. Only university degree courses use the cluster points system. When you use the Career Guidance Engine, select the appropriate pathway and you'll see the right criteria for each."),

    ("courses", "Can I save and compare courses?",
     "Yes. When logged in, you can:\n• Bookmark any course to your Watchlist (the bookmark icon on each course)\n• Shortlist up to your top choices for easy comparison\n• View cutoff trend charts to see how a course's cutoff has changed over the years\n• Access everything from your Dashboard"),

    # ── KUCCPS Process ────────────────────────────────────────────────────────
    ("kuccps", "When does the KUCCPS application portal open?",
     "The portal typically opens between June and August each year, after KCSE results are released. For 2026, the portal is estimated to open around 3 July 2026 and close around 21 August 2026. Check the official KUCCPS website and the KUCCPS Calendar on this site for confirmed dates."),

    ("kuccps", "How many course choices can I submit on KUCCPS?",
     "KUCCPS currently allows students to submit up to 4 course choices per pathway (degree, KMTC, TVET, TTC), ranked in order of preference. You are placed into the highest-ranked course you qualify for based on your cluster points and available slots."),

    ("kuccps", "What happens if I don't get my first choice?",
     "KUCCPS works through your ranked choices in order. If you don't qualify for your first choice (because your cluster points are below the cutoff or slots are filled), the system tries your second choice, then third, and so on. If none of your choices are successful, you may participate in the revision or inter-institutional transfer window."),

    ("kuccps", "Does CareerNext submit my application to KUCCPS?",
     "No. CareerNext is only a preparation and guidance tool. Your actual placement application must be submitted directly on the official KUCCPS portal at kuccps.ac.ke during the application window. CareerNext helps you decide what to apply for — you still complete the application yourself on the official site."),

    ("kuccps", "What is the HELB loan and how do I apply?",
     "The Higher Education Loans Board (HELB) provides subsidised loans and bursaries to Kenyan students in accredited institutions. Applications are done online at helb.co.ke. Apply as soon as you get your placement letter — bursary deadlines are typically strict."),

    # ── My Account ────────────────────────────────────────────────────────────
    ("account", "How do I reset my password?",
     "On the Login page, click 'Forgot password?'. Enter your email address and we'll send you a reset link. Check your spam/junk folder if you don't see it within a few minutes."),

    ("account", "Can I sign in with Google?",
     "Yes — the login page has a 'Continue with Google' option powered by Google OAuth. Your CareerNext account will be linked to your Google account for quick sign-in on any device."),

    ("account", "How do I update my county or KCSE year?",
     "Go to My Profile (accessible from the top-right account menu). You can update your full name, county, KCSE year, and profile picture there."),

    ("account", "Why does the Career Engine show sample courses instead of my results?",
     "The 'Recommended For You' section on your dashboard shows real results only after you've run the Career Engine at least once. Visit the Career Guidance Engine, enter your grades and preferences, and click Proceed. Your dashboard will then display your personalised matches."),

    ("account", "How do I report an error in course data or cutoff points?",
     "If you spot incorrect course information, outdated cutoff points, or a missing institution, please email us at info@careernext.co.ke with details. We update the database regularly and appreciate corrections from students and educators."),
]


STORIES_DATA = [
    {
        "name": "Faith Wanjiru", "initials": "FW", "county": "Kiambu County",
        "work_location": "Nairobi", "kcse_grade": "A-",
        "quote": "I wasn't sure my grades covered Computer Science. CareerNext confirmed I qualified and showed me the exact cluster I needed. I'm now in second year at UoN and interning at a Nairobi tech company.",
        "course_name": "BSc Computer Science", "institution": "University of Nairobi",
        "pathway": "degree", "year": 2023,
        "avatar_bg": "#eef2ff", "avatar_color": "#4f46e5", "order": 1,
    },
    {
        "name": "Caleb Ochieng", "initials": "CO", "county": "Kisumu County",
        "work_location": "Homa Bay", "kcse_grade": "C+",
        "quote": "People said C+ closes every door. The career engine showed me I met KMTC's minimum and flagged Community Health Nursing as a strong fit. I graduated and I'm now posted at a sub-county health centre in Homabay.",
        "course_name": "Diploma in Community Health Nursing", "institution": "KMTC Kisumu",
        "pathway": "kmtc", "year": 2022,
        "avatar_bg": "#fef2f2", "avatar_color": "#dc2626", "order": 2,
    },
    {
        "name": "Njeri Wambui", "initials": "NW", "county": "Muranga County",
        "work_location": "Muranga", "kcse_grade": "B",
        "quote": "I wanted Medicine but my points fell short. CareerNext recommended BSc Nursing as a near-equivalent with strong job prospects. I'm now a Registered Nurse at Muranga County Referral Hospital and I love every shift.",
        "course_name": "BSc Nursing", "institution": "Mount Kenya University",
        "pathway": "degree", "year": 2022,
        "avatar_bg": "#f5f3ff", "avatar_color": "#7c3aed", "order": 3,
    },
    {
        "name": "Vivian Achieng", "initials": "VA", "county": "Siaya County",
        "work_location": "Kisumu", "kcse_grade": "C",
        "quote": "The calculator matched me to Electrical Engineering Technology at my county poly. Within six months of graduating I landed a placement with a construction firm in Kisumu. I now supervise wiring on full housing estates.",
        "course_name": "Diploma in Electrical Engineering Tech", "institution": "Siaya Institute of Technology",
        "pathway": "tvet", "year": 2023,
        "avatar_bg": "#ecfdf5", "avatar_color": "#059669", "order": 4,
    },
    {
        "name": "Hassan Abdullahi", "initials": "HA", "county": "Mombasa County",
        "work_location": "Mombasa", "kcse_grade": "B-",
        "quote": "CareerNext shortlisted diploma options that matched my Commerce grade. I picked Business Administration, graduated in 2023, and now run a small logistics business linking Mombasa traders to Nairobi markets — 8 employees and counting.",
        "course_name": "Diploma in Business Administration", "institution": "Kenya School of Business",
        "pathway": "diploma", "year": 2022,
        "avatar_bg": "#ecfeff", "avatar_color": "#0891b2", "order": 5,
    },
    {
        "name": "Samuel Ruto", "initials": "SR", "county": "Uasin Gishu County",
        "work_location": "Uasin Gishu EPZ", "kcse_grade": "D+",
        "quote": "I thought D+ closed every option. The platform showed me the Artisan Certificate path and I went for Welding at Eldoret Polytechnic. Got NITA certified after graduation and I'm now contracted by a steel fabrication firm in the EPZ.",
        "course_name": "Artisan Certificate — Welding & Fabrication", "institution": "Eldoret National Polytechnic",
        "pathway": "artisan", "year": 2022,
        "avatar_bg": "#fffbeb", "avatar_color": "#d97706", "order": 6,
    },
]


SETTINGS_DATA = [
    # Contact
    ("contact_email",    "Contact Email",          "info@careernext.co.ke", "email",    "contact"),
    ("whatsapp_number",  "WhatsApp Number",         "254700000000",          "phone",    "contact"),
    ("instagram_handle", "Instagram Handle",        "careernext_ke",         "text",     "social"),
    ("twitter_handle",   "Twitter / X Handle",      "careernext_ke",         "text",     "social"),
    ("facebook_url",     "Facebook URL",            "",                      "url",      "social"),
    # Hero / branding
    ("hero_badge_text",  "Hero Badge Text",         "Kenya's #1 Placement Guide", "text", "hero"),
    ("hero_tagline",     "Hero Tagline",            "Find Your Perfect Course After KCSE", "text", "hero"),
    ("hero_subtext",     "Hero Sub-text",
     "Calculate your cluster points, discover courses you qualify for, and explore career paths — all in one place, free for Kenyan students.",
     "textarea", "hero"),
    # About page
    ("about_mission",    "About — Mission Paragraph",
     "CareerNext was built to change that. We put the full KUCCPS formula into a simple tool, pair it with a complete course database, and wrap it in career guidance — so every student can walk into the application portal knowing exactly where they stand.",
     "textarea", "about"),
]


class Command(BaseCommand):
    help = "Seed FAQItem, SuccessStory, and SiteSetting with initial content"

    def handle(self, *args, **options):
        # ── FAQ ──────────────────────────────────────────────────────────────
        faq_created = 0
        for i, (cat, question, answer) in enumerate(FAQ_DATA, start=1):
            _, created = FAQItem.objects.get_or_create(
                question=question,
                defaults={"answer": answer, "category": cat, "order": i, "is_active": True},
            )
            if created:
                faq_created += 1
        self.stdout.write(f"FAQ: {faq_created} created, {len(FAQ_DATA) - faq_created} already existed")

        # ── Success Stories ───────────────────────────────────────────────────
        story_created = 0
        for data in STORIES_DATA:
            _, created = SuccessStory.objects.get_or_create(
                name=data["name"],
                defaults=data,
            )
            if created:
                story_created += 1
        self.stdout.write(f"Stories: {story_created} created, {len(STORIES_DATA) - story_created} already existed")

        # ── Site Settings ─────────────────────────────────────────────────────
        setting_created = 0
        for key, label, value, stype, group in SETTINGS_DATA:
            _, created = SiteSetting.objects.get_or_create(
                key=key,
                defaults={"label": label, "value": value, "setting_type": stype, "group": group},
            )
            if created:
                setting_created += 1
        self.stdout.write(f"Settings: {setting_created} created, {len(SETTINGS_DATA) - setting_created} already existed")

        self.stdout.write(self.style.SUCCESS("Done — content seeded successfully."))
