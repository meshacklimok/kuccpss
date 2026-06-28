from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from courses.models import CourseType, CourseCategory, Course, Review


class CourseListTests(TestCase):
    def test_course_types_list_loads(self):
        response = self.client.get(reverse('courses:course_types_list'))
        self.assertIn(response.status_code, [200, 301, 302])


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
