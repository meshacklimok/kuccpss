from datetime import date, timedelta

from django.test import TestCase
from django.urls import reverse

from institutions.models import Institution, InstitutionPromotion, InstitutionType


class InstitutionTypeSlugTests(TestCase):
    def test_slug_auto_generated_from_name(self):
        itype = InstitutionType.objects.create(name="Public University")
        self.assertEqual(itype.slug, "public-university")

    def test_explicit_slug_not_overwritten(self):
        itype = InstitutionType.objects.create(name="KMTC", slug="custom-slug")
        self.assertEqual(itype.slug, "custom-slug")

    def test_bg_color_known_hex(self):
        itype = InstitutionType.objects.create(name="TVET", color_code="#059669")
        self.assertEqual(itype.bg_color, "#ecfdf5")

    def test_bg_color_unknown_hex_falls_back(self):
        itype = InstitutionType.objects.create(name="TTC", color_code="#123456")
        self.assertEqual(itype.bg_color, "#f8fafc")


class InstitutionSlugCollisionTests(TestCase):
    def setUp(self):
        self.itype = InstitutionType.objects.create(name="Public University")

    def test_slug_auto_generated(self):
        inst = Institution.objects.create(name="University of Nairobi", institution_type=self.itype)
        self.assertEqual(inst.slug, "university-of-nairobi")

    def test_duplicate_name_gets_suffixed_slug(self):
        first = Institution.objects.create(name="Kenyatta University", institution_type=self.itype)
        second = Institution.objects.create(name="Kenyatta University", institution_type=self.itype)
        self.assertEqual(first.slug, "kenyatta-university")
        self.assertEqual(second.slug, "kenyatta-university-1")

    def test_get_absolute_url(self):
        inst = Institution.objects.create(name="Moi University", institution_type=self.itype)
        url = inst.get_absolute_url()
        self.assertIn(self.itype.slug, url)
        self.assertIn(inst.slug, url)


class InstitutionPromotionLiveWindowTests(TestCase):
    def setUp(self):
        itype = InstitutionType.objects.create(name="Private University")
        self.institution = Institution.objects.create(name="Strathmore University", institution_type=itype)

    def test_is_live_within_window(self):
        promo = InstitutionPromotion.objects.create(
            institution=self.institution,
            start_date=date.today() - timedelta(days=1),
            end_date=date.today() + timedelta(days=1),
        )
        self.assertTrue(promo.is_live)

    def test_is_live_false_before_start(self):
        promo = InstitutionPromotion.objects.create(
            institution=self.institution,
            start_date=date.today() + timedelta(days=1),
            end_date=date.today() + timedelta(days=10),
        )
        self.assertFalse(promo.is_live)

    def test_is_live_false_after_end(self):
        promo = InstitutionPromotion.objects.create(
            institution=self.institution,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() - timedelta(days=1),
        )
        self.assertFalse(promo.is_live)

    def test_days_remaining_never_negative(self):
        promo = InstitutionPromotion.objects.create(
            institution=self.institution,
            start_date=date.today() - timedelta(days=10),
            end_date=date.today() - timedelta(days=1),
        )
        self.assertEqual(promo.days_remaining, 0)


class InstitutionViewTests(TestCase):
    def test_institution_types_list_loads(self):
        response = self.client.get(reverse("institutions:institution_types_list"))
        self.assertEqual(response.status_code, 200)

    def test_institution_detail_loads(self):
        itype = InstitutionType.objects.create(name="Public University")
        inst = Institution.objects.create(name="University of Nairobi", institution_type=itype)
        url = reverse(
            "institutions:institution_detail",
            kwargs={"type_slug": itype.slug, "institution_slug": inst.slug},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
