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


class SyncContentTests(TestCase):
    """sync_content round-trips content into a database with different ids."""

    def test_export_then_import_into_empty_site(self):
        import os, tempfile
        from unittest import mock
        from django.core.management import call_command
        from accounts.models import User
        from career.models import QuizQuestion, QuizOption
        from courses.models import Course, CourseType
        from institutions.models import Institution, InstitutionType
        from mentorship.models import MentorProfile
        from resources.management.commands import sync_content

        inst = Institution.objects.create(name='Test Uni', institution_type=InstitutionType.objects.create(name='Uni'))
        course = Course.objects.create(name='BSc Test', course_type=CourseType.objects.create(name='Degree'))
        user = User.objects.create_user(email='mentor@example.com', password='secret123', full_name='Test Mentor')
        MentorProfile.objects.create(user=user, course=course, institution=inst, bio='Hi',
                                     wallet_balance=900, is_approved=True)
        q = QuizQuestion.objects.create(text='Do you like maths?', category='x', order=1)
        QuizOption.objects.create(question=q, text='Yes', career_tags='math', order=1)
        FAQItem.objects.create(question='What is this?', answer='A test')

        tmp = tempfile.mkdtemp()
        with mock.patch.object(sync_content, 'DATA_FILE', os.path.join(tmp, 'c.json')), \
             mock.patch.object(sync_content, 'MEDIA_DIR', os.path.join(tmp, 'media')):
            call_command('sync_content', export=True, stdout=open(os.devnull, 'w'))
            # The "live" site has the same courses/institutions but none of the content
            MentorProfile.objects.all().delete()
            User.objects.all().delete()
            QuizQuestion.objects.all().delete()
            FAQItem.objects.all().delete()
            call_command('sync_content', stdout=open(os.devnull, 'w'))

            m = MentorProfile.objects.get(user__email='mentor@example.com')
            self.assertEqual((m.course, m.institution, m.bio, m.is_approved), (course, inst, 'Hi', True))
            self.assertEqual(m.wallet_balance, 0)              # earnings never copied
            self.assertFalse(m.user.has_usable_password())    # test passwords never copied
            self.assertEqual(QuizOption.objects.get().question.text, 'Do you like maths?')
            self.assertTrue(FAQItem.objects.filter(question='What is this?').exists())

            # Second run is a no-op (marker), and --force doesn't duplicate rows
            FAQItem.objects.update(answer='edited on live')
            call_command('sync_content', stdout=open(os.devnull, 'w'))
            self.assertEqual(FAQItem.objects.get().answer, 'edited on live')
            call_command('sync_content', force=True, stdout=open(os.devnull, 'w'))
            self.assertEqual(FAQItem.objects.count(), 1)
            self.assertEqual(QuizOption.objects.count(), 1)
