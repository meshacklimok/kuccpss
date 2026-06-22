from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from courses.models import Course, CourseType, CourseCategory
from institutions.models import Institution, InstitutionType
from clusters.models import Cluster
from resources.models import Article, Resource


class StaticPagesSitemap(Sitemap):
    priority = 1.0
    changefreq = "weekly"

    def items(self):
        return [
            "home",
            "clusterpoints:calculator",
            "clusterpoints:eligible_courses",
            "courses:course_types_list",
            "institutions:institution_types_list",
            "clusters:cluster_list",
            "resources:article_list",
            "resources:resource_list",
            "resources:how_to_guides",
            "resources:kuccps_calendar",
            "career:home",
        ]

    def location(self, item):
        return reverse(item)


class CourseSitemap(Sitemap):
    priority = 0.9
    changefreq = "monthly"

    def items(self):
        return Course.objects.select_related("course_type", "category").filter(
            course_type__isnull=False
        )

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)


class CourseTypeSitemap(Sitemap):
    priority = 0.8
    changefreq = "monthly"

    def items(self):
        return CourseType.objects.all()

    def location(self, obj):
        return reverse("courses:course_type_detail", kwargs={"type_slug": obj.slug})


class CourseCategorySitemap(Sitemap):
    priority = 0.75
    changefreq = "monthly"

    def items(self):
        return CourseCategory.objects.select_related("course_type").all()

    def location(self, obj):
        return reverse(
            "courses:course_category_detail",
            kwargs={"type_slug": obj.course_type.slug, "category_slug": obj.slug},
        )


class InstitutionSitemap(Sitemap):
    priority = 0.85
    changefreq = "monthly"

    def items(self):
        return Institution.objects.select_related("institution_type").all()

    def location(self, obj):
        return obj.get_absolute_url()

    def lastmod(self, obj):
        return getattr(obj, "updated_at", None) or getattr(obj, "created_at", None)


class InstitutionTypeSitemap(Sitemap):
    priority = 0.8
    changefreq = "monthly"

    def items(self):
        return InstitutionType.objects.all()

    def location(self, obj):
        return reverse(
            "institutions:institution_type_detail", kwargs={"type_slug": obj.slug}
        )


class ClusterSitemap(Sitemap):
    priority = 0.85
    changefreq = "monthly"

    def items(self):
        return Cluster.objects.all()

    def location(self, obj):
        return obj.get_absolute_url()


class ArticleSitemap(Sitemap):
    priority = 0.9
    changefreq = "weekly"

    def items(self):
        return Article.objects.filter(is_published=True).order_by("-updated_at")

    def location(self, obj):
        return reverse("resources:article_detail", kwargs={"slug": obj.slug})

    def lastmod(self, obj):
        return obj.updated_at


sitemaps = {
    "static": StaticPagesSitemap,
    "courses": CourseSitemap,
    "course-types": CourseTypeSitemap,
    "course-categories": CourseCategorySitemap,
    "institutions": InstitutionSitemap,
    "institution-types": InstitutionTypeSitemap,
    "clusters": ClusterSitemap,
    "articles": ArticleSitemap,
}
