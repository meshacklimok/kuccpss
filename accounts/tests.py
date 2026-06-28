from django.test import TestCase, Client
from django.urls import reverse
from django.core import mail

from accounts.models import User


class RegistrationTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_register_page_loads(self):
        response = self.client.get(reverse('accounts:register'))
        self.assertEqual(response.status_code, 200)

    def test_register_creates_user(self):
        self.client.post(reverse('accounts:register'), {
            'full_name': 'Test Student',
            'email': 'student@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'agreed_terms': True,
        })
        self.assertTrue(User.objects.filter(email='student@example.com').exists())

    def test_register_sends_verification_email(self):
        self.client.post(reverse('accounts:register'), {
            'full_name': 'Email User',
            'email': 'emailuser@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'agreed_terms': True,
        })
        self.assertGreater(len(mail.outbox), 0)

    def test_duplicate_email_rejected(self):
        User.objects.create_user(email='dup@example.com', password='Pass123!', full_name='Dup')
        self.client.post(reverse('accounts:register'), {
            'full_name': 'Another',
            'email': 'dup@example.com',
            'password1': 'SecurePass123!',
            'password2': 'SecurePass123!',
            'agreed_terms': True,
        })
        self.assertEqual(User.objects.filter(email='dup@example.com').count(), 1)


class LoginTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='login@example.com',
            password='TestPass123!',
            full_name='Login User',
            is_verified=True,
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_valid_login_redirects(self):
        response = self.client.post(reverse('accounts:login'), {
            'email': 'login@example.com',
            'password': 'TestPass123!',
        })
        self.assertIn(response.status_code, [200, 302])

    def test_wrong_password_rejected(self):
        self.client.post(reverse('accounts:login'), {
            'email': 'login@example.com',
            'password': 'WrongPass!',
        })
        response = self.client.get(reverse('accounts:dashboard'))
        # anonymous user gets a 200 (guest dashboard), not authenticated
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_suspended_user_cannot_login(self):
        self.user.is_suspended = True
        self.user.save()
        self.client.post(reverse('accounts:login'), {
            'email': 'login@example.com',
            'password': 'TestPass123!',
        })
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertFalse(response.wsgi_request.user.is_authenticated)


class DashboardTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='dash@example.com',
            password='TestPass123!',
            full_name='Dash User',
            is_verified=True,
        )

    def test_dashboard_accessible_as_guest(self):
        # Dashboard shows a guest view rather than redirecting
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_dashboard_loads_when_authenticated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('accounts:dashboard'))
        self.assertEqual(response.status_code, 200)


class HealthCheckTests(TestCase):
    def test_health_endpoint_ok(self):
        response = self.client.get('/health/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['status'], 'ok')
        self.assertTrue(data['db'])
