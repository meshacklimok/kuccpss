from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from career.models import CareerProfile
from courses.models import Course, CourseOffering, CourseType
from institutions.models import Institution, InstitutionType
from kuccpss import seo


@override_settings(KCSE_CANDIDATE_YEAR=2026)
class SeoMetaTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        uni_type = InstitutionType.objects.create(name="Public University")
        kmtc_type = InstitutionType.objects.create(name="KMTC")
        cls.uni = Institution.objects.create(
            name="Kenyatta University", institution_type=uni_type, location="Nairobi County")
        cls.uni2 = Institution.objects.create(name="Moi University", institution_type=uni_type)
        cls.kmtc = Institution.objects.create(
            name="KMTC Kabarnet", institution_type=kmtc_type, location="Baringo County")

        degree = CourseType.objects.create(name="Degree")
        kmtc_ct = CourseType.objects.create(name="KMTC")
        cls.nursing = Course.objects.create(name="BACHELOR OF SCIENCE IN NURSING", course_type=degree)
        CourseOffering.objects.create(course=cls.nursing, institution=cls.uni,
                                      cutoff_points={"2025": 41.234, "2024": 40.0})
        CourseOffering.objects.create(course=cls.nursing, institution=cls.uni2,
                                      cutoff_points={"2025": 38.5})
        cls.cha = Course.objects.create(name="Certificate in Community Health Assistant",
                                        course_type=kmtc_ct, minimum_mean_grade="C-")
        CourseOffering.objects.create(course=cls.cha, institution=cls.kmtc)

    def test_university_mentions_cutoffs_and_application_year(self):
        meta = seo.institution_meta(self.uni, 90)
        self.assertEqual(meta["title"], "Kenyatta University Courses & Cutoff Points 2027 | CareerNext")
        self.assertIn("90 degree courses with KCSE 2025 cutoff points", meta["description"])
        self.assertIn("KCSE 2026 candidate?", meta["description"])

    def test_kmtc_uses_mean_grade_not_cutoff_points(self):
        meta = seo.institution_meta(self.kmtc, 1)
        self.assertNotIn("Cutoff", meta["title"])
        self.assertIn("1 KUCCPS course with", meta["description"])
        self.assertIn("mean grade", meta["description"])

    def test_degree_course_shows_cutoff_range_and_fixes_caps(self):
        meta = seo.course_meta(self.nursing, list(self.nursing.offerings.all()))
        self.assertTrue(meta["title"].startswith("Bachelor of Science in Nursing: Cutoff Points"))
        self.assertIn("2 universities", meta["description"])
        self.assertIn("from 38.5 to 41.2 points", meta["description"])

    def test_non_degree_course_uses_mean_grade(self):
        meta = seo.course_meta(self.cha, list(self.cha.offerings.all()))
        self.assertNotIn("Cutoff", meta["title"])
        self.assertIn("Minimum KCSE mean grade: C-.", meta["description"])

    def test_lengths_stay_within_limits(self):
        for meta in (seo.institution_meta(self.uni, 90), seo.institution_meta(self.kmtc, 1),
                     seo.course_meta(self.cha, [])):
            self.assertLessEqual(len(meta["title"]), seo.TITLE_MAX)
            self.assertLessEqual(len(meta["description"]), seo.DESCRIPTION_MAX)

    def test_detail_pages_render_generated_meta(self):
        resp = self.client.get(self.uni.get_absolute_url())
        self.assertContains(resp, "<title>Kenyatta University Courses &amp; Cutoff Points 2027 | CareerNext</title>", html=False)
        resp = self.client.get(self.nursing.get_absolute_url())
        self.assertContains(resp, "Bachelor of Science in Nursing: Cutoff Points")
        self.assertNotContains(resp, "{&#x27;2025&#x27;")  # raw cutoff dict no longer leaks into meta


class SeoHelperTests(SimpleTestCase):
    def test_long_name_drops_brand_before_keywords(self):
        title = seo._fit_title("Diploma in Agribusiness Management: Requirements & Where to Study 2027",
                               "Diploma in Agribusiness Management")
        self.assertEqual(title, "Diploma in Agribusiness Management: Requirements & Where to Study 2027")

    def test_display_name_keeps_acronyms(self):
        self.assertEqual(seo._display_name("BACHELOR OF COMMERCE (WITH IT)"),
                         "Bachelor of Commerce (with IT)")
        self.assertEqual(seo._display_name("Diploma in Pharmacy"), "Diploma in Pharmacy")


class SitemapTests(TestCase):
    def test_sitemap_lists_engine_pages_not_login_gated_ones(self):
        CareerProfile.objects.create(title="Actuary", description="x")
        body = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(reverse("career:career_profile_detail", kwargs={"slug": "actuary"}), body)
        self.assertIn(reverse("career:quiz"), body)
        self.assertNotIn(reverse("clusterpoints:eligible_courses"), body)
        self.assertNotIn(reverse("career:kcse_input"), body)  # retired, 301s to /career/
