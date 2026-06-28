from django.test import TestCase, Client
from django.urls import reverse

from resources.models import SiteFeedback, Announcement, FAQItem, Article


class FeedbackSubmissionTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_feedback_requires_post(self):
        response = self.client.get(reverse('resources:submit_feedback'))
        self.assertEqual(response.status_code, 405)

    def test_valid_feedback_saved(self):
        response = self.client.post(reverse('resources:submit_feedback'), {
            'feedback_type': 'bug',
            'message': 'The calculator is broken on mobile.',
            'email': 'user@example.com',
            'page_url': '/clusterpoints/',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['ok'])
        self.assertEqual(SiteFeedback.objects.count(), 1)
        fb = SiteFeedback.objects.first()
        self.assertEqual(fb.feedback_type, 'bug')
        self.assertEqual(fb.status, 'new')

    def test_empty_message_rejected(self):
        response = self.client.post(reverse('resources:submit_feedback'), {
            'feedback_type': 'general',
            'message': '',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()['ok'])

    def test_invalid_type_defaults_to_general(self):
        self.client.post(reverse('resources:submit_feedback'), {
            'feedback_type': 'hacked',
            'message': 'Test message',
        })
        fb = SiteFeedback.objects.first()
        self.assertEqual(fb.feedback_type, 'general')


class AnnouncementModelTests(TestCase):
    def test_create_announcement(self):
        ann = Announcement.objects.create(
            title='Test Notice',
            body='Something important happened.',
            kind='info',
            is_active=True,
        )
        self.assertEqual(str(ann), 'Test Notice')

    def test_inactive_announcement_not_in_context(self):
        Announcement.objects.create(title='Hidden', body='Not shown', is_active=False)
        from django.utils import timezone
        from django.db.models import Q
        now = timezone.now()
        active = Announcement.objects.filter(is_active=True).filter(
            Q(starts_at__isnull=True) | Q(starts_at__lte=now)
        ).filter(
            Q(ends_at__isnull=True) | Q(ends_at__gte=now)
        )
        self.assertEqual(active.count(), 0)


class ArticleTests(TestCase):
    def test_article_list_loads(self):
        response = self.client.get(reverse('resources:article_list'))
        self.assertEqual(response.status_code, 200)

    def test_article_detail_404_for_unpublished(self):
        article = Article.objects.create(
            title='Draft Article',
            content='Not published yet.',
            is_published=False,
        )
        response = self.client.get(reverse('resources:article_detail', args=[article.slug]))
        self.assertEqual(response.status_code, 404)
