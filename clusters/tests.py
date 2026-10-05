from io import StringIO
from types import SimpleNamespace

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from clusters.admin import ClusterAdmin
from clusters.constants import NUM_KUCCPS_CLUSTERS
from clusters.models import Cluster


class ExactlyEighteenClustersTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_clusters', stdout=StringIO())

    def test_seed_creates_exactly_18(self):
        self.assertEqual(NUM_KUCCPS_CLUSTERS, 18)
        self.assertEqual(Cluster.objects.count(), 18)
        self.assertEqual(
            list(Cluster.objects.kuccps().values_list('number', flat=True)),
            list(range(101, 119)),
        )

    def test_reseed_is_idempotent(self):
        call_command('seed_clusters', stdout=StringIO())
        self.assertEqual(Cluster.objects.count(), 18)

    def test_cannot_add_19th_cluster(self):
        with self.assertRaises(ValidationError):
            Cluster.objects.create(name='Extra Cluster')
        with self.assertRaises(ValidationError):
            Cluster(name='Extra Cluster').full_clean()
        self.assertEqual(Cluster.objects.count(), 18)

    def test_cannot_renumber_outside_range(self):
        c = Cluster.objects.get(number=101)
        c.number = 119
        with self.assertRaises(ValidationError):
            c.save()

    def test_admin_add_disabled_when_full(self):
        from django.contrib.admin.sites import site
        request = SimpleNamespace(user=SimpleNamespace(has_perm=lambda *a: True))
        self.assertFalse(ClusterAdmin(Cluster, site).has_add_permission(request))

    def test_free_slot_reused_after_delete(self):
        Cluster.objects.get(number=105).delete()
        c = Cluster.objects.create(name='Replacement')
        self.assertEqual(c.number, 105)

    def test_calculator_returns_18_results(self):
        from clusterpoints.services import calculate_clusters_anonymous
        results = calculate_clusters_anonymous({'Mathematics': 12, 'English': 12})
        self.assertEqual(len(results), 18)
