from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from courses.models import CourseType, CourseCategory, Course, Review


class CourseListTests(TestCase):
    def test_course_types_list_loads(self):
        response = self.client.get(reverse('courses:course_types_list'))
        self.assertIn(response.status_code, [200, 301, 302])

    def test_course_type_slug_is_case_insensitive(self):
        CourseType.objects.create(name='KMTC', slug='KMTC')
        response = self.client.get('/courses/kmtc/?q=nursing')
        self.assertRedirects(response, '/courses/KMTC/?q=nursing',
                             status_code=301, fetch_redirect_response=False)
        self.assertEqual(self.client.get('/courses/KMTC/').status_code, 200)
        self.assertEqual(self.client.get('/courses/no-such-type/').status_code, 404)


class ReviewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='reviewer@example.com',
            password='TestPass123!',
            full_name='Reviewer',
            is_verified=True,
        )
        self.course_type = CourseType.objects.create(name='Degree', slug='degree')
        self.category = CourseCategory.objects.create(
            name='Sciences', slug='sciences', course_type=self.course_type
        )
        self.course = Course.objects.create(
            name='Computer Science',
            slug='computer-science',
            course_type=self.course_type,
            category=self.category,
        )

    def test_review_requires_login(self):
        url = reverse('courses:submit_course_review', args=['degree', 'sciences', 'computer-science'])
        response = self.client.post(url, {'rating': 5, 'body': 'Great!'})
        # unauthenticated → redirect to login or forbidden
        self.assertIn(response.status_code, [302, 403])

    def test_authenticated_user_can_submit_review(self):
        self.client.force_login(self.user)
        url = reverse('courses:submit_course_review', args=['degree', 'sciences', 'computer-science'])
        response = self.client.post(url, {'rating': 4, 'body': 'Good course.'})
        self.assertIn(response.status_code, [200, 302])
        self.assertTrue(Review.objects.filter(course=self.course, user=self.user).exists())

    def test_review_model_str(self):
        Review.objects.create(user=self.user, course=self.course, rating=5, body='Excellent!')
        review = Review.objects.get(course=self.course)
        self.assertEqual(review.rating, 5)
        self.assertEqual(review.body, 'Excellent!')


class CatalogueTests(TestCase):
    """courses.catalogue: shared, read-only offering cache for the career engine."""

    def setUp(self):
        from institutions.models import Institution, InstitutionType
        from courses.models import CourseOffering
        self.kmtc = CourseType.objects.create(name='KMTC', slug='kmtc')
        inst_type = InstitutionType.objects.create(name='KMTC Campus')
        self.inst = Institution.objects.create(name='KMTC Nairobi', institution_type=inst_type)
        self.course = Course.objects.create(name='Diploma in Nursing', course_type=self.kmtc)
        CourseOffering.objects.create(course=self.course, institution=self.inst)

    def test_matches_queryset_and_shares_course_objects(self):
        from courses import catalogue
        from courses.models import CourseOffering
        other = type(self.inst).objects.create(
            name='KMTC Mombasa', institution_type=self.inst.institution_type)
        CourseOffering.objects.create(course=self.course, institution=other)
        offerings = catalogue.typed_offerings(['KMTC'])
        self.assertEqual({o.pk for o in offerings},
                         set(CourseOffering.objects.filter(course__course_type=self.kmtc).values_list('pk', flat=True)))
        self.assertIs(offerings[0].course, offerings[1].course)

    def test_course_change_invalidates_catalogue(self):
        from courses import catalogue
        before = catalogue.typed_offerings(['KMTC'])
        self.assertIs(catalogue.typed_offerings(['KMTC']), before)  # cached
        self.course.minimum_mean_grade = 'C'
        self.course.save()
        after = catalogue.typed_offerings(['KMTC'])
        self.assertIsNot(after, before)
        self.assertEqual(after[0].course.minimum_mean_grade, 'C')
